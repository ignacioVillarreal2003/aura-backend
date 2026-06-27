import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact_quiz.exceptions import (
    LLMServiceException,
    QuizAccessDeniedException,
    QuizNotFoundException,
    QuizOptionNotFoundException,
    QuizQuestionNotFoundException,
)
from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizQuestion
from apps.artifact_quiz.repositories.quiz_repository import quiz_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Generá el cuestionario a partir del o los documentos adjuntos."


def _normalize_questions(questions: list) -> list:
    from apps.artifact_quiz.models import ArtifactQuizQuestion

    valid_kinds = {c.value for c in ArtifactQuizQuestion.Kind}
    normalized = []
    for q_idx, q in enumerate(questions):
        q_type = str(q.get("type", ArtifactQuizQuestion.Kind.SINGLE))
        if q_type not in valid_kinds:
            q_type = ArtifactQuizQuestion.Kind.SINGLE
        options = q.get("options") or []
        normalized.append({
            "text": str(q.get("question", q.get("text", ""))),
            "kind": q_type,
            "explanation": str(q.get("explanation", "")),
            "position": q_idx,
            "options": [
                {
                    "text": str(opt.get("text", "")),
                    "is_correct": bool(opt.get("is_correct", False)),
                    "position": o_idx,
                }
                for o_idx, opt in enumerate(options)
            ],
        })
    return normalized


@transaction.atomic
def _persist_generated_quiz(
        *,
        user_id: int,
        title: str,
        description: str,
        query: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        instructions: str,
        questions: list,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.QUIZ,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    quiz = quiz_repository.create(
        user_id=user_id,
        instructions=instructions,
        questions=questions,
        artifact_id=artifact.id,
        title=title,
        description=description,
        query=query,
    )
    return artifact, quiz


class QuizService(ArtifactCrudService):
    repository = quiz_repository
    not_found_exc = QuizNotFoundException
    access_denied_exc = QuizAccessDeniedException
    log_model = "ArtifactQuiz"
    log_id_key = "quiz_id"
    perm_list = perms.LIST_QUIZZES
    perm_manage = perms.MANAGE_QUIZZES
    perm_get = perms.GET_QUIZ
    perm_update = perms.UPDATE_QUIZ
    perm_export = perms.EXPORT_QUIZ
    perm_manage_export = perms.MANAGE_EXPORT_QUIZ
    perm_delete = perms.DELETE_QUIZ
    logger = logger

    def list_quizzes(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_quizzes(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_quiz(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        return self._get(user, quiz_id)

    def get_own_quiz(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        return self._get_own(user, quiz_id)

    def get_quiz_admin_export(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        return self._get_admin_export(user, quiz_id)

    def delete_quiz(self, user: AuthenticatedUser, quiz_id: int) -> None:
        self._delete(user, quiz_id)

    @transaction.atomic
    def answer_question(
            self,
            user: AuthenticatedUser,
            quiz_id: int,
            question_id: int,
            option_id: int,
    ) -> dict:
        """Guarda la opción seleccionada para una pregunta y devuelve la corrección.

        Requiere permiso ``UPDATE_QUIZ`` y ser el creador del quiz o un miembro
        activo (contributor) del chat de origen.
        """
        AccessControl.require_permissions(user, frozenset({self.perm_update}))
        quiz = self.repository.get_by_id_for_update(quiz_id)
        if quiz is None:
            raise self.not_found_exc()
        self._assert_access(user.id, quiz, require_contributor=True)

        question = self.repository.get_question(quiz_id, question_id)
        if question is None:
            raise QuizQuestionNotFoundException()
        option = self.repository.get_option(question_id, option_id)
        if option is None:
            raise QuizOptionNotFoundException()

        self.repository.set_selected_option(question, option_id)

        quiz = self.repository.get_by_id(quiz_id)
        total, answered, correct = self._progress(quiz)
        correct_ids = [opt.id for opt in question.options.all() if opt.is_correct]
        return {
            "question_id": question_id,
            "selected_option_id": option_id,
            "is_correct": bool(option.is_correct),
            "correct_option_ids": correct_ids,
            "answered_count": answered,
            "correct_count": correct,
            "total_questions": total,
            "score_pct": round(correct / total * 100) if total else 0,
        }

    @transaction.atomic
    def reset_quiz(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        """Limpia todas las respuestas seleccionadas del quiz."""
        AccessControl.require_permissions(user, frozenset({self.perm_update}))
        quiz = self.repository.get_by_id_for_update(quiz_id)
        if quiz is None:
            raise self.not_found_exc()
        self._assert_access(user.id, quiz, require_contributor=True)
        self.repository.reset_answers(quiz_id)
        self.logger.info("ArtifactQuiz answers reset", extra={"user_id": user.id, self.log_id_key: quiz_id})
        return self.repository.get_by_id(quiz_id)

    @staticmethod
    def _progress(quiz: ArtifactQuiz) -> tuple[int, int, int]:
        questions = list(quiz.questions.all())
        total = len(questions)
        answered = 0
        correct = 0
        for q in questions:
            if q.selected_option_id is None:
                continue
            answered += 1
            if any(o.id == q.selected_option_id and o.is_correct for o in q.options.all()):
                correct += 1
        return total, answered, correct

    async def generate_quiz(
            self,
            user: AuthenticatedUser,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactQuiz, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_QUIZ_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)
        human_text = message.strip() if message else _DOCUMENTS_ONLY_INSTRUCTION
        messages = history + [{"role": "human", "content": human_text}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_quiz_stream_events(
                    messages=messages,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
                    document_ids=document_ids,
            ):
                et = event.get("type")
                if et == "progress":
                    await broadcast_artifact_progress(chat_id, str(event.get("step", "")),
                                                      str(event.get("message", "")))
                elif et == "complete":
                    result_data = event.get("result") or {}
                elif et == "error":
                    logger.error(
                        "LLM quiz stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM quiz-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM quiz stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        title = str(result_data.get("title", "")).strip()
        description = str(result_data.get("description", "")).strip()
        raw_questions = result_data.get("questions") or []
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))
        instructions = str(result_data.get("instructions", ""))

        if not title:
            logger.error("LLM returned empty title for quiz", extra={"user_id": user.id})
            raise LLMServiceException()
        if not raw_questions:
            logger.error("LLM returned empty questions for quiz", extra={"user_id": user.id})
            raise LLMServiceException()

        questions = _normalize_questions(raw_questions)
        artifact, quiz = await sync_to_async(_persist_generated_quiz)(
            user_id=user.id,
            title=title,
            description=description,
            query=message,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            instructions=instructions,
            questions=questions,
            fragments=fragments,
        )
        logger.info(
            "ArtifactQuiz generated and saved",
            extra={
                "user_id": user.id,
                "quiz_id": quiz.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return quiz, out_messages, fragments


quiz_service = QuizService()

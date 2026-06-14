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
from apps.artifact_quiz.exceptions import QuizAccessDeniedException, QuizNotFoundException, LLMServiceException
from apps.artifact_quiz.models import ArtifactQuiz
from apps.artifact_quiz.repositories.quiz_repository import quiz_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


def _to_int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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
        mode: str,
        source_chat_id: int,
        instructions: str,
        pass_score,
        questions: list,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.QUIZ,
        mode=mode,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    quiz = quiz_repository.create(
        user_id=user_id,
        instructions=instructions,
        pass_score=pass_score,
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

    async def generate_quiz(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactQuiz, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_QUIZ_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)
        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_quiz_stream_events(
                    messages=messages,
                    mode=mode,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
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
        passing_score = _to_int_or_none(result_data.get("passing_score"))

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
            mode=mode,
            source_chat_id=chat_id,
            instructions=instructions,
            pass_score=passing_score,
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

import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact_quiz.exceptions import QuizAccessDeniedException, QuizNotFoundException, LLMServiceException
from apps.artifact_quiz.models import ArtifactQuiz
from apps.artifact_quiz.repositories.quiz_repository import quiz_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


def _to_int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _assert_quiz_access(user_id: int, quiz, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, quiz, QuizAccessDeniedException(), require_contributor=require_contributor)


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
        title=title,
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
    )
    return artifact, quiz


class QuizService:
    def list_quizzes(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_QUIZZES}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return quiz_repository.list_by_chat(source_chat_id=chat_id)

    def list_all_quizzes(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_QUIZZES}))
        return quiz_repository.list_all()

    def get_quiz(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        AccessControl.require_permissions(user, frozenset({perms.GET_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz)
        return quiz

    def get_own_quiz(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz)
        return quiz

    def get_quiz_admin_export(self, user: AuthenticatedUser, quiz_id: int) -> ArtifactQuiz:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        return quiz

    @transaction.atomic
    def update_quiz(
            self,
            user: AuthenticatedUser,
            quiz_id: int,
            title: Optional[str] = None,
            instructions: Optional[str] = None,
            pass_score: Optional[int] = None,
            pass_score_provided: bool = False,
            questions: Optional[list] = None,
    ) -> ArtifactQuiz:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_QUIZ}))
        quiz = quiz_repository.get_by_id_for_update(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz, require_contributor=True)
        if title is not None:
            artifact_repository.update(quiz.artifact, updated_by=user.id, title=title)
        normalized = _normalize_questions(questions) if questions is not None else None
        return quiz_repository.update(
            quiz,
            updated_by=user.id,
            instructions=instructions,
            pass_score=pass_score,
            pass_score_provided=pass_score_provided,
            questions=normalized,
        )

    @transaction.atomic
    def delete_quiz(self, user: AuthenticatedUser, quiz_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_QUIZ}))
        quiz = quiz_repository.get_by_id_for_update(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz, require_contributor=True)
        quiz_repository.soft_delete(quiz, deleted_by=user.id)
        _cleanup_artifact_interactions(quiz.artifact_id)
        artifact_repository.soft_delete(quiz.artifact, deleted_by=user.id)
        logger.info("ArtifactQuiz deleted", extra={"user_id": user.id, "quiz_id": quiz_id})

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
        history = await sync_to_async(build_chat_history)(chat_id)
        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_quiz_stream_events(
                    messages=messages,
                    mode=mode,
                    user=user,
                    chat_id=chat_id,
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

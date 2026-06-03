import logging
from typing import Optional

from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import QuizGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.quiz.exceptions import QuizAccessDeniedException, QuizNotFoundException, LLMServiceException
from apps.quiz.models import Quiz
from apps.quiz.repositories.quiz_repository import quiz_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.models.artifact_message import ArtifactMessage
from apps.message.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)


def _assert_quiz_access(user_id: int, quiz: Quiz, *, require_contributor: bool = False) -> None:
    if quiz.created_by == user_id:
        return
    source_chat_id = quiz.artifact.source_chat_id
    checker = (
        membership_repository.is_active_contributor
        if require_contributor
        else membership_repository.is_active_member
    )
    if checker(source_chat_id, user_id):
        return
    raise QuizAccessDeniedException()


def _normalize_questions(questions: list) -> list:
    from apps.quiz.models import ArtifactQuizQuestion

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


class QuizService:
    def list_quizzes(self, user: AuthenticatedUser, chat_id: Optional[int] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_QUIZZES}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return quiz_repository.list_by_chat(source_chat_id=chat_id)
        return quiz_repository.list_by_user(user_id=user.id)

    def list_all_quizzes(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_QUIZZES}))
        return quiz_repository.list_all()

    def get_quiz(self, user: AuthenticatedUser, quiz_id: int) -> Quiz:
        AccessControl.require_permissions(user, frozenset({perms.GET_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz)
        return quiz

    def get_own_quiz(self, user: AuthenticatedUser, quiz_id: int) -> Quiz:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz)
        return quiz

    def get_quiz_admin_export(self, user: AuthenticatedUser, quiz_id: int) -> Quiz:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        return quiz

    def update_quiz(
            self,
            user: AuthenticatedUser,
            quiz_id: int,
            instructions: Optional[str] = None,
            pass_score: Optional[int] = None,
            pass_score_provided: bool = False,
            questions: Optional[list] = None,
    ) -> Quiz:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz, require_contributor=True)
        normalized = _normalize_questions(questions) if questions is not None else None
        return quiz_repository.update(
            quiz,
            updated_by=user.id,
            instructions=instructions,
            pass_score=pass_score,
            pass_score_provided=pass_score_provided,
            questions=normalized,
        )

    def delete_quiz(self, user: AuthenticatedUser, quiz_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_QUIZ}))
        quiz = quiz_repository.get_by_id(quiz_id)
        if quiz is None:
            raise QuizNotFoundException()
        _assert_quiz_access(user.id, quiz, require_contributor=True)
        quiz_repository.soft_delete(quiz, deleted_by=user.id)
        logger.info("Quiz deleted", extra={"user_id": user.id, "quiz_id": quiz_id})

    async def generate_quiz(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[Quiz, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_QUIZ_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        is_contributor = await sync_to_async(membership_repository.is_active_contributor)(chat_id, user.id)
        if not is_contributor:
            raise ChatAccessDeniedException()
        history: list[dict] = []
        recent = await sync_to_async(message_repository.get_recent_messages)(chat_id, limit=20)
        recent.reverse()
        for msg in recent:
            role = "human" if msg.sender_type == ArtifactMessage.SenderType.USER else "assistant"
            history.append({"role": role, "content": msg.message})

        messages = history + [{"role": "human", "content": message}]
        try:
            result: QuizGenerateResult = await llm_client.generate_quiz(
                messages=messages,
                mode=mode,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM quiz-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.title or not result.title.strip():
            logger.error("LLM returned empty title for quiz", extra={"user_id": user.id})
            raise LLMServiceException()
        if not result.questions:
            logger.error("LLM returned empty questions for quiz", extra={"user_id": user.id})
            raise LLMServiceException()

        questions = _normalize_questions(result.questions)
        artifact_id = await sync_to_async(self._create_artifact_header)(
            user_id=user.id,
            title=result.title,
            mode=mode,
            source_chat_id=chat_id,
        )
        quiz = await sync_to_async(quiz_repository.create)(
            user_id=user.id,
            instructions=result.instructions,
            pass_score=result.passing_score,
            questions=questions,
            artifact_id=artifact_id,
        )
        logger.info(
            "Quiz generated and saved",
            extra={
                "user_id": user.id,
                "quiz_id": quiz.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact_id,
            },
        )
        return quiz, result.messages, result.fragments

    @staticmethod
    def _create_artifact_header(
            *,
            user_id: int,
            title: str,
            mode: str,
            source_chat_id: int,
    ) -> Optional[int]:
        """Create the unified artifact header (+ initial version) for a quiz.

        Soft-fails: a failure here must never block quiz generation.
        """
        try:
            artifact = artifact_repository.create(
                user_id=user_id,
                type=Artifact.Type.QUIZ,
                title=title,
                status=Artifact.Status.FINAL,
                mode=mode,
                source_chat_id=source_chat_id,
            )
            return artifact.id
        except Exception:
            logger.warning(
                "Failed to create artifact header for quiz",
                extra={"user_id": user_id, "source_chat_id": source_chat_id},
                exc_info=True,
            )
            return None


quiz_service = QuizService()

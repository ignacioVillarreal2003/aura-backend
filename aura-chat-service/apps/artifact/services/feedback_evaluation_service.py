import logging
import concurrent.futures
from django.db import close_old_connections, transaction
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.artifact.models.artifact import Artifact
from apps.artifact.models.artifact_feedback import ArtifactFeedback
from apps.artifact.models.artifact_feedback_evaluation import ArtifactFeedbackEvaluation
from apps.artifact_message.models import ArtifactMessage
from apps.artifact_message.repositories.message_repository import message_repository
from core.clients.llm_client import llm_client
from core.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="feedback_eval")


class FeedbackEvaluationService:
    def trigger_evaluation(self, feedback_id: int) -> None:
        """Triggers the evaluation of negative feedback in a background thread."""
        logger.info(f"Triggering feedback evaluation in background for feedback_id: {feedback_id}")
        _executor.submit(self._evaluate, feedback_id)

    def _evaluate(self, feedback_id: int) -> None:
        try:
            self._execute_evaluation(feedback_id)
        except Exception as e:
            logger.exception(f"Error evaluating feedback_id {feedback_id}: {e}")
        finally:
            close_old_connections()

    def _execute_evaluation(self, feedback_id: int) -> None:
        # Fetch feedback details
        try:
            feedback = ArtifactFeedback.objects.select_related("artifact").get(id=feedback_id)
        except ArtifactFeedback.DoesNotExist:
            logger.warning(f"Feedback with id {feedback_id} does not exist, skipping evaluation.")
            return

        if feedback.value != -1:
            logger.info(f"Feedback {feedback_id} is not negative (value={feedback.value}), skipping evaluation.")
            return

        artifact = feedback.artifact
        if artifact.type != Artifact.Type.MESSAGE:
            logger.warning(f"Artifact {artifact.id} is not a MESSAGE, skipping evaluation.")
            return

        # Fetch the assistant message content
        try:
            assistant_msg = ArtifactMessage.objects.get(artifact=artifact)
        except ArtifactMessage.DoesNotExist:
            logger.warning(f"ArtifactMessage content for artifact {artifact.id} does not exist, skipping.")
            return

        if assistant_msg.sender_type != ArtifactMessage.SenderType.ASSISTANT:
            logger.warning(f"ArtifactMessage for artifact {artifact.id} is not from ASSISTANT, skipping.")
            return

        # Retrieve conversation history around this message
        chat_id = artifact.source_chat_id
        recent_msgs = message_repository.get_recent_messages(chat_id, limit=15)
        # Sort chronologically (oldest first)
        ordered_msgs = list(reversed(recent_msgs))

        # Find the index of our assistant message in the chronological order
        assistant_idx = -1
        for i, m in enumerate(ordered_msgs):
            if m.artifact_id == artifact.id:
                assistant_idx = i
                break

        if assistant_idx == -1:
            logger.error(f"Assistant message with artifact {artifact.id} not found in recent history of chat {chat_id}.")
            return

        # User query is the user message immediately preceding the assistant message
        user_query = ""
        for i in range(assistant_idx - 1, -1, -1):
            if ordered_msgs[i].sender_type == ArtifactMessage.SenderType.USER:
                user_query = ordered_msgs[i].message
                break

        # If no preceding user message is found, default to the one before assistant_idx if it exists, or empty
        if not user_query and assistant_idx > 0:
            user_query = ordered_msgs[assistant_idx - 1].message

        # Build chat history up to (but not including) the assistant's message
        chat_history = []
        for m in ordered_msgs[:assistant_idx]:
            role = "user" if m.sender_type == ArtifactMessage.SenderType.USER else "assistant"
            chat_history.append({"role": role, "content": m.message})

        # Build AuthenticatedUser dummy to forward authentication headers downstream
        # We fetch the user details of the evaluator or the user who created the feedback
        # In base, we use a service user or a dummy user representing the feedback creator.
        user_id = feedback.created_by
        # Create a mock/dummy user representing the authenticated user who initiated this
        user = AuthenticatedUser(
            id=user_id,
            email=f"user_{user_id}@local.aura",
            first_name="",
            last_name="",
            permissions=frozenset(),
            roles=frozenset(),
        )

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            eval_result = loop.run_until_complete(
                llm_client.evaluate_feedback(
                    user_query=user_query,
                    assistant_response=assistant_msg.message,
                    chat_history=chat_history,
                    user=user,
                    fragments=artifact.fragments or [],
                    feedback_reason=feedback.reason,
                    feedback_comment=feedback.comment or "",
                    mode=artifact.mode,
                )
            )
        finally:
            loop.close()

        # Parse evaluation response and persist
        failure_category = eval_result.get("failure_category", "other")
        failure_explanation = eval_result.get("failure_explanation", "")
        expected_output = eval_result.get("expected_output", "")
        confidence_score = eval_result.get("confidence_score")
        judge_model = eval_result.get("judge_model", "judge-model")

        # Save or update the evaluation
        with transaction.atomic():
            ArtifactFeedbackEvaluation.objects.update_or_create(
                feedback=feedback,
                defaults={
                    "judge_model": judge_model,
                    "failure_category": failure_category,
                    "failure_explanation": failure_explanation,
                    "expected_output": expected_output,
                    "confidence_score": confidence_score,
                    "raw_response": eval_result,
                }
            )
        logger.info(f"Successfully evaluated and saved feedback_id {feedback_id} with category {failure_category}.")


feedback_evaluation_service = FeedbackEvaluationService()

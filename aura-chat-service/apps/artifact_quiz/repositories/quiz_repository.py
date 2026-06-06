import logging
from typing import Optional
from django.db import transaction
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.artifact_quiz.models import ArtifactQuiz, ArtifactQuizOption, ArtifactQuizQuestion

logger = logging.getLogger(__name__)

_QUESTIONS_PREFETCH = Prefetch("questions", queryset=ArtifactQuizQuestion.objects.prefetch_related(
    Prefetch("options", queryset=ArtifactQuizOption.objects.order_by("position"))
).order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_QUESTIONS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(question_count=Count("questions", distinct=True))


def _bulk_create_questions(quiz_id: int, questions: list) -> None:
    question_objs = [
        ArtifactQuizQuestion(
            quiz_id=quiz_id,
            text=q["text"],
            kind=q["kind"],
            explanation=str(q.get("explanation", "")),
            position=q["position"],
        )
        for q in questions
    ]
    created = ArtifactQuizQuestion.objects.bulk_create(question_objs)

    option_objs = []
    for question_obj, question_data in zip(created, questions):
        for opt in question_data.get("options", []):
            option_objs.append(ArtifactQuizOption(
                question_id=question_obj.id,
                text=opt["text"],
                is_correct=bool(opt.get("is_correct", False)),
                position=opt["position"],
            ))
    if option_objs:
        ArtifactQuizOption.objects.bulk_create(option_objs)


class QuizRepository:
    def create(
            self,
            *,
            user_id: int,
            questions: list,
            instructions: str = "",
            pass_score: Optional[int] = None,
            artifact_id: int,
    ) -> ArtifactQuiz:
        quiz = ArtifactQuiz.objects.create(
            created_by=user_id,
            instructions=instructions,
            pass_score=pass_score,
            artifact_id=artifact_id,
        )
        _bulk_create_questions(quiz.id, questions)
        return _with_prefetch(ArtifactQuiz.objects.filter(id=quiz.id)).first()

    def get_by_id(self, quiz_id: int) -> Optional[ArtifactQuiz]:
        return _with_prefetch(ArtifactQuiz.objects.filter(id=quiz_id)).first()

    def get_by_id_for_update(self, quiz_id: int) -> Optional[ArtifactQuiz]:
        return ArtifactQuiz.objects.select_for_update().select_related("artifact").filter(id=quiz_id).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactQuiz.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactQuiz.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactQuiz.objects.all())

    @transaction.atomic
    def update(
            self,
            quiz: ArtifactQuiz,
            *,
            updated_by: int,
            instructions: Optional[str] = None,
            pass_score: Optional[int] = None,
            pass_score_provided: bool = False,
            questions: Optional[list] = None,
    ) -> ArtifactQuiz:
        update_fields = []
        if instructions is not None:
            quiz.instructions = instructions
            update_fields.append("instructions")
        if pass_score_provided:
            quiz.pass_score = pass_score
            update_fields.append("pass_score")
        if questions is not None:
            ArtifactQuizQuestion.objects.filter(quiz_id=quiz.id).delete()
            _bulk_create_questions(quiz.id, questions)
        if update_fields:
            quiz.updated_by = updated_by
            update_fields.append("updated_by")
            quiz.save(update_fields=update_fields)
        elif questions is not None:
            quiz.updated_by = updated_by
            quiz.save(update_fields=["updated_by"])
        return _with_prefetch(ArtifactQuiz.objects.filter(id=quiz.id)).first()

    def soft_delete(self, quiz: ArtifactQuiz, deleted_by: int) -> None:
        quiz.delete(deleted_by=deleted_by)


quiz_repository = QuizRepository()

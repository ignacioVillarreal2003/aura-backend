import logging
from typing import Optional
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


def _bulk_create_questions(quiz_id: int, questions: list, created_by: int) -> None:
    question_objs = [
        ArtifactQuizQuestion(
            quiz_id=quiz_id,
            text=q["text"],
            kind=q["kind"],
            explanation=str(q.get("explanation", "")),
            position=q["position"],
            created_by=created_by,
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
                created_by=created_by,
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
            artifact_id: int,
            title: str = "",
            description: str = "",
            query: str = "",
    ) -> ArtifactQuiz:
        quiz = ArtifactQuiz.objects.create(
            created_by=user_id,
            instructions=instructions,
            artifact_id=artifact_id,
            title=title,
            description=description,
            query=query,
        )
        _bulk_create_questions(quiz.id, questions, created_by=user_id)
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

    def soft_delete(self, quiz: ArtifactQuiz, deleted_by: int) -> None:
        quiz.delete(deleted_by=deleted_by)

    def get_question(self, quiz_id: int, question_id: int) -> Optional[ArtifactQuizQuestion]:
        return (
            ArtifactQuizQuestion.objects
            .prefetch_related("options")
            .filter(id=question_id, quiz_id=quiz_id)
            .first()
        )

    def get_option(self, question_id: int, option_id: int) -> Optional[ArtifactQuizOption]:
        return ArtifactQuizOption.objects.filter(id=option_id, question_id=question_id).first()

    def set_selected_option(self, question: ArtifactQuizQuestion, option_id: Optional[int]) -> ArtifactQuizQuestion:
        question.selected_option_id = option_id
        question.save(update_fields=["selected_option_id"])
        return question

    def reset_answers(self, quiz_id: int) -> None:
        ArtifactQuizQuestion.objects.filter(quiz_id=quiz_id).update(selected_option_id=None)


quiz_repository = QuizRepository()

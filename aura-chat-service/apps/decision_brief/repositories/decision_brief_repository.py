import logging
from typing import Optional
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.decision_brief.models import DecisionBrief, DecisionBriefOption

logger = logging.getLogger(__name__)

_OPTIONS_PREFETCH = Prefetch("options", queryset=DecisionBriefOption.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.prefetch_related(_OPTIONS_PREFETCH)


def _with_counts(qs):
    return qs.annotate(option_count=Count("options", distinct=True))


def _bulk_create_options(decision_brief_id: int, options: list) -> None:
    option_objs = [
        DecisionBriefOption(
            decision_brief_id=decision_brief_id,
            title=opt["title"],
            description=str(opt.get("description", "")),
            pros=str(opt.get("pros", "")),
            cons=str(opt.get("cons", "")),
            is_recommended=bool(opt.get("is_recommended", False)),
            position=opt["position"],
        )
        for opt in options
    ]
    if option_objs:
        DecisionBriefOption.objects.bulk_create(option_objs)


class DecisionBriefRepository:
    def create(
            self,
            *,
            user_id: int,
            title: str,
            options: list,
            mode: str,
            problem: str = "",
            context: str = "",
            risks: str = "",
            recommendation: str = "",
            source_chat_id: Optional[int] = None,
            artifact_id: Optional[int] = None,
    ) -> DecisionBrief:
        brief = DecisionBrief.objects.create(
            created_by=user_id,
            title=title,
            problem=problem,
            context=context,
            risks=risks,
            recommendation=recommendation,
            mode=mode,
            source_chat_id=source_chat_id,
            artifact_id=artifact_id,
        )
        _bulk_create_options(brief.id, options)
        return _with_prefetch(DecisionBrief.objects.filter(id=brief.id)).first()

    def get_by_id(self, decision_brief_id: int) -> Optional[DecisionBrief]:
        return _with_prefetch(DecisionBrief.objects.filter(id=decision_brief_id)).first()

    def list_by_user(self, user_id: int):
        return _with_counts(DecisionBrief.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(DecisionBrief.objects.filter(source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(DecisionBrief.objects.all())

    def update(
            self,
            brief: DecisionBrief,
            *,
            updated_by: int,
            title: Optional[str] = None,
            problem: Optional[str] = None,
            context: Optional[str] = None,
            risks: Optional[str] = None,
            recommendation: Optional[str] = None,
            options: Optional[list] = None,
    ) -> DecisionBrief:
        update_fields = []
        for field, value in (
            ("title", title),
            ("problem", problem),
            ("context", context),
            ("risks", risks),
            ("recommendation", recommendation),
        ):
            if value is not None:
                setattr(brief, field, value)
                update_fields.append(field)
        if options is not None:
            DecisionBriefOption.objects.filter(decision_brief_id=brief.id).delete()
            _bulk_create_options(brief.id, options)
        if update_fields:
            brief.updated_by = updated_by
            update_fields.append("updated_by")
            brief.save(update_fields=update_fields)
        elif options is not None:
            brief.updated_by = updated_by
            brief.save(update_fields=["updated_by"])
        return _with_prefetch(DecisionBrief.objects.filter(id=brief.id)).first()

    def soft_delete(self, brief: DecisionBrief, deleted_by: int) -> None:
        brief.delete(deleted_by=deleted_by)


decision_brief_repository = DecisionBriefRepository()

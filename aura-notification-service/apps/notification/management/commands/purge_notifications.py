import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notification.models import Notification

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Hard-delete notifications soft-deleted for more than "
        "NOTIFICATION_HARD_DELETE_DAYS days (default: 90)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override NOTIFICATION_HARD_DELETE_DAYS for this run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        days = options["days"] or getattr(settings, "NOTIFICATION_HARD_DELETE_DAYS", 90)
        cutoff = timezone.now() - timedelta(days=days)

        queryset = Notification.objects.filter(
            deleted_at__isnull=False,
            deleted_at__lte=cutoff,
        )
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Would hard-delete {count} notification(s) "
                    f"soft-deleted before {cutoff.date()} ({days} days ago)."
                )
            )
            return

        deleted, _ = queryset.delete()
        msg = (
            f"Hard-deleted {deleted} notification(s) soft-deleted before "
            f"{cutoff.date()} ({days} days ago)."
        )
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)

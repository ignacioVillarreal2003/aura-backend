"""Management command to revoke and delete expired refresh tokens."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import RefreshToken


class Command(BaseCommand):
    help = 'Revoke expired refresh tokens and delete revoked ones older than 30 days.'

    def handle(self, *args, **options):
        now = timezone.now()

        # Mark expired-but-not-revoked tokens as revoked
        expired = RefreshToken.objects.filter(expires_at__lte=now, is_revoked=False)
        count_revoked = expired.update(is_revoked=True, updated_at=now)

        # Delete tokens that have been revoked for more than 30 days
        cutoff = now - timezone.timedelta(days=30)
        deleted, _ = RefreshToken.objects.filter(
            is_revoked=True,
            updated_at__lte=cutoff,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Revoked {count_revoked} expired tokens. Deleted {deleted} old revoked tokens.'
            )
        )

"""Comando para revocar y borrar refresh tokens vencidos."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import RefreshToken


class Command(BaseCommand):
    help = 'Revoca los refresh tokens vencidos y borra los revocados de mas de 30 dias.'

    def handle(self, *args, **options):
        now = timezone.now()

        expired = RefreshToken.objects.filter(expires_at__lte=now, is_revoked=False)
        count_revoked = expired.update(is_revoked=True, updated_at=now)

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

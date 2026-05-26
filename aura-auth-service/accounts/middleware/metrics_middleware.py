import logging

from django.conf import settings
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

_METRICS_PATHS = {"/metrics", "/metrics/"}


class MetricsAccessMiddleware:
    """Restricts /metrics to allowed internal IPs only."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in _METRICS_PATHS:
            allowed = getattr(settings, "METRICS_ALLOWED_IPS", ["127.0.0.1", "::1"])
            client_ip = request.META.get("REMOTE_ADDR", "")
            if client_ip not in allowed:
                logger.warning(
                    "Metrics access denied.",
                    extra={"ip": client_ip},
                )
                return HttpResponseForbidden("Access denied.")
        return self.get_response(request)

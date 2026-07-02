import logging
import aio_pika.abc

logger = logging.getLogger(__name__)

RETRY_COUNT_HEADER = "x-retry-count"


def extract_retry_count(message: aio_pika.abc.AbstractIncomingMessage) -> int:
    if not message.headers:
        return 0
    raw = message.headers.get(RETRY_COUNT_HEADER)
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        logger.warning("The retry-count header could not be parsed; treating retry count as zero.")
        return 0

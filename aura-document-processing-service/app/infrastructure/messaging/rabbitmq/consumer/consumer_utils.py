import logging
import aio_pika.abc

logger = logging.getLogger(__name__)


def extract_retry_count(message: aio_pika.abc.AbstractIncomingMessage) -> int:
    if not message.headers:
        return 0
    x_death = message.headers.get("x-death")
    if not x_death:
        return 0
    try:
        return int(sum(entry.get("count", 0) for entry in x_death))
    except Exception:
        logger.warning("The x-death header could not be parsed; treating retry count as zero.")
        return 0

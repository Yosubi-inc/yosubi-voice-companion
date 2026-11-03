"""Bounded retries for external service calls."""
import random
import time


def transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", getattr(exc, "status", None))
    return isinstance(exc, (TimeoutError, ConnectionError)) or status == 429 or (isinstance(status, int) and 500 <= status < 600)


def retry(call, *, attempts=3, base_delay=0.1, retryable=transient, sleep=time.sleep, jitter=random.uniform):
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            if attempt == attempts - 1 or not retryable(exc):
                raise
            delay = base_delay * (2 ** attempt)
            sleep(delay + jitter(0, delay))

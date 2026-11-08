from collections import deque
from threading import Lock
from time import monotonic


class RateLimitExceededError(Exception):
    pass


# Rate limiting en memoria del proceso (MVP, una instancia). En multiinstancia usar Redis o storage compartido.
_SWEEP_INTERVAL_SECONDS = 60.0

_attempts: dict[str, deque[float]] = {}
_lock = Lock()
_max_window_seconds = 0.0
_last_sweep = monotonic()


def check_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    global _max_window_seconds
    now = monotonic()
    with _lock:
        _max_window_seconds = max(_max_window_seconds, float(window_seconds))
        _sweep_expired_buckets(now)

        bucket = _attempts.setdefault(key, deque())
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            raise RateLimitExceededError

        bucket.append(now)


def _sweep_expired_buckets(now: float) -> None:
    """Elimina claves sin intentos recientes para que la memoria no crezca sin limite."""
    global _last_sweep
    if now - _last_sweep < _SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep = now
    expired = [key for key, bucket in _attempts.items() if not bucket or now - bucket[-1] >= _max_window_seconds]
    for key in expired:
        del _attempts[key]


def rate_limit_bucket_count() -> int:
    with _lock:
        return len(_attempts)


def clear_rate_limit_state() -> None:
    global _max_window_seconds, _last_sweep
    with _lock:
        _attempts.clear()
        _max_window_seconds = 0.0
        _last_sweep = monotonic()

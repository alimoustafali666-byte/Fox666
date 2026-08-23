import time
from collections import defaultdict
from threading import Lock

from app.core.config import settings


class InMemoryLoginRateLimiter:
    """Fixed-window failed-login counter, keyed by normalized email.

    LIMITATION (documented, not hidden): this state lives in this one
    Python process's memory. It is NOT shared across multiple backend
    replicas/workers -- in a horizontally-scaled deployment, each
    instance enforces its own independent limit, so the effective limit
    an attacker faces is (max_attempts * number_of_instances), and a
    lockout on one instance doesn't apply on another. That's an accepted
    tradeoff for a single-instance MVP; the fix when scaling out is a
    shared store (Redis, most commonly) behind this same interface, not
    a rewrite of the callers.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    @staticmethod
    def _normalize(key: str) -> str:
        return key.strip().lower()

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self._window_seconds
        self._failures[key] = [t for t in self._failures[key] if t > cutoff]

    def is_locked(self, key: str) -> bool:
        key = self._normalize(key)
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            return len(self._failures[key]) >= self._max_attempts

    def record_failure(self, key: str) -> None:
        key = self._normalize(key)
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._failures[key].append(now)

    def reset(self, key: str) -> None:
        key = self._normalize(key)
        with self._lock:
            self._failures.pop(key, None)

    def reset_all(self) -> None:
        """Test-only convenience: this limiter is a process-wide singleton
        (see login_rate_limiter below), so tests must clear it between
        cases to avoid one test's failed attempts bleeding into another's.
        """
        with self._lock:
            self._failures.clear()


login_rate_limiter = InMemoryLoginRateLimiter(
    max_attempts=settings.login_rate_limit_max_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)


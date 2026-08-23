"""Reuses the existing generic fixed-window limiter (see
app.modules.auth.rate_limit's documented single-instance-only
limitation, which applies identically here) rather than introducing
Redis solely for Step 17. Keyed by user_id, not IP or email -- a support
action is always made by an authenticated user.
"""

from app.core.config import settings
from app.modules.auth.rate_limit import InMemoryLoginRateLimiter

ticket_create_rate_limiter = InMemoryLoginRateLimiter(
    max_attempts=settings.support_ticket_create_rate_limit_max,
    window_seconds=settings.support_ticket_create_rate_limit_window_seconds,
)

assistant_ask_rate_limiter = InMemoryLoginRateLimiter(
    max_attempts=settings.support_assistant_rate_limit_max,
    window_seconds=settings.support_assistant_rate_limit_window_seconds,
)


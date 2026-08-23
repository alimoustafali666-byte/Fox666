"""Reuses the existing generic fixed-window limiter (see
app.modules.auth.rate_limit's documented single-instance-only
limitation, which applies identically here) rather than introducing
Redis solely for Step 18. Keyed by user_id -- every collaboration action
is made by an authenticated, already-tenant-resolved user.
"""

from app.core.config import settings
from app.modules.auth.rate_limit import InMemoryLoginRateLimiter

message_send_rate_limiter = InMemoryLoginRateLimiter(
    max_attempts=settings.collaboration_message_rate_limit_max,
    window_seconds=settings.collaboration_message_rate_limit_window_seconds,
)

ai_insights_rate_limiter = InMemoryLoginRateLimiter(
    max_attempts=settings.collaboration_ai_rate_limit_max,
    window_seconds=settings.collaboration_ai_rate_limit_window_seconds,
)


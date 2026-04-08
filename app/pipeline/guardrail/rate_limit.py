"""In-memory rate limiting per reporter email.

Simple sliding window counter. In production, use Redis for persistence
across workers/restarts.
"""

import time
from collections import defaultdict
from dataclasses import dataclass

# Max incidents per reporter per window
MAX_INCIDENTS_PER_HOUR = 10
WINDOW_SECONDS = 3600


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int | None


# In-memory store: email -> list of timestamps
_submissions: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(reporter_email: str) -> RateLimitResult:
    """Check if a reporter has exceeded their rate limit."""
    now = time.time()
    window_start = now - WINDOW_SECONDS

    # Clean old entries for this email
    timestamps = _submissions[reporter_email]
    active = [t for t in timestamps if t > window_start]
    if active:
        _submissions[reporter_email] = active
    else:
        _submissions.pop(reporter_email, None)  # reclaim memory for stale emails

    current = len(_submissions.get(reporter_email, []))

    if current >= MAX_INCIDENTS_PER_HOUR:
        oldest = min(_submissions[reporter_email])
        retry_after = int(oldest + WINDOW_SECONDS - now) + 1
        return RateLimitResult(
            allowed=False,
            current_count=current,
            limit=MAX_INCIDENTS_PER_HOUR,
            retry_after_seconds=max(retry_after, 1),
        )

    return RateLimitResult(
        allowed=True,
        current_count=current,
        limit=MAX_INCIDENTS_PER_HOUR,
        retry_after_seconds=None,
    )


def record_submission(reporter_email: str) -> None:
    """Record a successful submission for rate limiting."""
    _submissions[reporter_email].append(time.time())


def reset_limits() -> None:
    """Reset all rate limits (for testing)."""
    _submissions.clear()

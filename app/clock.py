"""Injectable clock for deterministic testing and historical as-of time-travel."""
from datetime import datetime, timezone
from typing import Optional

_mock_time: Optional[datetime] = None


def get_now() -> datetime:
    """Return the current time in UTC, or the injected mock time if set."""
    if _mock_time is not None:
        return _mock_time
    return datetime.now(timezone.utc)


def set_time(dt: datetime) -> None:
    """Inject a fixed time for testing. Ensures timezone is set to UTC."""
    global _mock_time
    if dt.tzinfo is None:
        _mock_time = dt.replace(tzinfo=timezone.utc)
    else:
        _mock_time = dt.astimezone(timezone.utc)


def reset_time() -> None:
    """Reset clock back to system real-time."""
    global _mock_time
    _mock_time = None

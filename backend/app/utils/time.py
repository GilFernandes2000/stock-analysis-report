"""UTC clock helper.

``datetime.utcnow()`` is deprecated (Python 3.12+). ``utcnow()`` returns the
same *naive* UTC datetime the rest of the codebase relies on when it compares
against SQLite ``DateTime`` columns (which have no timezone) and when it
serializes timestamps, but without the deprecation warning.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC now — a drop-in replacement for ``datetime.utcnow()``."""
    return datetime.now(UTC).replace(tzinfo=None)

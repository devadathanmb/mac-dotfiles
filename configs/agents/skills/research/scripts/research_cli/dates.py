"""Publication dates as search providers and pages state them."""

import re
from email.utils import parsedate_to_datetime

# An ISO date with an optional time and UTC offset: (date, time, offset).
TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2})"
    r"(?:[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?"
)


def iso_timestamp(value: object) -> str:
    """ISO date from an ISO or RFC 2822 timestamp, or "" when unrecognised.

    The time and UTC offset are kept when the source states them: a date alone
    can be a day off for a reader in another timezone.
    """
    text = str(value or "").strip()
    if match := TIMESTAMP.search(text):
        day, clock, zone = match.groups()
        # Midnight is how sources pad a date-only value; it is not a time.
        if not clock or not clock.strip("0:"):
            return day
        return f"{day}T{clock}{zone or ''}"
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return ""
    if not any((parsed.hour, parsed.minute, parsed.second)):
        return parsed.date().isoformat()
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")

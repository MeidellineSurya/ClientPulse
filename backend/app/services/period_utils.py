# Shared helper for defining "the current week" as a signal_snapshot period,
# consistent with the Monday-Sunday weeks used by backend/scripts/generate_seed.py.

from datetime import date, timedelta


def current_week_period() -> tuple[date, date]:
    # Monday of the current week through the following Sunday.
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end

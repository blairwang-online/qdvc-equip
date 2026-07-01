"""dates.py — purchase-date formatting and age display (GTK-free core).

The optional ``purchased`` asset-information field holds an ISO date
(``YYYY-MM-DD``). The Preview pane shows it as a locale-neutral, human-friendly
date followed by the asset's age:

    2026-07-01  ->  Wed 01 Jul 2026 (52d)
    2022-10-14  ->  Fri 14 Oct 2022 (3.7y)

Age rule: under one year is shown in whole days (``52d``); one year or more is
shown as years to one decimal place (``3.7y``). "One year" is defined as
365.25 days so leap years don't skew the boundary.

These helpers are pure Python (no GTK, no locale calls) so they can be
unit-tested deterministically by passing an explicit ``today``.
"""

import datetime

# Fixed English abbreviations so output doesn't depend on the host locale
# (matching the "Wed 01 Jul 2026" spec exactly).
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_DAYS_PER_YEAR = 365.25


def parse_iso_date(value):
    """Parse *value* as an ISO ``YYYY-MM-DD`` date, or return None.

    Tolerates surrounding whitespace and an optional time component (anything
    after the date is ignored). Returns a ``datetime.date`` or None if the
    leading token isn't a valid date.
    """
    if not value:
        return None
    token = str(value).strip().split()[0] if str(value).strip() else ""
    # Keep only the date part if a full timestamp was given.
    token = token.split("T")[0]
    try:
        return datetime.date(*(int(p) for p in token.split("-")[:3]))
    except (ValueError, TypeError):
        return None


def format_date(d):
    """Format a ``datetime.date`` as e.g. ``Wed 01 Jul 2026``."""
    return "%s %02d %s %04d" % (
        _WEEKDAYS[d.weekday()], d.day, _MONTHS[d.month], d.year)


def format_age(purchase_date, today=None):
    """Return the age string for *purchase_date*, e.g. ``52d`` or ``3.7y``.

    Under one year -> whole days with a ``d`` suffix; one year or more -> years
    to one decimal place with a ``y`` suffix. A future date yields ``0d``.
    *today* defaults to the real current date.
    """
    if today is None:
        today = datetime.date.today()
    days = (today - purchase_date).days
    if days < 0:
        days = 0
    if days < _DAYS_PER_YEAR:
        return "%dd" % days
    return "%.1fy" % (days / _DAYS_PER_YEAR)


def format_purchased(value, today=None):
    """Format a raw ``purchased`` value as ``<date> (<age>)``, or '' if unparsable.

    Example: ``"2026-07-01"`` -> ``"Wed 01 Jul 2026 (52d)"``. Returns '' when the
    value isn't a valid ISO date, so callers can fall back to showing it raw.
    """
    d = parse_iso_date(value)
    if d is None:
        return ""
    return "%s (%s)" % (format_date(d), format_age(d, today=today))

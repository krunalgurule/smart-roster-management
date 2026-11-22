
from calendar import monthrange
from datetime import date


def get_month_dates(year, month):
    total_days = monthrange(year, month)[1]

    return [
        date(year, month, day)
        for day in range(1, total_days + 1)
    ]


def is_operating(rule, current_date, holidays):
    mode = rule.calendar_mode

    if mode == "EVERY_DAY":
        return True

    if mode == "NO_PUBLIC_HOLIDAYS":
        return current_date not in holidays

    if mode == "NO_SUNDAYS_OR_HOLIDAYS":
        return (
            current_date.weekday() != 6
            and current_date not in holidays
        )

    raise ValueError(f"Unknown calendar mode: {mode}")


def is_employee_available(employee_id, current_date, availability):
    event = availability.get((employee_id, current_date))

    if not event:
        return True

    if not event.is_approved:
        return True

    return event.status not in {
        "LEAVE",
        "COMP_OFF",
        "UNAVAILABLE",
    }


def get_week_key(current_date):
    iso = current_date.isocalendar()

    return iso.year, iso.week

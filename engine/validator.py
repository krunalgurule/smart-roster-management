
from collections import Counter
from datetime import date

from sqlalchemy import select

from database.models import (
    Employee,
    Assignment,
    OperatingRule,
    PublicHoliday,
    WeeklyOff,
    EmployeeAvailability,
    RosterEntry,
)

from engine.constraints import (
    get_month_dates,
    get_week_key,
    is_operating,
)


def validate_roster(session, year, month, roster):
    """
    Validate a roster against current database rules.

    roster: list of dictionaries containing:
        employee_id
        brand_id
        process_id
        work_date

    Returns:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
        }
    """

    errors = []
    warnings = []

    employees = {
        employee.id: employee
        for employee in session.scalars(
            select(Employee).where(
                Employee.is_active.is_(True)
            )
        ).all()
    }

    valid_assignments = {
        (
            assignment.employee_id,
            assignment.brand_id,
            assignment.process_id,
        )
        for assignment in session.scalars(
            select(Assignment)
        ).all()
    }

    rules = session.scalars(
        select(OperatingRule)
    ).all()

    rule_map = {
        (rule.brand_id, rule.process_id): rule
        for rule in rules
    }

    holidays = {
        holiday.holiday_date
        for holiday in session.scalars(
            select(PublicHoliday)
        ).all()
    }

    weekly_offs = {
        (weekly_off.employee_id, weekly_off.weekday)
        for weekly_off in session.scalars(
            select(WeeklyOff)
        ).all()
    }

    availability = {
        (
            event.employee_id,
            event.availability_date,
        ): event
        for event in session.scalars(
            select(EmployeeAvailability)
        ).all()
    }

    coverage = Counter()
    employee_workdays = set()
    seen_assignments = set()

    month_dates = set(
        get_month_dates(year, month)
    )

    for entry in roster:

        eid = entry["employee_id"]
        bid = entry["brand_id"]
        pid = entry["process_id"]
        day = entry["work_date"]

        # 1. Check date belongs to selected month
        if day not in month_dates:
            errors.append(
                f"Assignment date {day} is outside "
                f"{year}-{month:02d}."
            )
            continue

        # 2. Detect duplicate assignments
        assignment_key = (
            eid,
            bid,
            pid,
            day,
        )

        if assignment_key in seen_assignments:
            errors.append(
                f"Duplicate assignment: Employee {eid}, "
                f"Brand {bid}, Process {pid}, Date {day}"
            )
            continue

        seen_assignments.add(assignment_key)

        # 3. Check active employee
        if eid not in employees:
            errors.append(
                f"Inactive or missing employee: {eid}"
            )
            continue

        # 4. Check employee eligibility
        if (eid, bid, pid) not in valid_assignments:
            errors.append(
                f"Invalid assignment: Employee {eid}, "
                f"Brand {bid}, Process {pid}, Date {day}"
            )

        # 5. Check operating rules
        rule = rule_map.get((bid, pid))

        if rule is None:
            errors.append(
                f"Missing operating rule: "
                f"Brand {bid}, Process {pid}"
            )
            continue

        if not is_operating(rule, day, holidays):
            errors.append(
                f"Non-operating day: "
                f"Brand {bid}, Process {pid}, Date {day}"
            )

        # 6. Check approved leave/unavailability
        event = availability.get((eid, day))

        if (
            event is not None
            and event.is_approved
            and event.status in {
                "LEAVE",
                "COMP_OFF",
                "UNAVAILABLE",
            }
        ):
            errors.append(
                f"Employee {eid} is unavailable "
                f"on {day}: {event.status}"
            )

        # 7. Check preferred weekly off
        if (eid, day.weekday()) in weekly_offs:
            warnings.append(
                f"Employee {eid} works on "
                f"preferred weekly off: {day}"
            )

        coverage[(bid, pid, day)] += 1
        employee_workdays.add((eid, day))

    # 8. Check weekly workday limits
    weekly_counts = Counter()

    for eid, day in employee_workdays:
        weekly_counts[
            (eid, get_week_key(day))
        ] += 1

    for (eid, week), count in weekly_counts.items():

        limit = employees[eid].max_workdays_per_week

        if count > limit:
            errors.append(
                f"Employee {eid} exceeds weekly limit: "
                f"{count}/{limit} days in week {week}"
            )

    # 9. Check minimum staffing coverage
    for rule in rules:

        for day in month_dates:

            if not is_operating(
                rule,
                day,
                holidays,
            ):
                continue

            actual = coverage[
                (
                    rule.brand_id,
                    rule.process_id,
                    day,
                )
            ]

            if actual < rule.min_staff:
                errors.append(
                    f"Coverage gap on {day}: "
                    f"Brand {rule.brand_id}, "
                    f"Process {rule.process_id}, "
                    f"Required {rule.min_staff}, "
                    f"Actual {actual}"
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_saved_roster(session, roster_run):
    """
    Load assignments belonging to a saved roster
    and validate them against current database rules.
    """

    entries = session.scalars(
        select(RosterEntry).where(
            RosterEntry.roster_run_id == roster_run.id
        )
    ).all()

    roster = [
        {
            "employee_id": entry.employee_id,
            "brand_id": entry.brand_id,
            "process_id": entry.process_id,
            "work_date": entry.work_date,
        }
        for entry in entries
    ]

    return validate_roster(
        session,
        roster_run.year,
        roster_run.month,
        roster,
    )

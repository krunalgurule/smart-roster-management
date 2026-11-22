
from sqlalchemy import select

from database.db import SessionLocal
from database.models import (
    RosterRun,
    RosterEntry,
    EmployeeAvailability,
)

from engine.validator import validate_saved_roster


with SessionLocal() as session:

    try:
        roster = session.scalar(
            select(RosterRun).where(
                RosterRun.year == 2026,
                RosterRun.month == 11,
                RosterRun.status == "PUBLISHED",
            )
        )

        if roster is None:
            raise RuntimeError("Published November roster not found.")

        entry = session.scalar(
            select(RosterEntry)
            .where(RosterEntry.roster_run_id == roster.id)
            .order_by(RosterEntry.id)
        )

        if entry is None:
            raise RuntimeError("Roster has no assignments.")

        print("===== BASELINE VALIDATION =====")

        baseline = validate_saved_roster(session, roster)

        print("Valid:", baseline["valid"])
        print("Errors:", len(baseline["errors"]))

        assert baseline["valid"], (
            "Baseline roster must pass before conflict test."
        )

        print("\n===== INJECT TEMPORARY LEAVE CONFLICT =====")

        existing = session.scalar(
            select(EmployeeAvailability).where(
                EmployeeAvailability.employee_id == entry.employee_id,
                EmployeeAvailability.availability_date == entry.work_date,
            )
        )

        if existing is None:
            session.add(
                EmployeeAvailability(
                    employee_id=entry.employee_id,
                    availability_date=entry.work_date,
                    status="LEAVE",
                    is_approved=True,
                    note="Temporary conflict detection test",
                )
            )
        else:
            existing.status = "LEAVE"
            existing.is_approved = True
            existing.note = "Temporary conflict detection test"

        session.flush()

        result = validate_saved_roster(session, roster)

        leave_errors = [
            error
            for error in result["errors"]
            if "unavailable" in error.lower()
        ]

        print("Valid:", result["valid"])
        print("Errors:", len(result["errors"]))

        assert not result["valid"], (
            "Roster should fail with approved leave conflict."
        )

        assert leave_errors, (
            "Expected employee unavailability conflict."
        )

        print("PASS: Leave conflict detected.")
        print("Detected:", leave_errors[0])

    finally:
        session.rollback()
        print("\nTemporary changes rolled back.")

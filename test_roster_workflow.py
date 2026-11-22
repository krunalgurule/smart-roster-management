
from datetime import date

from sqlalchemy import select

from database.db import SessionLocal
from database.models import RosterRun, RosterEntry

from engine.roster_manager import (
    approve_roster,
    publish_roster,
    reject_roster,
    RosterWorkflowError,
)


with SessionLocal() as session:

    try:

        print("\n===== TEST 1: INVALID ROSTER =====")

        # Create a temporary incomplete roster.
        invalid_roster = RosterRun(
            year=2035,
            month=12,
            status="DRAFT",
            notes="Temporary invalid roster test",
        )

        session.add(invalid_roster)
        session.flush()

        try:
            approve_roster(session, invalid_roster.id)

        except RosterWorkflowError as error:
            print("PASS: Invalid roster approval blocked.")
            print(str(error).splitlines()[0])

        else:
            raise AssertionError(
                "Invalid roster should not be approved."
            )

        assert invalid_roster.status == "DRAFT"

        print("\n===== TEST 2: VALID ROSTER =====")

        # Find an existing November 2026 roster.
        source_roster = session.scalar(
            select(RosterRun)
            .where(
                RosterRun.year == 2026,
                RosterRun.month == 11,
                RosterRun.status == "PUBLISHED",
            )
            .order_by(RosterRun.id.desc())
        )

        if source_roster is None:
            raise RuntimeError(
                "No published November 2026 roster found."
            )

        source_entries = session.scalars(
            select(RosterEntry).where(
                RosterEntry.roster_run_id == source_roster.id
            )
        ).all()

        if not source_entries:
            raise RuntimeError(
                "Published roster has no assignments."
            )

        # Copy the complete roster into a temporary draft.
        valid_roster = RosterRun(
            year=2026,
            month=11,
            status="DRAFT",
            notes="Temporary valid roster test",
        )

        session.add(valid_roster)
        session.flush()

        for entry in source_entries:

            session.add(
                RosterEntry(
                    roster_run_id=valid_roster.id,
                    employee_id=entry.employee_id,
                    brand_id=entry.brand_id,
                    process_id=entry.process_id,
                    work_date=entry.work_date,
                    status=entry.status,
                )
            )

        session.flush()

        print(
            "Copied assignments:",
            len(source_entries),
        )

        approve_roster(
            session,
            valid_roster.id,
        )

        assert valid_roster.status == "APPROVED"

        print("PASS: Valid roster approved.")

        # Publishing should be blocked because the
        # original published roster already exists.
        try:
            publish_roster(
                session,
                valid_roster.id,
            )

        except RosterWorkflowError:
            print(
                "PASS: Duplicate monthly publication blocked."
            )

        else:
            raise AssertionError(
                "Publishing a second roster should fail."
            )

        # Rejection of an approved roster should work.
        reject_roster(
            session,
            valid_roster.id,
        )

        assert valid_roster.status == "REJECTED"

        print("PASS: Approved roster rejected correctly.")

    finally:

        # Undo every temporary change, even if a test fails.
        session.rollback()

        print("\nTemporary test data rolled back.")

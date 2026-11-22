
from datetime import date

from sqlalchemy import select

from database.db import SessionLocal
from database.models import Employee, Brand, Process
from engine.leave_manager import record_availability
from engine.scheduler import generate_monthly_roster


test_date = date(2026, 11, 25)

with SessionLocal() as session:

    employee = session.scalar(
        select(Employee).where(
            Employee.employee_code == "DS021"
        )
    )

    brand = session.scalar(
        select(Brand).where(
            Brand.name == "Brand 21"
        )
    )

    process = session.scalar(
        select(Process).where(
            Process.code == "CS"
        )
    )

    if not employee or not brand or not process:
        raise RuntimeError("Required test records not found.")

    # Approve leave for Employee 21.
    record_availability(
        session=session,
        employee_id=employee.id,
        availability_date=test_date,
        status="LEAVE",
        note="Automatic backup allocation test",
        approved=True,
    )

    session.commit()

    # Generate a new roster without saving it.
    result = generate_monthly_roster(
        session=session,
        year=2026,
        month=11,
        save=False,
        time_limit_seconds=60,
    )

    print("\n===== LEAVE TEST RESULTS =====")
    print("Solver:", result["status"])
    print("Message:", result["message"])

    if result["status"] in ("OPTIMAL", "FEASIBLE"):

        replacements = [
            entry for entry in result["entries"]
            if entry["brand_id"] == brand.id
            and entry["process_id"] == process.id
            and entry["work_date"] == test_date
        ]

        print("\nBrand 21 CS coverage on:", test_date)

        for entry in replacements:
            replacement = session.get(
                Employee,
                entry["employee_id"]
            )
            print("Assigned employee:", replacement.employee_code)

        assert len(replacements) >= 1

        assert all(
            entry["employee_id"] != employee.id
            for entry in replacements
        )

        print("\nPASS: Approved leave was respected.")
        print("PASS: Customer Support coverage maintained.")

    else:
        print("\nScheduling errors:")
        for error in result["errors"]:
            print("-", error)

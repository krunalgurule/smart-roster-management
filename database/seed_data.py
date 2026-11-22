
from sqlalchemy import select

from database.db import Base, engine, SessionLocal
from database.models import (
    Pod, Employee, Brand, Process,
    Assignment, OperatingRule, WeeklyOff
)


PROCESS_DATA = [
    ("CS", "Customer Support"),
    ("ACC", "Abandoned Cart Conversions"),
    ("NDR", "Non-Delivery Report"),
]


def seed_database():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:

        if session.scalar(select(Employee.id).limit(1)):
            print("Database already contains employees.")
            return

        # 1. Create five operational pods
        pods = [
            Pod(name=f"Operations Pod {i}")
            for i in range(1, 6)
        ]

        session.add_all(pods)
        session.flush()

        # 2. Create processes
        processes = [
            Process(code=code, name=name)
            for code, name in PROCESS_DATA
        ]

        session.add_all(processes)
        session.flush()

        process_map = {p.code: p for p in processes}

        # 3. Create 30 employees
        employees = []

        for i in range(1, 31):
            pod = pods[(i - 1) // 6]

            employee = Employee(
                employee_code=f"DS{i:03d}",
                full_name=f"Employee {i:02d}",
                email=f"employee{i:02d}@example.com",
                pod_id=pod.id,
                max_workdays_per_week=6,
            )

            employees.append(employee)
            session.add(employee)

        session.flush()

        # 4. Create 25 brands
        brands = [
            Brand(
                name=f"Brand {i:02d}",
                description=f"Sample D2C client brand {i:02d}"
            )
            for i in range(1, 26)
        ]

        session.add_all(brands)
        session.flush()

        # 5. First 20 brands:
        # One employee handles all three processes.
        # These processes do not operate Sundays or public holidays.

        for i, brand in enumerate(brands[:20]):

            employee = employees[i]

            for code in ("CS", "ACC", "NDR"):

                session.add(
                    Assignment(
                        employee_id=employee.id,
                        brand_id=brand.id,
                        process_id=process_map[code].id,
                    )
                )

                session.add(
                    OperatingRule(
                        brand_id=brand.id,
                        process_id=process_map[code].id,
                        calendar_mode="NO_SUNDAYS_OR_HOLIDAYS",
                        min_staff=1,
                    )
                )

            # Sunday weekly off
            session.add(
                WeeklyOff(
                    employee_id=employee.id,
                    weekday=6,
                )
            )

        # 6. Last five brands:
        # Each brand has two employees.

        for i, brand in enumerate(brands[20:]):

            first = employees[20 + i * 2]
            second = employees[21 + i * 2]

            if i == 0:
                # Brand 21: Both employees can cover all processes.
                # CS operates 365 days a year.
                employee_assignments = [
                    (first, "CS"),
                    (first, "ACC"),
                    (first, "NDR"),
                    (second, "CS"),
                    (second, "ACC"),
                    (second, "NDR"),
                ]

                first_off = 0   # Monday
                second_off = 1  # Tuesday

            else:
                # Brands 22-25: Separate process responsibilities.
                employee_assignments = [
                    (first, "CS"),
                    (second, "ACC"),
                    (second, "NDR"),
                ]

                first_off = 6
                second_off = 6

            for employee, code in employee_assignments:

                session.add(
                    Assignment(
                        employee_id=employee.id,
                        brand_id=brand.id,
                        process_id=process_map[code].id,
                    )
                )

            # Operating rules
            for code in ("CS", "ACC", "NDR"):

                calendar_mode = (
                    "EVERY_DAY"
                    if i == 0 and code == "CS"
                    else "NO_SUNDAYS_OR_HOLIDAYS"
                )

                session.add(
                    OperatingRule(
                        brand_id=brand.id,
                        process_id=process_map[code].id,
                        calendar_mode=calendar_mode,
                        min_staff=1,
                    )
                )

            session.add_all([
                WeeklyOff(
                    employee_id=first.id,
                    weekday=first_off,
                ),
                WeeklyOff(
                    employee_id=second.id,
                    weekday=second_off,
                ),
            ])

        # 7. Assign pod leads
        for i, pod in enumerate(pods):
            pod.lead_employee_id = employees[i * 6].id

        session.commit()

        print("================================")
        print("DATABASE SEEDED SUCCESSFULLY")
        print("Employees: 30")
        print("Brands: 25")
        print("Pods: 5")
        print("Processes: 3")
        print("Single-resource brands: 20")
        print("Multi-resource brands: 5")
        print("365-day CS coverage: Brand 21")
        print("================================")


if __name__ == "__main__":
    seed_database()

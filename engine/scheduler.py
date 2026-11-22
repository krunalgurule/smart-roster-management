
from collections import defaultdict
from pyexpat import model

from ortools.sat.python import cp_model
from sqlalchemy import select

from database.models import (
    Employee,
    Assignment,
    OperatingRule,
    PublicHoliday,
    WeeklyOff,
    EmployeeAvailability,
    RosterRun,
    RosterEntry,
)

from engine.constraints import (
    get_month_dates,
    get_week_key,
    is_operating,
    is_employee_available,
)

from engine.validator import validate_roster


def generate_monthly_roster(
    session,
    year,
    month,
    time_limit_seconds=30,
    save=True,
):

    days = get_month_dates(year, month)

    employees = session.scalars(
        select(Employee).where(Employee.is_active.is_(True))
    ).all()

    assignments = session.scalars(select(Assignment)).all()
    rules = session.scalars(select(OperatingRule)).all()

    holidays = {
        h.holiday_date
        for h in session.scalars(select(PublicHoliday)).all()
    }

    weekly_offs = {
        (w.employee_id, w.weekday)
        for w in session.scalars(select(WeeklyOff)).all()
    }

    availability = {
        (a.employee_id, a.availability_date): a
        for a in session.scalars(select(EmployeeAvailability)).all()
    }

    if not employees:
        return {
            "status": "INFEASIBLE",
            "message": "No active employees found.",
            "entries": [],
            "errors": ["No active employees found."],
            "warnings": [],
        }

    employee_map = {e.id: e for e in employees}

    # Map employees to their assigned brand/process pairs.
    eligible_employees = defaultdict(list)

    for assignment in assignments:

        if assignment.employee_id in employee_map:

            eligible_employees[
                (assignment.brand_id, assignment.process_id)
            ].append(assignment.employee_id)

    model = cp_model.CpModel()

    work_vars = {}
    employee_day_vars = defaultdict(list)
    coverage_vars = defaultdict(list)

    impossible = []

    # Create assignment decision variables.
    for rule in rules:

        eligible_ids = set(
            eligible_employees[
                (rule.brand_id, rule.process_id)
            ]
        )

        for day in days:

            if not is_operating(rule, day, holidays):
                continue

            possible_ids = [
                eid for eid in eligible_ids
                if is_employee_available(eid, day, availability)
            ]

            if len(possible_ids) < rule.min_staff:

                impossible.append(
                    f"{day}: Brand {rule.brand_id}, "
                    f"process {rule.process_id} requires "
                    f"{rule.min_staff} employees but only "
                    f"{len(possible_ids)} are available."
                )

            for eid in possible_ids:

                key = (
                    eid,
                    rule.brand_id,
                    rule.process_id,
                    day,
                )

                variable = model.NewBoolVar(
                    f"employee_{eid}_brand_{rule.brand_id}_"
                    f"process_{rule.process_id}_{day}"
                )

                work_vars[key] = variable

                coverage_vars[
                    (rule.brand_id, rule.process_id, day)
                ].append(variable)

                employee_day_vars[(eid, day)].append(variable)

    # HARD CONSTRAINT 1:
    # Every operating process must meet minimum coverage.
    for rule in rules:

        for day in days:

            if not is_operating(rule, day, holidays):
                continue

            variables = coverage_vars[
                (rule.brand_id, rule.process_id, day)
            ]

            model.Add(sum(variables) >= rule.min_staff)

    # HARD CONSTRAINT 2:
    # Link process assignments to employee daily workload.
    employee_daily_work = {}

    for (eid, day), variables in employee_day_vars.items():

        daily_work = model.NewBoolVar(
            f"employee_{eid}_works_{day}"
        )

        model.Add(sum(variables) >= daily_work)

        model.Add(
            sum(variables) <= len(variables) * daily_work
        )

        employee_daily_work[(eid, day)] = daily_work

    # HARD CONSTRAINT 3:
    # Employee cannot exceed weekly working-day limit.
    weekly_buckets = defaultdict(list)

    for (eid, day), variable in employee_daily_work.items():

        weekly_buckets[
            (eid, get_week_key(day))
        ].append(variable)

    for (eid, week), variables in weekly_buckets.items():

        limit = employee_map[eid].max_workdays_per_week

        model.Add(sum(variables) <= limit)

    # SOFT CONSTRAINT:
    # Avoid employee's preferred weekly-off weekday.
    penalties = []

    for (eid, day), variable in employee_daily_work.items():

        if (eid, day.weekday()) in weekly_offs:

            penalties.append(100 * variable)

    # Minimise unnecessary assignments.

    # SOFT CONSTRAINT:
    # Balance monthly working days across employees.

    employee_monthly_loads = {}

    for employee in employees:

        daily_variables = [
            variable
            for (eid, day), variable in employee_daily_work.items()
            if eid == employee.id
        ]

        monthly_load = model.NewIntVar(
            0,
            len(days),
            f"monthly_load_{employee.id}"
        )

        model.Add(monthly_load == sum(daily_variables))

        employee_monthly_loads[employee.id] = monthly_load

    # Minimise the difference between the most
    # and least loaded employees.

    loads = list(employee_monthly_loads.values())

    maximum_load = model.NewIntVar(
        0, len(days), "maximum_monthly_load"
    )

    minimum_load = model.NewIntVar(
        0, len(days), "minimum_monthly_load"
    )

    model.AddMaxEquality(maximum_load, loads)
    model.AddMinEquality(minimum_load, loads)

    workload_imbalance = model.NewIntVar(
        0, len(days), "workload_imbalance"
    )

    model.Add(
        workload_imbalance == maximum_load - minimum_load
    )

    # Keep weekly-off preferences important.
    weekly_off_penalty = sum(penalties)

    # Minimise unnecessary process assignments.
    assignment_penalty = sum(work_vars.values())

    # Final optimisation objective.
    model.Minimize(
        weekly_off_penalty
        + assignment_penalty
        + 20 * workload_imbalance
    )

    solver = cp_model.CpSolver()

    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):

        errors = impossible or [
            "No valid roster satisfies all hard constraints. "
            "Review employee availability, weekly limits and coverage."
        ]

        return {
            "status": "INFEASIBLE",
            "message": "Unable to generate a valid roster.",
            "entries": [],
            "errors": errors,
            "warnings": [],
        }

    # Extract generated assignments.
    entries = []

    for key, variable in work_vars.items():

        if solver.BooleanValue(variable):

            eid, bid, pid, day = key

            entries.append({
                "employee_id": eid,
                "brand_id": bid,
                "process_id": pid,
                "work_date": day,
                "status": "WORK",
            })

    # Independent validation.
    validation = validate_roster(
        session,
        year,
        month,
        entries,
    )

    if not validation["valid"]:

        return {
            "status": "VALIDATION_FAILED",
            "message": "Post-generation validation failed.",
            "entries": entries,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    # Save only a validated draft.
    roster_run_id = None

    if save:

        run = RosterRun(
            year=year,
            month=month,
            status="DRAFT",
            notes="Generated using OR-Tools CP-SAT.",
        )

        session.add(run)
        session.flush()

        for item in entries:

            session.add(
                RosterEntry(
                    roster_run_id=run.id,
                    employee_id=item["employee_id"],
                    brand_id=item["brand_id"],
                    process_id=item["process_id"],
                    work_date=item["work_date"],
                    status=item["status"],
                )
            )

        session.commit()

        roster_run_id = run.id

    status_name = (
        "OPTIMAL"
        if status == cp_model.OPTIMAL
        else "FEASIBLE"
    )

    return {
        "status": status_name,
        "message": (
            f"Successfully generated {len(entries)} "
            f"employee-process assignments."
        ),
        "entries": entries,
        "errors": [],
        "warnings": validation["warnings"],
        "roster_run_id": roster_run_id,
    }

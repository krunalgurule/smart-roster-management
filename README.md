# Smart Roster Management System

An automated workforce scheduling and roster management application built using Python, Streamlit, SQLAlchemy, and Google OR-Tools.

The system generates optimized monthly employee rosters, manages employee leave and availability, detects scheduling conflicts, supports roster approval and publishing, and provides workforce analytics.

## Features

### 1. Automated Monthly Roster Generation
- Generate monthly employee schedules using OR-Tools CP-SAT.
- Allocate employees to eligible brands and processes.
- Respect approved leave and employee availability.
- Apply operating calendars and minimum staffing requirements.
- Enforce employee weekly workday limits.
- Export generated rosters as CSV files.

### 2. Leave and Availability Management
- Submit employee leave, compensatory-off, and unavailability requests.
- Approve or reject pending requests.
- Exclude unavailable employees from newly generated schedules.
- Allocate eligible backup employees while maintaining required coverage.

### 3. Roster Approval and Publishing
- Manage rosters through DRAFT, APPROVED, PUBLISHED, and REJECTED states.
- Validate rosters before approval and publication.
- Prevent multiple published rosters for the same month.
- Review saved roster assignments and export CSV files.

### 4. Roster Validation and Conflict Detection
- Detect assignments involving unavailable or inactive employees.
- Check employee eligibility for brands and processes.
- Detect duplicate assignments and out-of-month dates.
- Verify minimum staffing coverage.
- Check operating calendars and weekly workday limits.
- Report preferred weekly-off warnings.
- Export scheduling conflict reports.

### 5. Workforce Analytics Dashboard
- Employee workload analysis.
- Daily staffing trends.
- Brand assignment distribution.
- Process assignment distribution.
- Brand and process assignment matrix.
- Approved leave statistics.
- Interactive brand and process filters.
- Analytics CSV exports.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Web interface | Streamlit |
| Optimization engine | Google OR-Tools CP-SAT |
| Database ORM | SQLAlchemy |
| Local database | SQLite |
| Data analysis | Pandas |
| Visualizations | Streamlit charts |

## Project Structure

```text
smart-roster-management/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── database/
│   ├── db.py
│   ├── models.py
│   └── seed_data.py
├── engine/
│   ├── constraints.py
│   ├── leave_manager.py
│   ├── roster_manager.py
│   ├── scheduler.py
│   └── validator.py
├── test_leave.py
├── test_roster_workflow.py
└── test_conflict_detection.py
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/smart-roster-management.git
cd smart-roster-management
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Initialize the database

The application uses SQLAlchemy database models and includes a seed-data module.

Database initialization and seed-data commands should be confirmed against the implementations in `database/db.py` and `database/seed_data.py` before running a fresh installation.

### 5. Start the application

```bash
streamlit run app.py
```

Open the local URL displayed by Streamlit.

## Testing

The project includes scripts for verifying key scheduling and workflow functionality.

```bash
python test_leave.py
python test_roster_workflow.py
python test_conflict_detection.py
```

### Verified Development Test Results

- Python syntax checks passed.
- OR-Tools generated an optimal test roster containing 1,883 assignments.
- Approved leave was respected during roster generation.
- Required Customer Support coverage was maintained through backup allocation.
- Invalid empty-roster approval was blocked.
- Valid roster approval succeeded.
- Duplicate monthly publication was blocked.
- A temporary leave conflict was detected successfully.
- Temporary test changes were rolled back.
- Installed Python dependencies passed `pip check`.

These results describe the tested local development environment and seed dataset, not universal performance guarantees.

## Sample Dataset

The tested development dataset contains:

- 30 employees
- 25 brands
- 5 pods
- 3 processes
- 78 employee-process assignments

## Current Limitations

- The application does not yet implement user authentication or role-based access control.
- The local SQLite database is intended for development and demonstration.
- Persistent hosted deployment requires appropriate database configuration.
- The validator checks weekly workday limits within the selected roster month; cross-month weeks require additional handling.
- Analytics summarize roster assignments but do not replace scheduling validation.

## Future Enhancements

- Authentication and administrator permissions.
- Persistent hosted database support.
- Cross-month scheduling validation.
- Enhanced workforce utilization reports.
- Additional automated tests.
- Production monitoring and deployment hardening.

## Project Purpose

Developed as a workforce scheduling and optimization project for a DataStraw Tech internship assessment.

The project demonstrates Python application development, relational database modeling, constraint-based optimization, automated validation, and interactive analytics.
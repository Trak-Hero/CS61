# CS61

!! IMPORTANT NOTES TO TEAM

FRONTEND CONNECTION
- Frontend runs on port 8000.
- Backend runs on port 5001.
- frontend/app.py forwards /api/* requests to the backend.

REQUEST FORMAT
- The frontend currently sends X-Role and X-Student-Id.
- These headers are for local testing only and are NOT secure authentication.

DATABASE
- Uses the CS61_Project MySQL database.
- Connection configuration is handled in db.py.
- DONT hard-code database passwords in source files.

ACCESS CONTROL
- A student's dorm auto grants building access.
- Student_Access stores additional building permissions.
- Student accounts must be active to use student features.
- !!! The voting backend must enforce these same rules before
    accepting or updating votes.

VOTING WINDOWS
- Voting windows currently created manually by admins.
- Their start/end times determine when voting is allowed.
- !!!Recommendation calculation is triggered by the admin close endpoint, not auto at the scheduled end.
- !!!The voting backend must prevent submissions to closed windows and coordinate with recommendation calculation.

RECOMMENDATIONS
- Each voting window has 0 or 1 recommendation.
- Recommendations are stored as historical snapshots.
- The direction values are: warmer, colder, hold, no data.
- !!!Final recommendation thresholds need to be agreed on

DATA INTEGRITY TO RMB
- One vote per student per window (unique constraint).
- One temperature log per building per timestamp.
- Building temperature limits must satisfy min_temp < max_temp.
- Voting windows must satisfy start_time < end_time.
- Student dorm assignments must reference DORM buildings --> this validation belongs in student assignment operations.

SETUP (fresh database)
- mysql < database/schema.sql   (drops and rebuilds CS61_Project, wipes test data)
- mysql < database/seed.sql     (Trak's demo data: closed, open, ended and scheduled windows)
- cd backend && python app.py
- python test_voting.py         (41 checks, run on a freshly seeded DB)

TIME
- All DATETIMEs are stored and compared in UTC.

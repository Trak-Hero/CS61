SUMMARY

INCLUDED ENDPOINTS
1. Voting Windows
2. Voting
3. Recommendations and Results

!!! Registered through the Flask Blueprint (baila_bp) in app.py
!!! Reuses execute_handler, building_access and the validators from trak_routes.py
!!! All times are UTC, same as close_window
!!! Recommendations are computed by POST /api/admin/windows/<id>/close (Trak). These routes only read them.

Window status (same rule as GET /api/admin/windows)
    closed     a Recommendations row exists
    scheduled  now < start_time
    ended      now >= end_time, admin has not closed it yet
    open       otherwise

VOTING WINDOWS
--------------------
GET /api/buildings/<building_id>/windows/active
    - The open window for a building. 404 if none.
GET /api/windows/<window_id>
    - One window with its status. Caller needs access to its building.
GET /api/buildings/<building_id>/windows
    - Every window for a building, newest first, with status.

VOTING (student role + X-Student-Id required)
--------------------
GET /api/windows/<window_id>/my_vote
    - {"voted": true, "requested_temp": ...} or {"voted": false, "requested_temp": null}
POST /api/windows/<window_id>/vote     body {"requested_temp": 70.5}
    - 201 on success. 409 if already voted (use PUT).
PUT /api/windows/<window_id>/vote      body {"requested_temp": 71}
    - 200 on success. 404 if no vote yet (use POST).

Checks, in order, for POST and PUT
    401/403  not a student, or bad X-Student-Id
    400      body not JSON, requested_temp missing, not a number, more than 1 decimal
    404      student or window not found
    403      student inactive, or no access to the window's building
    409      window is scheduled, ended or closed
    400      requested_temp outside the building's min_temp to max_temp
The window row is locked (FOR UPDATE) during a vote. close_window locks the
same row, so a vote can never land after the recommendation is computed.

Database backstop: trg_votes_bi and trg_votes_bu repeat every check above.
A trigger rejection comes back as 409 with the trigger's message.

RECOMMENDATIONS AND RESULTS
--------------------
GET /api/buildings/<building_id>/recommendations/latest
    - Most recent snapshot for the building. 404 if none.
GET /api/windows/<window_id>/recommendation
    - Snapshot for one window. 404 with the window status if not closed yet.
GET /api/buildings/<building_id>/recommendations
    - All snapshots for the building, newest first.

TESTING
--------------------
mysql < database/schema.sql && mysql < database/seed.sql
cd backend && python app.py      (in another terminal)
python test_voting.py            (41 checks, needs a freshly seeded DB)

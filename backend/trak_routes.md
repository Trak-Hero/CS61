SUMMARY

INCLUDED ENDPOINTS
1. Building Data
2. Admin Endpoints
3. Simulated Temperature Logger

!!! Important notes: !!!
!!! registered through the Flask Blueprint (trak_bp)
!!! Database connections handled through db.py

BUILDING DATA (GET)
--------------------
GET /api/buildings
    - Returns buildings the student is authorized to access.
    - Access comes from their assigned dorm or Student_Access.
    - Admin/logger roles can view all buildings.

GET /api/buildings/<building_id>
    - Returns a specific building's information.
    - Includes building name, type, min_temp, and max_temp.
    - Checks whether the student can access that building.

GET /api/buildings/<building_id>/temperature
    - Returns the latest logged temperature for a building.
    - Reads from Temp_Logs, ordered by recorded_at.

GET /api/buildings/<building_id>/temperature/history
    - Returns historical temperature readings for a building.
    - Useful for displaying temperature trends or graphs.

ADMIN ENDPOINTS
--------------------
POST /api/admin/windows
    - Creates a new voting window for a building.
    - Requires building_id, start_time, and end_time.
    - Validates the building, time range, and overlapping windows.

POST /api/admin/windows/<window_id>/close
    - Closes a voting window and calculates its recommendation.
    - Gets votes from Votes and finds the median requested temp.
    - Compares the median with the latest logged temperature.
    - Saves a historical snapshot in Recommendations.
    - Prevents duplicate recommendations for the same window.

GET /api/admin/windows
    - Returns all voting windows and their statuses.
    - Includes recommendation information when available.

PATCH /api/admin/students/<student_id>
    - Activates or deactivates a student account.
    - Updates Students.is_active (1 = active, 0 = inactive).
    - Other backend routes must reject votes from inactive students.

POST /api/admin/buildings
    - Adds a new building to Buildings.
    - Requires building_name, building_type, min_temp, max_temp.
    - building_type must be DORM or PUBLIC.

PATCH /api/admin/buildings/<building_id>
    - Updates the allowed temperature range for a building.
    - Validates that min_temp is less than max_temp.


SIMULATED TEMP LOGGER
--------------------
POST /api/logger/temperatures
    - Inserts a simulated temperature reading into Temp_Logs.
    - Uses building_id to associate the reading with a building.
    - Accepts temperature_f and optional recorded_at.
    - Rejects invalid buildings and duplicate timestamps.
    - Currently triggered manually by the frontend/API;
      automatic periodic logging is not implemented.
"""

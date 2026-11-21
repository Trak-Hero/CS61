# Endpoints from my part (voting windows, voting, recommendations).
# Uses the same helpers + execute_handler as trak_routes so errors look the same.

"""PLEASE CHECK baila_routes.md for documentation of the endpoints and their expected behavior."""

from datetime import datetime, timezone

from flask import Blueprint

from trak_routes import (building_access, decimal_temp, error, execute_handler,
                         payload, respond, role_is, student_identity)

baila_bp = Blueprint("baila", __name__)

# note to team --> all times are UTC, same as close_window
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

# same status rule as GET /api/admin/windows so both views agree
WINDOW_SELECT = '''
    SELECT w.window_id, w.building_id, w.start_time, w.end_time,
        CASE WHEN r.window_id IS NOT NULL THEN 'closed'
            WHEN UTC_TIMESTAMP() < w.start_time THEN 'scheduled'
            WHEN UTC_TIMESTAMP() >= w.end_time THEN 'ended'
            ELSE 'open' END AS status
    FROM Voting_Windows w
    LEFT JOIN Recommendations r ON r.window_id = w.window_id
'''

REC_SELECT = '''
    SELECT r.window_id, w.building_id, w.start_time, w.end_time,
        r.vote_count, r.median_temp, r.logged_temp, r.direction, r.computed_at
    FROM Recommendations r
    JOIN Voting_Windows w ON w.window_id = r.window_id
'''

# CHECK ACCESS PORTION

# Load a window + check the caller can see its building.
def window_access(cur, window_id, lock=False):
    sql = WINDOW_SELECT + ' WHERE w.window_id = %s'
    if lock: sql += ' FOR UPDATE'
    cur.execute(sql, (window_id,))
    window = cur.fetchone()
    if not window: return None, error('Voting window not found', 404)
    _, failure = building_access(cur, window['building_id'])
    if failure is not None: return None, failure
    return window, None

def require_student():
    sid = student_identity()
    if sid is None:
        code = 401 if role_is('student') else 403
        return None, error('Only a student with an X-Student-Id can vote', code)
    return sid, None

# Shared checks for POST + PUT vote. Returns (sid, window, temp, failure)
def check_vote(cur, window_id):
    sid, failure = require_student()
    if failure is not None: return None, None, None, failure
    data = payload()
    if 'requested_temp' not in data: raise ValueError('requested_temp is required')
    temp = decimal_temp(data.get('requested_temp'), 'requested_temp')

    cur.execute('SELECT is_active FROM Students WHERE student_id = %s', (sid,))
    student = cur.fetchone()
    if not student: return None, None, None, error('Student not found', 404)
    if not student['is_active']:
        return None, None, None, error('Inactive students cannot vote', 403)

    # FOR UPDATE locks the window row. close_window locks the same row
    # so a vote and a close can never happen at the same time.
    window, failure = window_access(cur, window_id, lock=True)
    if failure is not None: return None, None, None, failure
    if window['status'] != 'open':
        return None, None, None, error(f"Voting window is {window['status']}, not open", 409)

    cur.execute('SELECT min_temp, max_temp FROM Buildings WHERE building_id = %s',
                (window['building_id'],))
    rng = cur.fetchone()
    if temp < rng['min_temp'] or temp > rng['max_temp']:
        raise ValueError(f"requested_temp must be between {rng['min_temp']} and {rng['max_temp']} for this building")
    return sid, window, temp, None


# VOTING WINDOWS

# GET ACTIVE WINDOW FOR A BUILDING
@baila_bp.get('/api/buildings/<int:building_id>/windows/active')
@execute_handler
def active_window(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    cur.execute('''
        SELECT w.window_id, w.building_id, w.start_time, w.end_time, 'open' AS status
        FROM Voting_Windows w
        WHERE w.building_id = %s
            AND w.start_time <= UTC_TIMESTAMP() AND w.end_time > UTC_TIMESTAMP()
            AND NOT EXISTS (SELECT 1 FROM Recommendations r WHERE r.window_id = w.window_id)
        ORDER BY w.start_time DESC LIMIT 1
    ''', (building_id,))
    window = cur.fetchone()
    return respond(window) if window else error('No open voting window for this building', 404)

# GET WINDOW BY ID
@baila_bp.get('/api/windows/<int:window_id>')
@execute_handler
def get_window(cur, conn, window_id):
    window, failure = window_access(cur, window_id)
    return failure if failure is not None else respond(window)

# LIST WINDOWS FOR A BUILDING
@baila_bp.get('/api/buildings/<int:building_id>/windows')
@execute_handler
def list_building_windows(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    cur.execute(WINDOW_SELECT + ' WHERE w.building_id = %s ORDER BY w.start_time DESC',
                (building_id,))
    return respond(cur.fetchall())


# VOTING

# GET MY VOTE IN A WINDOW
@baila_bp.get('/api/windows/<int:window_id>/my_vote')
@execute_handler
def my_vote(cur, conn, window_id):
    sid, failure = require_student()
    if failure is not None: return failure
    _, failure = window_access(cur, window_id)
    if failure is not None: return failure
    cur.execute('''
        SELECT vote_id, window_id, requested_temp, submitted_at
        FROM Votes WHERE student_id = %s AND window_id = %s
    ''', (sid, window_id))
    vote = cur.fetchone()
    # frontend treats requested_temp = null as "hasnt voted yet"
    if not vote: return respond({'window_id': window_id, 'voted': False, 'requested_temp': None})
    vote['voted'] = True
    return respond(vote)

# SUBMIT A NEW VOTE
@baila_bp.post('/api/windows/<int:window_id>/vote')
@execute_handler
def submit_vote(cur, conn, window_id):
    sid, window, temp, failure = check_vote(cur, window_id)
    if failure is not None:
        conn.rollback()
        return failure
    cur.execute('SELECT 1 FROM Votes WHERE student_id = %s AND window_id = %s', (sid, window_id))
    if cur.fetchone():
        conn.rollback()
        return error('You already voted in this window. Use PUT to change your vote', 409)
    now = utc_now()
    cur.execute('''
        INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
        VALUES (%s, %s, %s, %s)
    ''', (sid, window_id, temp, now))
    vote_id = cur.lastrowid
    conn.commit()
    return respond({'vote_id': vote_id, 'student_id': sid, 'window_id': window_id,
                    'requested_temp': temp, 'submitted_at': now}, 201)

# UPDATE MY VOTE (window still has to be open)
@baila_bp.put('/api/windows/<int:window_id>/vote')
@execute_handler
def update_vote(cur, conn, window_id):
    sid, window, temp, failure = check_vote(cur, window_id)
    if failure is not None:
        conn.rollback()
        return failure
    cur.execute('''
        SELECT vote_id, submitted_at FROM Votes
        WHERE student_id = %s AND window_id = %s FOR UPDATE
    ''', (sid, window_id))
    vote = cur.fetchone()
    if not vote:
        conn.rollback()
        return error('No vote to update. Use POST to submit one', 404)
    cur.execute('UPDATE Votes SET requested_temp = %s WHERE vote_id = %s',
                (temp, vote['vote_id']))
    conn.commit()
    return respond({'vote_id': vote['vote_id'], 'student_id': sid, 'window_id': window_id,
                    'requested_temp': temp, 'submitted_at': vote['submitted_at']})


# RECOMMENDATIONS AND RESULTS
# note to team --> these only READ. the calc happens in close_window (trak_routes)

# GET LATEST RECOMMENDATION FOR A BUILDING
@baila_bp.get('/api/buildings/<int:building_id>/recommendations/latest')
@execute_handler
def latest_recommendation(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    cur.execute(REC_SELECT + ' WHERE w.building_id = %s ORDER BY w.end_time DESC LIMIT 1',
                (building_id,))
    rec = cur.fetchone()
    return respond(rec) if rec else error('No recommendations for this building yet', 404)

# GET RECOMMENDATION FOR ONE WINDOW
@baila_bp.get('/api/windows/<int:window_id>/recommendation')
@execute_handler
def window_recommendation(cur, conn, window_id):
    window, failure = window_access(cur, window_id)
    if failure is not None: return failure
    cur.execute(REC_SELECT + ' WHERE r.window_id = %s', (window_id,))
    rec = cur.fetchone()
    if rec: return respond(rec)
    return error(f"No recommendation yet. Window is {window['status']}", 404)

# GET RECOMMENDATION HISTORY FOR A BUILDING
@baila_bp.get('/api/buildings/<int:building_id>/recommendations')
@execute_handler
def list_recommendations(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    cur.execute(REC_SELECT + ' WHERE w.building_id = %s ORDER BY w.end_time DESC',
                (building_id,))
    return respond(cur.fetchall())

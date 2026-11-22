# Endpoints from my part. 
# This is so we can separately work on the endpoints.

"""PLEASE CHECK trak_routes.md for documentation of the endpoints and their expected behavior."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from statistics import median
import re


from flask import Blueprint, jsonify, request
from mysql.connector import Error, IntegrityError

from db import get_connection

trak_bp = Blueprint("trak", __name__)

def jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value

def respond(obj, status=200):
    return jsonify(jsonable(obj)), status

def error(message, code=400):
    return jsonify({"error": message}), code

def payload():
    obj = request.get_json(silent=True)
    if not isinstance(obj, dict):
        raise ValueError('Expected a JSON object')
    return obj

def positive_id(value, field='id'):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9]\d*',str(value)):
        raise ValueError(f'{field} must be a positive integer')
    return int(value)

def decimal_temp(value, field='temperature_f'):
    if isinstance(value, bool) or value is None:
        raise ValueError(f'{field} must be a number')
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f'{field} must be a number') from None
    if not number.is_finite() or number < Decimal('-99.9') or number > Decimal('999.9'):
            raise ValueError(f'{field} must fit DECIMAL(4,1)')
    if number != number.quantize(Decimal('0.1')):
        raise ValueError(f'{field} may have at most 1 decimal place')
    return number

def parse_dt(value, field, *, optional=False):
    if value is None and optional:
        return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    if not isinstance(value, str):
        raise ValueError(f'{field} must be a datetime string')
    try:
        dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'{field} must be YYYY-MM-DD HH:MM:SS') from None
    # for demo: naive front-end datetime-local fields are interpreted literally, not converted
    # for team note: use a single timezone convention!!!
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0)

def role_is(*roles):
    # for classroom demo only. Browser user can freely impersonate roles.
    return request.headers.get('X-Role', '').lower() in roles

def require_role(*roles):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not role_is(*roles):
                return error('Role not permitted (classroom demo only)', 403)
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def student_identity():
    if not role_is('student'):
        return None
    try:
        return positive_id(request.headers.get('X-Student-Id'), 'X-Student-Id')
    except ValueError:
        return None
    
# ----------------------
# CHECK ACCESS PORTION
# ----------------------

# Check student access to a building.
def has_access(cur, student_id, building_id):
    cur.execute('''
        SELECT 1 FROM Students s
        WHERE s.student_id = %s AND s.is_active = 1
            AND (s.dorm_building_id = %s OR EXISTS (
            SELECT 1 FROM Student_Access a
            WHERE a.student_id = s.student_id AND a.building_id = %s
            ))
    ''', (student_id, building_id, building_id))
    return cur.fetchone() is not None


def building_access(cur, building_id):
    cur.execute('SELECT * FROM Buildings WHERE building_id = %s', (building_id,))
    building = cur.fetchone()
    if not building:
        return None, error('Building not found', 404)
    if role_is('admin', 'logger'):
        return building, None
    sid = student_identity()
    if sid is None:
        return None, error('Student ID required', 401)
    if not has_access(cur, sid, building_id):
        return None, error('Not authorized to access this building', 403)
    return building, None


## connection lifecycle and rollback on errors.
'''
def execute_handler(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        conn = None
        try:
            conn = get_connection()
            with conn.cursor(dictionary=True) as cur:
                result = fn(cur, conn, *args, **kwargs)
            return result
        except ValueError as exc:
            if conn: conn.rollback()
            return error(str(exc), 400)
        except IntegrityError as exc:
            if conn: conn.rollback()
            if exc.errno == 1062:
                return error('A record with these unique fields already exists', 409)
            if exc.errno in (1451, 1452):
                return error('Foreign key constraint violation', 400)
            if exc.errno == 3819:
                return error('CHECK constraint violation', 400)
            return error('Database integrity constraint violation', 400)
        except Error:
            if conn: conn.rollback()
            # note to team --> We will not expose raw database/credentials errors to API callers.
            return error('Database error. check backend terminal', 500)
        finally:
            if conn: conn.close()
    return wrapped
'''
# TEMP VERSION FOR DEBUGGING
def execute_handler(fn):
    """Centralize connection lifecycle and rollback on errors."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        conn = None
        try:
            conn = get_connection()
            with conn.cursor(dictionary=True, buffered=True) as cur:
                result = fn(cur, conn, *args, **kwargs)
            return result
        except ValueError as exc:
            if conn:
                conn.rollback()
            return error(str(exc), 400)
        except IntegrityError as exc:
            if conn:
                conn.rollback()
            print(f"MYSQL INTEGRITY ERROR: {exc}", flush=True)
            if exc.errno == 1062:
                return error(
                    'A record with these unique fields already exists', 409
                )
            if exc.errno in (1451, 1452):
                return error('Foreign key constraint violation', 400)
            if exc.errno == 3819:
                return error('CHECK constraint violation', 400)
            return error('Database integrity constraint violation', 400)
        except Error as exc:
            if conn:
                conn.rollback()
            # A trigger SIGNAL (errno 1644) is a business-rule rejection, not a crash.
            if exc.errno == 1644:
                return error(exc.msg, 409)
            import traceback
            print(f"MYSQL ERROR: {exc}", flush=True)
            traceback.print_exc()
            return error('Database error; check backend terminal', 500)
        finally:
            if conn:
                conn.close()
    return wrapped




# ------------------------------------------------------------------
# ------------------------------------------------------------------
# BUILDING DATA-----------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------

# GET: LIST BUILDINGS
@trak_bp.get('/api/buildings')
@execute_handler
def list_buildings(cur, conn):
    if role_is('admin', 'logger'):
        cur.execute('SELECT * FROM Buildings ORDER BY building_name')
    else:
        sid = student_identity()
        if sid is None:
            return error('Student ID required', 401)
        cur.execute('''
            SELECT b.*
            FROM Buildings b
            JOIN Students s ON s.student_id = %s
            WHERE s.is_active = 1
              AND (
                  b.building_id = s.dorm_building_id
                  OR EXISTS (
                      SELECT 1
                      FROM Student_Access sa
                      WHERE sa.student_id = s.student_id
                        AND sa.building_id = b.building_id
                  )
              )
            ORDER BY b.building_name
        ''', (sid,))
    return respond(cur.fetchall())
# GET BUILDING BY ID
@trak_bp.get('/api/buildings/<int:building_id>')
@execute_handler
def get_building(cur, conn, building_id):
    building, failure = building_access(cur, building_id)
    return failure if failure is not None else respond(building)

# GET BUILDING TEMPEARTURE BY BUILDING ID
@trak_bp.get('/api/buildings/<int:building_id>/temperature')
@execute_handler
def get_latest_temperature(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    cur.execute('''
        SELECT log_id, building_id, recorded_at, temperature_f
        FROM Temp_Logs WHERE building_id = %s
        ORDER BY recorded_at DESC, log_id DESC LIMIT 1
    ''', (building_id,))
    reading = cur.fetchone()
    return respond(reading) if reading else error('No temperature readings yet', 404)

# GET BUILDING TEMPERAUTRE HISTORY BY BUILDING ID
@trak_bp.get('/api/buildings/<int:building_id>/temperature/history')
@execute_handler
def get_temperature_history(cur, conn, building_id):
    _, failure = building_access(cur, building_id)
    if failure is not None: return failure
    limit_arg = request.args.get('limit', '100')
    limit = positive_id(limit_arg, 'limit')
    if limit > 500: raise ValueError('limit cannot exceed 500')
    cur.execute('''
        SELECT log_id, building_id, recorded_at, temperature_f
        FROM Temp_Logs WHERE building_id = %s
        ORDER BY recorded_at DESC, log_id DESC LIMIT %s
    ''', (building_id, limit))
    return respond(cur.fetchall())


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ADMIN ENDPOINTS-----------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------

# CREATE VOTING WINDOW
@trak_bp.post('/api/admin/windows')
@require_role('admin')
@execute_handler
def create_window(cur, conn):
    data = payload()
    bid = positive_id(data.get('building_id'), 'building_id')
    start = parse_dt(data.get('start_time'), 'start_time')
    end = parse_dt(data.get('end_time'), 'end_time')
    if start >= end: raise ValueError('start_time must be before end_time')
    cur.execute('SELECT building_id FROM Buildings WHERE building_id = %s FOR UPDATE', (bid,))
    if not cur.fetchone():
        return error('Building not found', 404)
    cur.execute('''
        SELECT window_id FROM Voting_Windows
        WHERE building_id = %s AND start_time < %s AND end_time > %s
        LIMIT 1
    ''', (bid, end, start))
    if cur.fetchone(): return error('Another voting window overlaps this period', 409)
    cur.execute('''
        INSERT INTO Voting_Windows (building_id, start_time, end_time)
        VALUES (%s, %s, %s)
    ''', (bid, start, end))
    wid = cur.lastrowid
    conn.commit()
    return respond({'window_id': wid, 'building_id': bid, 'start_time': start, 'end_time': end}, 201)

# LIST THE WINDOWS
@trak_bp.get('/api/admin/windows')
@require_role('admin')
@execute_handler
def list_windows(cur, conn):
    cur.execute('''
        SELECT w.*, r.window_id AS recommendation_id,
        CASE WHEN r.window_id IS NOT NULL THEN 'closed'
            WHEN UTC_TIMESTAMP() < w.start_time THEN 'scheduled'
            WHEN UTC_TIMESTAMP() >= w.end_time THEN 'ended'
            ELSE 'open' END AS status
        FROM Voting_Windows w
        LEFT JOIN Recommendations r ON r.window_id = w.window_id
        ORDER BY w.start_time DESC
    ''')
    return respond(cur.fetchall()) 

# CLOSE VOTING WINDOW
@trak_bp.post('/api/admin/windows/<int:window_id>/close')
@require_role('admin')
@execute_handler
def close_window(cur, conn, window_id):
    cur.execute('''
        SELECT * FROM Voting_Windows WHERE window_id = %s FOR UPDATE
    ''', (window_id,))
    window = cur.fetchone()
    if not window: return error('Voting window not found', 404)
    cur.execute('SELECT * FROM Recommendations WHERE window_id = %s', (window_id,))
    existing = cur.fetchone()
    if existing: return respond(existing)

    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    if now < window['start_time']:
        return error('Cannot close a window that has not started', 409)
    effective_end = min(window['end_time'], now)
    if effective_end < window['end_time']:
        cur.execute('UPDATE Voting_Windows SET end_time = %s WHERE window_id = %s',
                    (effective_end, window_id))
    # votes that were submitted after the window's final end do not count.
    cur.execute('''
        SELECT requested_temp FROM Votes
        WHERE window_id = %s AND submitted_at <= %s
        ORDER BY requested_temp
    ''', (window_id, effective_end))
    votes = [row['requested_temp'] for row in cur.fetchall()]
    count = len(votes)
    mid = Decimal(str(median(votes))).quantize(Decimal('0.1')) if votes else None
    cur.execute('''
        SELECT temperature_f FROM Temp_Logs
        WHERE building_id = %s AND recorded_at <= %s
        ORDER BY recorded_at DESC, log_id DESC LIMIT 1
    ''', (window['building_id'], effective_end))
    reading = cur.fetchone()
    current = reading['temperature_f'] if reading else None
    if mid is None or current is None:
        direction = 'no data'
    elif mid > current:
        direction = 'warmer'
    elif mid < current:
        direction = 'colder'
    else:
        direction = 'hold'
    cur.execute('''
        INSERT INTO Recommendations
           (window_id, vote_count, median_temp, logged_temp, direction, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (window_id, count, mid, current, direction, now))
    conn.commit()
    return respond({'window_id': window_id, 'vote_count': count,
                    'median_temp': mid, 'logged_temp': current,
                    'direction': direction, 'computed_at': now}, 201)


# SET STUDENT ACTIVE STATUS
@trak_bp.patch('/api/admin/students/<int:student_id>')
@require_role('admin')
@execute_handler
def set_student_active(cur, conn, student_id):
    data = payload()
    active = data.get('is_active')
    if not isinstance(active, bool): raise ValueError('is_active must be true or false')
    cur.execute('SELECT student_id FROM Students WHERE student_id = %s', (student_id,))
    if not cur.fetchone(): return error('Student not found', 404)
    cur.execute('UPDATE Students SET is_active = %s WHERE student_id = %s',
                (int(active), student_id))
    conn.commit()
    return respond({'student_id': student_id, 'is_active': active})

# CREATE NEW BUILDINGS
@trak_bp.post('/api/admin/buildings')
@require_role('admin')
@execute_handler
def create_building(cur, conn):
    data = payload()
    name = data.get('building_name')
    btype = data.get('building_type')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError('building_name must be between 1-120 characters')
    if btype not in ('DORM', 'PUBLIC'):
        raise ValueError('building_type must be DORM or PUBLIC')
    lower = decimal_temp(data.get('min_temp'), 'min_temp')
    upper = decimal_temp(data.get('max_temp'), 'max_temp')
    if lower >= upper: raise ValueError('min_temp must be less than max_temp')
    cur.execute('''
        INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
        VALUES (%s, %s, %s, %s)
    ''', (name.strip(), btype, lower, upper))
    bid = cur.lastrowid
    conn.commit()
    return respond({'building_id': bid, 'building_name': name.strip(),
                    'building_type': btype, 'min_temp': lower, 'max_temp': upper}, 201)

# EDIT BUILDINGS
@trak_bp.patch('/api/admin/buildings/<int:building_id>')
@require_role('admin')
@execute_handler
def edit_building(cur, conn, building_id):
    data = payload()
    if not {'min_temp', 'max_temp'} & set(data):
        raise ValueError('Provide min_temp and/or max_temp')
    cur.execute('SELECT * FROM Buildings WHERE building_id = %s FOR UPDATE', (building_id,))
    current = cur.fetchone()
    if not current: return error('Building not found', 404)
    lower = decimal_temp(data['min_temp'], 'min_temp') if 'min_temp' in data else current['min_temp']
    upper = decimal_temp(data['max_temp'], 'max_temp') if 'max_temp' in data else current['max_temp']
    if lower >= upper: raise ValueError('min_temp must be less than max_temp')
    cur.execute('''UPDATE Buildings SET min_temp = %s, max_temp = %s
                   WHERE building_id = %s''', (lower, upper, building_id))
    conn.commit()
    current.update({'min_temp': lower, 'max_temp': upper})
    return respond(current)


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# ADMIN ENDPOINTS-----------------------------------------------------
# ------------------------------------------------------------------
# ------------------------------------------------------------------

# INSERT A SIMULATED TEMPERATURE LOG
@trak_bp.post('/api/logger/temperatures')
@require_role('logger', 'admin')
@execute_handler
def insert_temperature(cur, conn):
    data = payload()
    bid = positive_id(data.get('building_id'), 'building_id')
    temp = decimal_temp(data.get('temperature_f'), 'temperature_f')
    recorded = parse_dt(data.get('recorded_at'), 'recorded_at', optional=True)
    cur.execute('SELECT building_id FROM Buildings WHERE building_id = %s', (bid,))
    if not cur.fetchone(): return error('Building not found', 404)
    cur.execute('''
        INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
        VALUES (%s, %s, %s)
    ''', (bid, recorded, temp))
    log_id = cur.lastrowid
    conn.commit()
    return respond({'log_id': log_id, 'building_id': bid,
                    'recorded_at': recorded, 'temperature_f': temp}, 201)

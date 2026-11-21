"""Checks the voting endpoints against a fresh schema.sql + Trak's seed.sql.
Run: reload the DB, start the backend on 5001, then python test_voting.py
Each line prints PASS or FAIL with the status and response.
"""
import json
import sys

import requests

BASE = 'http://localhost:5001/api'
fails = 0


def call(method, path, role='student', sid=None, body=None, raw=None):
    headers = {'Content-Type': 'application/json', 'X-Role': role}
    if sid is not None:
        headers['X-Student-Id'] = str(sid)
    data = raw if raw is not None else (json.dumps(body) if body is not None else None)
    r = requests.request(method, BASE + path, headers=headers, data=data, timeout=10)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def check(name, got, want_status, test=lambda b: True):
    global fails
    status, body = got
    ok = status == want_status and test(body)
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {status} {json.dumps(body)[:110]}")


# Trak's seed IDs (fresh DB):
#   buildings 1 North (dorm), 2 South (dorm, 65-75), 3 West (dorm), 4 Library, 5 Allen, 6 School House
#   students 1 trak, 2 jace, 3 baila (North), 4 phoom + 7 john (South), 5 james (West), 6 patrick inactive (South)
#   windows 1 North open, 2 South ended, 3 West closed, 4 Library scheduled, 5 Allen open
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
fmt = lambda d: d.strftime('%Y-%m-%d %H:%M:%S')

# admin opens a new South window so john can vote fresh (window 6)
check('admin opens South window', call('POST', '/admin/windows', role='admin',
      body={'building_id': 2, 'start_time': fmt(now - timedelta(minutes=1)),
            'end_time': fmt(now + timedelta(days=1))}), 201, lambda b: b['window_id'] == 6)

# Windows
check('active window, North', call('GET', '/buildings/1/windows/active', sid=1), 200, lambda b: b['window_id'] == 1)
check('no active window, Library', call('GET', '/buildings/4/windows/active', sid=1), 404)
check('window detail, West', call('GET', '/windows/3', sid=1), 200, lambda b: b['status'] == 'closed')
check('window list, North', call('GET', '/buildings/1/windows', sid=1), 200, lambda b: len(b) == 1)
check('window in building without access', call('GET', '/windows/2', sid=1), 403)
check('window missing', call('GET', '/windows/999', sid=1), 404)
check('no student id', call('GET', '/windows/1'), 401)

# My vote
check('my_vote before voting', call('GET', '/windows/6/my_vote', sid=7), 200, lambda b: b['voted'] is False)
check('my_vote after voting', call('GET', '/windows/1/my_vote', sid=1), 200, lambda b: b['requested_temp'] == 70.0)
check('my_vote as admin', call('GET', '/windows/1/my_vote', role='admin'), 403)

# Submit
check('valid vote', call('POST', '/windows/6/vote', sid=7, body={'requested_temp': 70.5}), 201)
check('duplicate POST', call('POST', '/windows/6/vote', sid=7, body={'requested_temp': 71}), 409)
check('update vote', call('PUT', '/windows/6/vote', sid=7, body={'requested_temp': 71}), 200, lambda b: b['requested_temp'] == 71.0)
check('PUT with no vote', call('PUT', '/windows/6/vote', sid=4, body={'requested_temp': 70}), 404)
check('above building max', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': 79}), 400)
check('below building min', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': 61}), 400)
check('two decimals', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': 70.25}), 400)
check('text temperature', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': 'warm'}), 400)
check('boolean temperature', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': True}), 400)
check('missing field', call('POST', '/windows/6/vote', sid=4, body={}), 400)
check('not JSON', call('POST', '/windows/6/vote', sid=4, raw='temp=70'), 400)
check('SQL injection text', call('POST', '/windows/6/vote', sid=4, body={'requested_temp': "70; DROP TABLE Votes;--"}), 400)
check('injection in student id', call('POST', '/windows/6/vote', sid="1 OR 1=1", body={'requested_temp': 70}), 401)
check('no access to building', call('POST', '/windows/1/vote', sid=7, body={'requested_temp': 70}), 403)
check('inactive student', call('POST', '/windows/6/vote', sid=6, body={'requested_temp': 70}), 403)
check('unknown student', call('POST', '/windows/6/vote', sid=999, body={'requested_temp': 70}), 404)
check('closed window', call('POST', '/windows/3/vote', sid=1, body={'requested_temp': 70}), 409)
check('ended window', call('POST', '/windows/2/vote', sid=4, body={'requested_temp': 70}), 409)
check('scheduled window', call('POST', '/windows/4/vote', sid=1, body={'requested_temp': 70}), 409)
check('admin cannot vote', call('POST', '/windows/6/vote', role='admin', body={'requested_temp': 70}), 403)

# Recommendations
check('latest rec, West', call('GET', '/buildings/3/recommendations/latest', sid=1), 200, lambda b: b['direction'] == 'warmer')
check('no rec yet, North', call('GET', '/buildings/1/recommendations/latest', sid=1), 404)
check('rec for window 3', call('GET', '/windows/3/recommendation', role='admin'), 200, lambda b: b['median_temp'] == 74.0)
check('rec history, West', call('GET', '/buildings/3/recommendations', sid=1), 200, lambda b: len(b) == 1)
check('rec for open window', call('GET', '/windows/1/recommendation', sid=1), 404)

# Close flow
check('admin closes ended South window', call('POST', '/admin/windows/2/close', role='admin'), 201,
      lambda b: b['vote_count'] == 2 and b['median_temp'] == 71.0)
check('admin closes window 6 early', call('POST', '/admin/windows/6/close', role='admin'), 201, lambda b: b['vote_count'] == 1)
check('vote after close', call('PUT', '/windows/6/vote', sid=7, body={'requested_temp': 72}), 409)
check('active window gone, South', call('GET', '/buildings/2/windows/active', sid=7), 404)
check('latest rec is window 6', call('GET', '/buildings/2/recommendations/latest', sid=7), 200, lambda b: b['window_id'] == 6)

print(f"\n{fails} failed")
sys.exit(1 if fails else 0)

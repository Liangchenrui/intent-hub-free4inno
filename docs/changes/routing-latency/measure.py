"""Run from repository root: python docs/changes/routing-latency/measure.py before|after."""
import json
import sqlite3
import sys
from pathlib import Path
from time import perf_counter
from datetime import datetime, timezone

import requests

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'intent-hub-backend'))
from intent_hub.config import Config

phase = sys.argv[1]
output = Path(__file__).parent / 'evidence' / (phase + '.json')
output.parent.mkdir(exist_ok=True)
records = []
login = requests.post('http://127.0.0.1:5000/compat/master/auth/login',
    json={'username': Config.DEFAULT_USERNAME, 'password': Config.DEFAULT_PASSWORD}, timeout=10)
login.raise_for_status()
auth_key = login.json()['api_key']
for index in range(3):
    started = perf_counter()
    response = requests.post('http://127.0.0.1:5000/compat/master/predict',
        json={'text': '我要出国参加学术会议'},
        headers={'Authorization': 'Bearer ' + auth_key}, timeout=90)
    rid = response.headers.get('X-Request-ID')
    with sqlite3.connect('file:' + str(root / 'intent-hub-backend/data/logs.sqlite3') + '?mode=ro', uri=True) as db:
        row = db.execute("select payload from records where kind='routing' and request_id=?", (rid,)).fetchone()
    records.append({'request_id': rid, 'http_status': response.status_code,
        'client_elapsed_ms': round((perf_counter() - started) * 1000, 3),
        'routing': json.loads(row[0]) if row else None})
    output.write_text(json.dumps({'phase': phase, 'measured_at': datetime.now(timezone.utc).isoformat(),
        'note': 'Same input and local service; three samples, not production p95.',
        'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(index + 1, response.status_code, rid, records[-1]['client_elapsed_ms'], flush=True)

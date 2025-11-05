import sys
import json
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.app import create_app


def pretty(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


def main():
    app = create_app('development')
    app.testing = True
    with app.app_context():
        client = app.test_client()

        print("[1] GET /api/v1/sync/status")
        resp = client.get('/api/v1/sync/status')
        print('Status:', resp.status_code)
        try:
            data = resp.get_json()
        except Exception:
            data = {'raw': resp.data.decode('utf-8', errors='ignore')}
        print('Body:', pretty(data))

        print("\n[2] POST /api/v1/sync/trigger {full:false, max_pages:1}")
        resp2 = client.post('/api/v1/sync/trigger', json={"full": False, "max_pages": 1})
        print('Status:', resp2.status_code)
        try:
            data2 = resp2.get_json()
        except Exception:
            data2 = {'raw': resp2.data.decode('utf-8', errors='ignore')}
        print('Body:', pretty(data2))

        # Small delay to allow metadata update
        time.sleep(1.0)

        print("\n[3] GET /api/v1/sync/status (after trigger)")
        resp3 = client.get('/api/v1/sync/status')
        print('Status:', resp3.status_code)
        try:
            data3 = resp3.get_json()
        except Exception:
            data3 = {'raw': resp3.data.decode('utf-8', errors='ignore')}
        print('Body:', pretty(data3))


if __name__ == '__main__':
    main()
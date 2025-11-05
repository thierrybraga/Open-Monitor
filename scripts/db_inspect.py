import json
import sys
from pathlib import Path
from sqlalchemy import inspect

# Ensure project root is on sys.path for 'app' imports
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db


def main():
    app = create_app('development')
    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        assets_cols = set()
        if 'assets' in tables:
            assets_cols = {c['name'] for c in insp.get_columns('assets')}

        info = {
            'database_uri': uri,
            'tables_count': len(tables),
            'has_users': 'users' in tables,
            'has_assets': 'assets' in tables,
            'has_vendor': 'vendor' in tables,
            'assets_has_vendor_id': 'vendor_id' in assets_cols,
            'sample_assets_columns': sorted(list(assets_cols))[:12],
        }
        print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
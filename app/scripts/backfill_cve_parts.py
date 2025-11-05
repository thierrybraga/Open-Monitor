import json
import argparse
from typing import Set

from app.app import create_app
from app.extensions.db import db
from app.models.vulnerability import Vulnerability
from app.models.cve_part import CVEPart


def extract_parts_from_configs(configs) -> Set[str]:
    parts_set: Set[str] = set()
    try:
        configs_list = json.loads(configs) if isinstance(configs, str) else (configs or [])
    except Exception:
        configs_list = []

    for config in configs_list or []:
        nodes = config.get('nodes', []) if isinstance(config, dict) else []
        for node in nodes:
            for cpe_match in node.get('cpeMatch', []) or []:
                cpe_uri = cpe_match.get('criteria', '')
                if isinstance(cpe_uri, str) and cpe_uri.startswith('cpe:2.3:'):
                    parts = cpe_uri.split(':')
                    if len(parts) > 2:
                        part_value = parts[2]
                        if part_value in {'a', 'o', 'h'}:
                            parts_set.add(part_value)
    return parts_set


def backfill(limit: int = None, commit_batch: int = 1000):
    app = create_app('development')
    with app.app_context():
        q = db.session.query(Vulnerability.cve_id, Vulnerability.nvd_cpe_configurations)
        q = q.filter(Vulnerability.nvd_cpe_configurations.isnot(None))
        if limit:
            q = q.limit(limit)
        # Stream rows to avoid high memory; SQLite doesn't support true server-side cursors.
        rows = q.all()

        to_insert = []
        processed = 0
        inserted = 0

        for cve_id, configs in rows:
            processed += 1
            parts = extract_parts_from_configs(configs)
            if not parts:
                continue

            # Skip if already has parts
            exists = db.session.query(CVEPart).filter(CVEPart.cve_id == cve_id).first()
            if exists:
                continue

            for part in parts:
                to_insert.append(CVEPart(cve_id=cve_id, part=part))

            if len(to_insert) >= commit_batch:
                db.session.bulk_save_objects(to_insert)
                db.session.commit()
                inserted += len(to_insert)
                to_insert.clear()
            if processed % 10000 == 0:
                print(f"Progress: processed={processed}, inserted_so_far={inserted}")

        if to_insert:
            db.session.bulk_save_objects(to_insert)
            db.session.commit()
            inserted += len(to_insert)

        print(f"Processed: {processed}, Inserted: {inserted}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill cve_parts from existing vulnerabilities')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of vulnerabilities to process')
    parser.add_argument('--batch', type=int, default=2000, help='Commit batch size for inserts')
    args = parser.parse_args()
    backfill(limit=args.limit, commit_batch=args.batch)
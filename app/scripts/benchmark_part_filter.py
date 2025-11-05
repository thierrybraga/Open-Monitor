import time
import json
import argparse
from typing import Set

from app.app import create_app
from app.extensions.db import db
from app.models.cve_part import CVEPart
from app.models.vulnerability import Vulnerability


def extract_cve_ids_by_part_from_json(part: str, limit: int = None) -> Set[str]:
    ids: Set[str] = set()
    q = db.session.query(Vulnerability.cve_id, Vulnerability.nvd_cpe_configurations)
    q = q.filter(Vulnerability.nvd_cpe_configurations.isnot(None))
    if limit:
        q = q.limit(limit)
    rows = q.all()
    for cve_id, configs in rows:
        try:
            configs_list = json.loads(configs) if isinstance(configs, str) else (configs or [])
        except Exception:
            configs_list = []
        found = False
        for config in configs_list or []:
            nodes = config.get('nodes', []) if isinstance(config, dict) else []
            for node in nodes:
                for cpe_match in node.get('cpeMatch', []) or []:
                    cpe_uri = cpe_match.get('criteria', '')
                    if isinstance(cpe_uri, str) and cpe_uri.startswith('cpe:2.3:'):
                        parts = cpe_uri.split(':')
                        if len(parts) > 2 and parts[2] == part:
                            ids.add(cve_id)
                            found = True
                            break
                if found:
                    break
            if found:
                break
    return ids


def extract_cve_ids_by_part_from_materialized(part: str) -> Set[str]:
    rows = db.session.query(CVEPart.cve_id).filter(CVEPart.part == part).all()
    return {r[0] for r in rows}


def main():
    parser = argparse.ArgumentParser(description='Benchmark vendor part filter performance')
    parser.add_argument('--part', type=str, default='a', choices=['a', 'o', 'h'])
    parser.add_argument('--limit', type=int, default=30000)
    args = parser.parse_args()

    app = create_app('development')
    with app.app_context():
        # Materialized table timing
        t0 = time.perf_counter()
        ids_materialized = extract_cve_ids_by_part_from_materialized(args.part)
        t1 = time.perf_counter()

        # JSON fallback timing (limited)
        t2 = time.perf_counter()
        ids_json = extract_cve_ids_by_part_from_json(args.part, limit=args.limit)
        t3 = time.perf_counter()

        print(f"Part={args.part}")
        print(f"Materialized: {len(ids_materialized)} CVEs in {t1 - t0:.2f}s")
        print(f"JSON fallback (limit={args.limit}): {len(ids_json)} CVEs in {t3 - t2:.2f}s")


if __name__ == '__main__':
    main()
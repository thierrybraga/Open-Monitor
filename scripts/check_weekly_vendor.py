import sys
from pathlib import Path
# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from datetime import datetime, timedelta

from app.app import create_app
from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.vendor import Vendor
from app.models.cve_vendor import CVEVendor
from app.models.cve_product import CVEProduct
from app.models.product import Product
from sqlalchemy import or_, union


def main():
    name_substr = sys.argv[1] if len(sys.argv) > 1 else 'microsoft'
    app = create_app()
    with app.app_context():
        session = db.session
        week_ago = datetime.now() - timedelta(days=7)

        vendors = session.query(Vendor).filter(Vendor.name.ilike(f"%{name_substr}%")).all()
        print(f"Searching vendors like '{name_substr}':", [(v.id, v.name) for v in vendors])
        if not vendors:
            print("No vendors matched.")
            return 0

        vid = vendors[0].id
        print(f"Using vendor id {vid} ({vendors[0].name})")

        cves_v = session.query(CVEVendor.cve_id.label('cve_id')).filter(CVEVendor.vendor_id.in_([vid]))
        cves_p = (
            session.query(CVEProduct.cve_id.label('cve_id'))
            .join(Product, Product.id == CVEProduct.product_id)
            .filter(Product.vendor_id.in_([vid]))
        )
        u = union(cves_v, cves_p).subquery()

        q = (
            session.query(Vulnerability)
            .filter(
                or_(
                    Vulnerability.published_date >= week_ago,
                    Vulnerability.last_update >= week_ago,
                )
            )
            .filter(Vulnerability.cve_id.in_(session.query(u.c.cve_id)))
            .distinct()
        )

        total = q.count()
        critical = q.filter(Vulnerability.base_severity == 'CRITICAL').count()
        high = q.filter(Vulnerability.base_severity == 'HIGH').count()
        medium = q.filter(Vulnerability.base_severity == 'MEDIUM').count()
        print("Union-filter weekly:", {"total": total, "critical": critical, "high": high, "medium": medium})

        # JSON fallback using vendor name
        vname_lower = vendors[0].name.strip().lower()
        weekly_candidates = (
            session.query(Vulnerability)
            .filter(
                or_(
                    Vulnerability.published_date >= week_ago,
                    Vulnerability.last_update >= week_ago,
                )
            )
            .all()
        )

        def parse_list_field(raw):
            import json
            try:
                if raw is None:
                    return []
                if isinstance(raw, list):
                    return [str(x) for x in raw]
                if isinstance(raw, dict):
                    if 'vendors' in raw and isinstance(raw['vendors'], list):
                        return [str(x) for x in raw['vendors']]
                    if 'items' in raw and isinstance(raw['items'], list):
                        return [str(x) for x in raw['items']]
                    return [str(raw)]
                if isinstance(raw, str):
                    s = raw.strip()
                    if not s:
                        return []
                    try:
                        obj = json.loads(s)
                        return parse_list_field(obj)
                    except Exception:
                        return [p.strip() for p in s.split(',') if p.strip()]
                return []
            except Exception:
                return []

        tot = crt = hig = med = 0
        for v in weekly_candidates:
            try:
                vnames = [str(x).strip().lower() for x in parse_list_field(v.nvd_vendors_data)]
                if vname_lower not in vnames:
                    continue
                tot += 1
                sev = (v.base_severity or '').upper()
                if sev == 'CRITICAL':
                    crt += 1
                elif sev == 'HIGH':
                    hig += 1
                elif sev == 'MEDIUM':
                    med += 1
            except Exception:
                continue
        print("JSON-fallback weekly:", {"total": tot, "critical": crt, "high": hig, "medium": med})

        return 0


if __name__ == '__main__':
    sys.exit(main())
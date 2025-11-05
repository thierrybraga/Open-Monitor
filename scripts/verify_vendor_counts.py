"""
Quick verification script to compare product counts by different join strategies.

Usage: python scripts/verify_vendor_counts.py <vendor_id>
Defaults to Cisco vendor_id=18 when not provided.
"""

import sys
import os
from sqlalchemy import text


def main():
    # Ensure project root is on sys.path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if root not in sys.path:
        sys.path.insert(0, root)
    # Import after fixing sys.path
    try:
        from app import create_app
    except Exception:
        from app.app import create_app
    from app.extensions import db
    vid = 18
    if len(sys.argv) > 1:
        try:
            vid = int(sys.argv[1])
        except Exception:
            pass

    app = create_app('development')
    with app.app_context():
        s = db.session
        q1 = text(
            """
            SELECT COUNT(DISTINCT cp.product_id)
            FROM cve_products cp
            JOIN cve_vendors cv ON cv.cve_id = cp.cve_id
            WHERE cv.vendor_id = :vid
            """
        )
        q2 = text(
            """
            SELECT COUNT(DISTINCT p.id)
            FROM product p
            WHERE p.vendor_id = :vid
            """
        )
        q3 = text(
            """
            SELECT COUNT(DISTINCT cp.product_id)
            FROM cve_products cp
            JOIN product p ON p.id = cp.product_id
            WHERE p.vendor_id = :vid
            """
        )
        q4 = text(
            """
            SELECT COUNT(DISTINCT cp.product_id)
            FROM cve_products cp
            JOIN cve_vendors cv ON cv.cve_id = cp.cve_id
            JOIN product p ON p.id = cp.product_id
            WHERE cv.vendor_id = :vid AND (p.vendor_id != :vid)
            """
        )
        q5 = text(
            """
            SELECT COUNT(DISTINCT ap.product_id)
            FROM affected_product ap
            JOIN product p ON p.id = ap.product_id
            WHERE p.vendor_id = :vid
            """
        )
        q6 = text(
            """
            SELECT COUNT(DISTINCT vr.product_id)
            FROM version_ref vr
            JOIN product p ON p.id = vr.product_id
            WHERE p.vendor_id = :vid
            """
        )

        res1 = s.execute(q1, {"vid": vid}).scalar() or 0
        res2 = s.execute(q2, {"vid": vid}).scalar() or 0
        res3 = s.execute(q3, {"vid": vid}).scalar() or 0
        res4 = s.execute(q4, {"vid": vid}).scalar() or 0
        try:
            res5 = s.execute(q5, {"vid": vid}).scalar() or 0
        except Exception:
            res5 = None
        res6 = s.execute(q6, {"vid": vid}).scalar() or 0

        print(f"Vendor {vid} verification:")
        print(f"- Distinct products via CVEProduct∩CVEVendor (cv.vendor_id={vid}): {res1}")
        print(f"- Distinct products with Product.vendor_id={vid}: {res2}")
        print(f"- Distinct CVEProduct where Product.vendor_id={vid}: {res3}")
        print(f"- Mismatched products (cv.vendor_id={vid} but Product.vendor_id!={vid}): {res4}")
        if res5 is not None:
            print(f"- Distinct AffectedProduct where Product.vendor_id={vid}: {res5}")
        print(f"- Distinct VersionReference where Product.vendor_id={vid}: {res6}")


if __name__ == "__main__":
    main()
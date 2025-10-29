import sqlite3, json, os
DB = os.path.join('app','instance','vulnerabilities.db')
print('DB exists:', os.path.exists(DB), DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
rows = cur.execute("SELECT cve_id, nvd_vendors_data FROM vulnerabilities WHERE nvd_vendors_data IS NOT NULL").fetchall()
count_contains = 0
count_exact = 0
vendors_set = set()
for cve_id, vjson in rows:
    vlist = []
    try:
        vlist = json.loads(vjson) if isinstance(vjson, str) else []
    except Exception:
        pass
    vlist = [str(v).lower() for v in (vlist or [])]
    if any('fortinet' in v for v in vlist):
        count_contains += 1
        vendors_set.update([v for v in vlist if 'fortinet' in v])
    if 'fortinet' in vlist:
        count_exact += 1
print("CVEs with vendor containing 'fortinet':", count_contains)
print("CVEs with vendor exactly 'fortinet':", count_exact)
print("Distinct vendor names containing 'fortinet':", sorted(vendors_set)[:50], " ... total", len(vendors_set))
try:
    rows2 = cur.execute("SELECT COUNT(DISTINCT cv.cve_id) FROM cve_vendors cv JOIN vendor v ON v.id=cv.vendor_id WHERE LOWER(v.name) LIKE '%fortinet%'").fetchone()
    print("CVEVendor count for vendors name like fortinet:", rows2[0])
    detail_rows = cur.execute("SELECT v.name, COUNT(DISTINCT cv.cve_id) FROM cve_vendors cv JOIN vendor v ON v.id=cv.vendor_id WHERE LOWER(v.name) LIKE '%fortinet%' GROUP BY v.name ORDER BY COUNT(DISTINCT cv.cve_id) DESC").fetchall()
    print("Per-vendor counts (LIKE '%fortinet%'):", detail_rows)
except Exception as e:
    print("CVEVendor query error:", e)
conn.close()
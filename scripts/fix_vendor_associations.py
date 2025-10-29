import sqlite3, json, os, sys

DB = os.path.join('app','instance','vulnerabilities.db')
vendor_key = sys.argv[1].lower() if len(sys.argv) > 1 else 'fortinet'

print('Using DB:', DB)
print('Target vendor key:', vendor_key)

conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')
cur = conn.cursor()

# Ensure vendor row exists and get vendor_id
row = cur.execute("SELECT id, name FROM vendor WHERE LOWER(name)=?", (vendor_key,)).fetchone()
if row is None:
    cur.execute("INSERT INTO vendor(name) VALUES (?)", (vendor_key,))
    vendor_id = cur.lastrowid
    print('Created vendor:', vendor_key, 'id=', vendor_id)
else:
    vendor_id = row[0]
    print('Found vendor id:', vendor_id)

before = cur.execute("SELECT COUNT(DISTINCT cve_id) FROM cve_vendors WHERE vendor_id=?", (vendor_id,)).fetchone()[0]
print('Associations before:', before)

rows = cur.execute("SELECT cve_id, nvd_vendors_data FROM vulnerabilities WHERE nvd_vendors_data IS NOT NULL").fetchall()
inserted = 0
for cve_id, vjson in rows:
    try:
        vlist = json.loads(vjson) if isinstance(vjson, str) else []
    except Exception:
        vlist = []
    if not vlist:
        continue
    vlist_low = [str(v).strip().lower() for v in vlist]
    if any(vendor_key in v for v in vlist_low):
        try:
            cur.execute("INSERT OR IGNORE INTO cve_vendors(cve_id, vendor_id) VALUES (?, ?)", (cve_id, vendor_id))
            if cur.rowcount:
                inserted += 1
        except Exception:
            # Ignore errors for malformed rows
            pass

conn.commit()
after = cur.execute("SELECT COUNT(DISTINCT cve_id) FROM cve_vendors WHERE vendor_id=?", (vendor_id,)).fetchone()[0]
print('Inserted associations:', inserted)
print('Associations after:', after)

conn.close()
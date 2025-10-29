import sqlite3, json, os
from collections import defaultdict

DB = os.path.join('app','instance','vulnerabilities.db')
print('Using DB:', DB)

conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')
cur = conn.cursor()

# Load existing vendors into a map: name_lower -> (id, name)
vendors_map = {}
for vid, vname in cur.execute("SELECT id, name FROM vendor").fetchall():
    key = (vname or '').strip().lower()
    if key:
        vendors_map[key] = (vid, vname)

# Helper to normalize vendor names extracted from JSON

def extract_vendor_names(vjson):
    names = []
    data = vjson
    if isinstance(vjson, str):
        try:
            data = json.loads(vjson)
        except Exception:
            data = vjson

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                val = item.get('name') or item.get('vendor') or item.get('vendor_name')
                if val:
                    names.append(val)
    elif isinstance(data, dict):
        if 'vendors' in data and isinstance(data['vendors'], list):
            for itm in data['vendors']:
                if isinstance(itm, str):
                    names.append(itm)
                elif isinstance(itm, dict):
                    val = itm.get('name') or itm.get('vendor') or itm.get('vendor_name')
                    if val:
                        names.append(val)
        elif 'name' in data:
            names.append(data['name'])
        else:
            # Fallback: consider dict keys as potential names
            for key in list(data.keys()):
                if isinstance(key, str):
                    names.append(key)
    elif isinstance(data, str):
        if data.strip():
            names.append(data.strip())

    # Normalize
    normed = []
    for n in names:
        if isinstance(n, str):
            s = n.strip().lower()
            if s:
                normed.append(s)
    return list(dict.fromkeys(normed))

# Discover all vendor names across vulnerabilities
print('Scanning vulnerabilities for vendor names...')
all_vendor_names = set()
rows = cur.execute("SELECT nvd_vendors_data FROM vulnerabilities WHERE nvd_vendors_data IS NOT NULL").fetchall()
for (vjson,) in rows:
    for n in extract_vendor_names(vjson):
        all_vendor_names.add(n)

print('Distinct vendor names found:', len(all_vendor_names))

# Ensure vendor rows exist
created_vendors = 0
for name in sorted(all_vendor_names):
    if name not in vendors_map:
        cur.execute("INSERT INTO vendor(name) VALUES (?)", (name,))
        vid = cur.lastrowid
        vendors_map[name] = (vid, name)
        created_vendors += 1

print('Created new vendor rows:', created_vendors)

# Backfill associations cve_vendors
print('Backfilling CVE↔Vendor associations...')
inserted_assocs = 0
batch = 0

# Preload existing associations to avoid redundant checks
existing_pairs = set()
for cve_id, vendor_id in cur.execute("SELECT cve_id, vendor_id FROM cve_vendors").fetchall():
    existing_pairs.add((cve_id, vendor_id))

rows = cur.execute("SELECT cve_id, nvd_vendors_data FROM vulnerabilities WHERE nvd_vendors_data IS NOT NULL").fetchall()
for cve_id, vjson in rows:
    vnames = extract_vendor_names(vjson)
    for vname in vnames:
        tup = vendors_map.get(vname)
        if not tup:
            # Should not happen, but guard: create vendor
            cur.execute("INSERT INTO vendor(name) VALUES (?)", (vname,))
            vid = cur.lastrowid
            vendors_map[vname] = (vid, vname)
        else:
            vid = tup[0]
        key = (cve_id, vid)
        if key in existing_pairs:
            continue
        try:
            cur.execute("INSERT OR IGNORE INTO cve_vendors(cve_id, vendor_id) VALUES (?, ?)", (cve_id, vid))
            if cur.rowcount:
                inserted_assocs += 1
                existing_pairs.add(key)
                batch += 1
                if batch >= 1000:
                    conn.commit()
                    batch = 0
        except Exception:
            # Ignore malformed rows or constraint issues
            pass

conn.commit()

# Final stats
total_vendors = cur.execute("SELECT COUNT(*) FROM vendor").fetchone()[0]
total_assocs = cur.execute("SELECT COUNT(*) FROM cve_vendors").fetchone()[0]
print('Inserted associations:', inserted_assocs)
print('Total vendors:', total_vendors)
print('Total cve_vendors:', total_assocs)

conn.close()
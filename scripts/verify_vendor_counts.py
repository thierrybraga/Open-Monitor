import sqlite3, json, os
from collections import defaultdict

DB = os.path.join('app','instance','vulnerabilities.db')
print('Using DB:', DB)

conn = sqlite3.connect(DB)
cur = conn.cursor()

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

# Build JSON counts per vendor
json_counts = defaultdict(int)
rows = cur.execute("SELECT cve_id, nvd_vendors_data FROM vulnerabilities WHERE nvd_vendors_data IS NOT NULL").fetchall()
for cve_id, vjson in rows:
    for n in extract_vendor_names(vjson):
        json_counts[n] += 1

# Build table counts per vendor
sql_counts = {}
for vid, vname in cur.execute("SELECT id, name FROM vendor").fetchall():
    name_key = (vname or '').strip().lower()
    if not name_key:
        continue
    count = cur.execute("SELECT COUNT(DISTINCT cve_id) FROM cve_vendors WHERE vendor_id=?", (vid,)).fetchone()[0]
    sql_counts[name_key] = count

# Compare and report mismatches
mismatches = []
for name, jcount in json_counts.items():
    tcount = sql_counts.get(name, 0)
    if jcount != tcount:
        mismatches.append((name, jcount, tcount))

mismatches.sort(key=lambda x: (x[1] - x[2]), reverse=True)
print('Total vendors with mismatched counts:', len(mismatches))
for name, jcount, tcount in mismatches[:50]:
    print(f"{name}: json={jcount} table={tcount} delta={jcount - tcount}")

# Quick summary
total_vendors = len(sql_counts)
complete = sum(1 for name, jcount in json_counts.items() if sql_counts.get(name, 0) == jcount)
print(f"Summary: vendors={total_vendors}, complete={complete}, coverage={complete}/{len(json_counts)}")

conn.close()
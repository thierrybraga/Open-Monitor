import re, urllib.request
URL = 'http://127.0.0.1:5002/vulnerabilities/vendors?q=Fortinet'
html = urllib.request.urlopen(URL).read().decode('utf-8', errors='ignore')
rows = re.findall(r'<tr[^>]*>.*?<label[^>]*>([^<]+)</label>.*?<span[^>]*>(\d+)</span>.*?</tr>', html, flags=re.DOTALL|re.IGNORECASE)
print('Found rows:', len(rows))
for name, count in rows:
    if 'fortinet' in name.lower():
        print('Vendor:', name.strip(), 'Count:', count)
        break
else:
    print('Fortinet row not found.')
import json
import urllib.request

URL = "http://127.0.0.1:5001/api/chat/sessions/5/messages"
payload = {"content": "Ping com gpt-5"}
data = json.dumps(payload).encode("utf-8")

req = urllib.request.Request(URL, data=data, headers={
    "Content-Type": "application/json"
}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        print(body)
except Exception as e:
    print(f"Request error: {e}")
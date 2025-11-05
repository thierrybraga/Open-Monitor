import requests
import re

def fetch_csrf(session, base_url):
    r = session.get(f"{base_url}/auth/login", timeout=10)
    print("Login page preview:\n", r.text[:500])
    r.raise_for_status()
    m = re.search(r"<input[^>]*name=[\'\"]csrf_token[\'\"][^>]*value=[\'\"]([^\'\"]+)[\'\"]", r.text, re.IGNORECASE)
    if not m:
        raise RuntimeError("CSRF token not found in login page")
    return m.group(1)

def try_login(base_url="http://localhost:8000", username="admin", password="admin@teste"):
    s = requests.Session()
    csrf = fetch_csrf(s, base_url)
    payload = {
        "csrf_token": csrf,
        "username": username,
        "password": password,
        "remember_me": "y",
        "submit": "Entrar",
    }
    r = s.post(f"{base_url}/auth/login", data=payload, allow_redirects=False, timeout=15)
    body = r.text
    invalid_msg = "Usuário ou senha inválidos" in body or "Usuário ou senha inválidos." in body
    return r.status_code, r.headers.get("Location"), invalid_msg, body[:1000]

if __name__ == "__main__":
    status, location, invalid, body_snippet = try_login()
    print("Status:", status)
    print("Location:", location)
    print("Invalid creds message:", invalid)
    print("Body snippet:\n", body_snippet)
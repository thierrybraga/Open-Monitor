import re
import sys
import requests


BASE_URL = "http://localhost:8000"


def fetch_csrf(session: requests.Session, base_url: str) -> str:
    r = session.get(f"{base_url}/auth/login", timeout=10)
    r.raise_for_status()
    m = re.search(r"<input[^>]*name=[\'\"]csrf_token[\'\"][^>]*value=[\'\"]([^\'\"]+)[\'\"]", r.text, re.IGNORECASE)
    if not m:
        raise RuntimeError("CSRF token not found on login page")
    return m.group(1)


def login(session: requests.Session, base_url: str, username: str, password: str) -> None:
    csrf = fetch_csrf(session, base_url)
    payload = {
        "csrf_token": csrf,
        "username": username,
        "password": password,
        "remember_me": "y",
        "submit": "Entrar",
    }
    r = session.post(f"{base_url}/auth/login", data=payload, allow_redirects=False, timeout=15)
    if r.status_code not in (302, 303):
        print("Login failed:", r.status_code)
        print(r.text[:500])
        sys.exit(1)


def set_language(session: requests.Session, base_url: str, language: str) -> None:
    payload = {"general": {"language": language}}
    r = session.post(f"{base_url}/api/v1/account/user-settings", json=payload, timeout=10)
    print("Set user-settings status:", r.status_code)
    print("Response:", r.text[:200])
    if r.status_code != 200:
        print("Failed to set language")
        sys.exit(1)


def verify_html(session: requests.Session, base_url: str) -> None:
    html = session.get(f"{base_url}/", timeout=10).text
    # Extract lines of interest
    lang_tag = re.search(r"<html[^>]*lang=\"([^\"]+)\"", html)
    og_locale = re.search(r"<meta\s+property=\"og:locale\"\s+content=\"([^\"]+)\"", html)
    in_lang = re.search(r"\"inLanguage\"\s*:\s*\"([^\"]+)\"", html)
    out_lines = [
        f"HTML lang: {lang_tag.group(1) if lang_tag else '(not found)'}",
        f"og:locale: {og_locale.group(1) if og_locale else '(not found)'}",
        f"inLanguage: {in_lang.group(1) if in_lang else '(not found)'}",
    ]
    print("\n".join(out_lines))
    with open("scripts/verify_i18n_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))


def main():
    username = "admin"
    password = "admin@teste"
    target_lang = "en-US"

    s = requests.Session()
    login(s, BASE_URL, username, password)
    set_language(s, BASE_URL, target_lang)
    try:
        verify_html(s, BASE_URL)
    except Exception as e:
        msg = f"Verification error: {type(e).__name__}: {e}"
        print(msg)
        with open("scripts/verify_i18n_output.txt", "w", encoding="utf-8") as f:
            f.write(msg)


if __name__ == "__main__":
    main()
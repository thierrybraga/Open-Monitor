import os
from werkzeug.serving import run_simple

try:
    # Prefer the factory from app.app
    from app.app import create_app
except Exception:
    # Fallback: try legacy main_startup if present
    from app.main_startup import create_app  # type: ignore


def _get_env() -> str:
    return os.getenv("FLASK_ENV") or "development"


def _get_bind_host() -> str:
    # Default to localhost; allow override to external bind
    return os.getenv("BIND_HOST", "127.0.0.1")


def _get_port() -> int:
    try:
        return int(os.getenv("PORT", "8000"))
    except ValueError:
        return 8000

def _get_use_reloader() -> bool:
    val = (os.getenv("USE_RELOADER", "false") or "false").strip().lower()
    return val in ("1", "true", "yes", "on")


app = create_app(_get_env())


if __name__ == "__main__":
    host = _get_bind_host()
    port = _get_port()
    use_reloader = _get_use_reloader()
    print(f"[WSGI] Servidor ouvindo em http://{host}:{port}/", flush=True)
    print(f"[WSGI] Reloader: {'ON' if use_reloader else 'OFF'}", flush=True)
    # Simple WSGI server using Werkzeug; suitable for local/dev usage
    run_simple(host, port, app, use_reloader=use_reloader, use_debugger=app.debug)
"""
Flask-Babel extension initialization with safe fallback.

Provides dynamic locale selection based on user session settings.
"""

from typing import Optional

try:
    from flask_babel import Babel
except Exception:
    # Safe fallback when Flask-Babel is not installed to avoid runtime crashes
    class Babel:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def init_app(self, app, locale_selector=None, timezone_selector=None):
            app.extensions = getattr(app, 'extensions', {})
            app.extensions['babel'] = self

from flask import session, current_app


babel = Babel()


def _normalize_lang(lang: Optional[str]) -> str:
    """Normalize language codes to expected formats.

    - Prefer BCP 47 with dash for HTML/JS (e.g., 'pt-BR', 'en-US')
    - Flask-Babel expects underscore for locales (e.g., 'pt_BR', 'en_US')
    """
    if not lang:
        return 'pt-BR'
    lang = str(lang).strip()
    # Map short codes to regional defaults
    if lang.lower() == 'pt':
        return 'pt-BR'
    if lang.lower() == 'en':
        return 'en-US'
    return lang


def _to_babel_locale(lang: str) -> str:
    """Convert BCP 47 (dash) to Babel locale (underscore)."""
    return lang.replace('-', '_')


def select_locale() -> str:
    """Determine current locale based on session or configuration."""
    try:
        settings = session.get('settings') or {}
        general = settings.get('general') or {}
        lang = _normalize_lang(general.get('language') or current_app.config.get('HTML_LANG', 'pt-BR'))
        return _to_babel_locale(lang)
    except Exception:
        return _to_babel_locale(current_app.config.get('HTML_LANG', 'pt-BR'))


def init_babel(app) -> None:
    """Initialize Babel with dynamic locale selection and defaults."""
    # Defaults if not provided
    app.config.setdefault('BABEL_DEFAULT_LOCALE', _to_babel_locale(app.config.get('HTML_LANG', 'pt-BR')))
    app.config.setdefault('BABEL_DEFAULT_TIMEZONE', app.config.get('TIMEZONE', 'UTC'))
    app.config.setdefault('SUPPORTED_LOCALES', ['en_US', 'pt_BR'])

    # Flask-Babel v3 supports passing selectors to init_app
    try:
        babel.init_app(app, locale_selector=select_locale)
    except TypeError:
        # Older versions may require decorator usage; at least attach instance
        babel.init_app(app)
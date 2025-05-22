# forms/__init__.py

"""
Package-wide import of all Flask-WTF forms.
So you can write e.g.:
    from forms import LoginForm, RegisterForm, AssetForm, VulnerabilityForm, ReportFilterForm
"""

# --- Authentication forms ---
from .auth_form import LoginForm, RegisterForm

# --- Asset management forms ---
try:
    from .asset_form import AssetForm
except ImportError:
    # If you haven’t created asset_form yet, this will silently skip it
    AssetForm = None

# --- Vulnerability forms ---
try:
    from .vulnerability_form import VulnerabilityForm
except ImportError:
    VulnerabilityForm = None

# --- Report generation forms ---
try:
    from .report_form import ReportFilterForm
except ImportError:
    ReportFilterForm = None

# --- (Add additional forms here as you create them) ---

__all__ = [
    'LoginForm',
    'RegisterForm',
    'AssetForm',
    'VulnerabilityForm',
    'ReportFilterForm',
]

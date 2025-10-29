# forms/__init__.py

"""
Package-wide import of all Flask-WTF forms.
So you can write e.g.:
    from forms import LoginForm, RegisterForm, AssetForm, VulnerabilityForm
"""

# --- Authentication forms ---
from app.forms.auth_form import LoginForm, RegisterForm

# --- Asset management forms ---
try:
    from forms.asset_form import AssetForm
except ImportError:
    # If you haven't created asset_form yet, this will silently skip it
    AssetForm = None

# --- Vulnerability forms ---
try:
    from forms.vulnerability_form import VulnerabilityForm
except ImportError:
    VulnerabilityForm = None



# --- Report forms ---
try:
    from forms.report_form import ReportConfigForm, ReportFilterForm, ReportExportForm, QuickReportForm
except ImportError:
    ReportConfigForm = None
    ReportFilterForm = None
    ReportExportForm = None
    QuickReportForm = None

# --- (Add additional forms here as you create them) ---

__all__ = [
    'LoginForm',
    'RegisterForm',
    'AssetForm',
    'VulnerabilityForm',
    'ReportConfigForm',
    'ReportFilterForm', 
    'ReportExportForm',
    'QuickReportForm',
]

"""
Blueprints and routes for the main application pages.

This module defines the main routes using a Flask Blueprint,
configures page metadata in a ROUTES dictionary, and provides
a helper function for rendering templates. Basic error handling is included.
"""

import logging
from datetime import datetime # Importado do original, pode ser útil
from typing import Any, Dict, Optional, List, Tuple

from flask import (
    Blueprint,
    render_template,
    abort,
    request,
    current_app,
    flash,
    redirect,
    url_for,
    jsonify
)

# Import necessary services or models for data fetching
from app.services.vulnerability_service import VulnerabilityService
from app.services.user_service import UserService
from app.models.vulnerability import Vulnerability
from app.models.user import User
from app.models.asset import Asset
from app.models.asset_vulnerability import AssetVulnerability
from app.models.enums import severity_levels
from app.forms.search_forms import SearchForm
from app.forms.newsletter_forms import NewsletterSubscriptionForm, NewsletterUnsubscribeForm
from app.forms.profile_form import ProfileForm, ChangePasswordForm
from app.extensions import db
from flask_login import login_required, current_user
# Local helper to avoid circular import with app.app

def wants_json() -> bool:
    return request.is_json or 'application/json' in request.accept_mimetypes.values()


# Configuração do logger para este módulo
logger = logging.getLogger(__name__)
# Nível do logger pode ser configurado centralmente na sua aplicação Flask


# Criação do Blueprint para as rotas principais
main_bp = Blueprint('main', __name__)

ROUTES: Dict[str, Dict[str, Any]] = {
    # Rotas Principais
    'index':      {'template': 'pages/index.html',               'label': 'Home',           'icon': 'house',             'path': '/',         'methods': ['GET']}, # path ajustado para '/' se for a homepage principal
    'monitoring': {'template': 'monitoring/monitoring.html', 'label': 'Monitoramento',  'icon': 'activity',          'path': '/monitoring','methods': ['GET']}, # <<-- AJUSTADO
    'analytics':  {'template': 'analytics/analytics.html',   'label': 'Analytics',      'icon': 'bar-chart',         'path': '/analytics', 'methods': ['GET']}, # <<-- AJUSTADO

    'account':    {'template': 'user/account.html',             'label': 'Account',        'icon': 'person-circle',     'path': '/account',   'methods': ['GET', 'POST']}, # Adicionado se existir

    # Rotas de Ferramentas/Funcionalidades
    'search':     {'template': 'pages/search.html',              'label': 'Search',         'icon': 'search',            'path': '/search',    'methods': ['GET', 'POST']},
    'newsletter': {'template': 'newsletter/newsletter.html', 'label': 'Newsletter',   'icon': 'newspaper',         'path': '/newsletter','methods': ['GET', 'POST']}, # <<-- AJUSTADO (assumindo newsletter/newsletter.html)
    'chat':       {'template': 'user/chat/chat.html',                'label': 'Chat',           'icon': 'chat-dots',         'path': '/chat',      'methods': ['GET']},
    'assets':     {'template': 'assets/asset_list.html',              'label': 'Assets',         'icon': 'server',            'path': '/assets',    'methods': ['GET']},
    'insights':   {'template': 'pages/insights.html',            'label': 'Insights',       'icon': 'lightbulb',         'path': '/insights',  'methods': ['GET']},
    'settings':   {'template': 'pages/settings.html',            'label': 'Settings',       'icon': 'gear',              'path': '/settings',  'methods': ['GET', 'POST']},

    # Rotas de Detalhes/Itens Específicos (Exemplo)
    # 'vulnerability_details': Removida - usar vulnerability_ui.vulnerability_details

    # Rotas de Erro (Não navegáveis diretamente, usadas pelos handlers)
    '400':        {'template': 'error/400.html',          'label': 'Bad Request',    'icon': 'x-circle',          'path': None,       'methods': None}, # <<-- AJUSTADO
    '404':        {'template': 'error/404.html',          'label': 'Page Not Found', 'icon': 'exclamation-triangle','path': None,       'methods': None}, # <<-- AJUSTADO
    '403':        {'template': 'error/403.html',          'label': 'Forbidden',      'icon': 'slash-circle',      'path': None,       'methods': None}, # Exemplo se tiver
    '500':        {'template': 'error/500.html',          'label': 'Server Error',   'icon': 'x-octagon',         'path': None,       'methods': None}, # <<-- AJUSTADO

}

# Definição de links de redes sociais para o footer - Exemplo
# Assumindo que a chave corresponde a uma classe de Bootstrap Icon (ex: 'twitter' -> 'bi-twitter')
SOCIAL_LINKS: Dict[str, str] = {
    'twitter': 'https://twitter.com/opencvereport',
    'github': 'https://github.com/opencvereport',
    'linkedin': 'https://www.linkedin.com/company/opencvereport',
    # Adicione outros links conforme necessário
}


def render_page(page_key: str, **context: Any) -> str:
    """
    Helper to render templates based on ROUTES configuration with basic context.

    Args:
        page_key: The key for the page in the ROUTES dictionary.
        **context: Additional context variables to pass to the template.

    Returns:
        The rendered template string.

    Raises:
        NotFound: If the page key is not found in ROUTES.
        InternalServerError: If template rendering fails.
    """
    cfg = ROUTES.get(page_key)
    if not cfg:
        logger.error(f"Configuration for page key '{page_key}' not found in ROUTES.")
        abort(404) # Usa abort(404) para chamar o handler de erro 404

    template_name = cfg.get('template')
    if not template_name:
         logger.error(f"Template name not specified for page key '{page_key}'.")
         abort(500, description=f"Template name missing for page key: {page_key}") # Usa abort(500) para chamar o handler 500

    # Adiciona variáveis de contexto padrão aqui (mantendo a estrutura simples)
    default_context: Dict[str, Any] = {
        'app_name': current_app.config.get('APP_NAME', 'Sec4all'),
        'current_year': datetime.now().year,
        'social_links': SOCIAL_LINKS, # Adiciona links sociais
        # TODO: Adicionar outras variáveis de contexto padrão aqui (e.g., nav_items, user info)
        # 'nav_items': [value for key, value in ROUTES.items()], # Exemplo simples: todas as rotas
        # 'current_route': page_key, # Útil para marcar item ativo na navegação
    }

    # Mescla contexto padrão e adicional
    merged_context = {**default_context, **context}


    try:
         return render_template(template_name, **merged_context)
    except Exception as e:
         # Captura exceções durante a renderização do template
         import traceback
         error_details = traceback.format_exc()
         logger.error(f"Error rendering template '{template_name}' for page '{page_key}': {e}", exc_info=True)
         logger.error(f"Full traceback: {error_details}")
         logger.error(f"Template context keys: {list(merged_context.keys())}")
         # Aborta com erro 500 para ser capturado pelo handler de erro 500
         abort(500, description=f"Error rendering template: {template_name} - {str(e)}")


# =============================================================================
# Definição das Rotas (Mantida a estrutura fornecida)
# =============================================================================
# As rotas são definidas explicitamente, usando o dicionário ROUTES para metadados.

@main_bp.route(ROUTES['index']['path'], methods=ROUTES['index']['methods'])
def index() -> str:
    """Renders the home page."""
    logger.info("Accessing index page.") # Logging mais informativo

    try:
        from app.extensions import db
        
        # Get database session and initialize service
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # Get dashboard counts
        counts = vuln_service.get_dashboard_counts()
        
        # Get weekly counts for new CVEs
        weekly_counts = vuln_service.get_weekly_counts()
        
        # Get pagination parameters
        page: int = request.args.get('page', 1, type=int)
        per_page: int = request.args.get('per_page', 10, type=int)  # Number of vulnerabilities per page
        
        # Get recent vulnerabilities with pagination
        vulnerabilities, total_count = vuln_service.get_recent_paginated(page, per_page)
        total_pages = (total_count + per_page - 1) // per_page  # Calculate total pages
        
        # No need to close session as it's managed by Flask-SQLAlchemy
        
        return render_page(
            'index', # Passa a chave da rota
            critical_count=counts.get('critical', 0),
            high_count=counts.get('high', 0),
            medium_count=counts.get('medium', 0),
            total_count=counts.get('total', 0),
            weekly_critical=weekly_counts.get('critical', 0),
            weekly_high=weekly_counts.get('high', 0),
            weekly_medium=weekly_counts.get('medium', 0),
            weekly_total=weekly_counts.get('total', 0),
            page=page,
            per_page=per_page,
            vulnerabilities=vulnerabilities,
            total_pages=total_pages,
        )
        
    except Exception as e:
        logger.error(f"Error loading index page data: {e}", exc_info=True)
        # Fallback to placeholder data if database query fails
        return render_page(
            'index',
            critical_count=0,
            high_count=0,
            medium_count=0,
            total_count=0,
            weekly_critical=0,
            weekly_high=0,
            weekly_medium=0,
            weekly_total=0,
            page=1,
            per_page=10,
            vulnerabilities=[],
            total_pages=1,
        )

@main_bp.route(ROUTES['search']['path'], methods=ROUTES['search']['methods'])
def search() -> str:
    """Renders the search page and processes the search form."""
    logger.info(f"Accessing search page with method: {request.method}") # Logging mais informativo

    query: str = request.args.get('q', '').strip() # Permite busca via GET (?q=...)

    if request.method == 'POST':
         query = request.form.get('q', '').strip()
         if query:
             # Padrão PRG (Post/Redirect/Get) para busca
             logger.info(f"Search form submitted, redirecting for query: '{query}'")
             return redirect(url_for('main.search', q=query))
         else:
             flash('Por favor, insira um termo de busca.', 'warning') # Uso de flash messages
             logger.debug("Search form submitted without query.")
             return render_page('search', query='')


    # Lógica para exibir resultados da busca (GET)
    search_results: List[Any] = [] # Placeholder
    total_results: int = 0 # Placeholder

    if query: # Só realiza a busca se houver um termo na URL (após GET ou redirecionamento)
        logger.info(f"Performing search for query: '{query}'")
        # TODO: Add logic to perform the search (from DB or service)
        # search_results = SearchService.search(query)
        # total_results = len(search_results) # Ou obtido do service

        # TODO: Implementar paginação para resultados da busca, se necessário


    return render_page(
        'search', # Passa a chave da rota
        query=query,
        search_results=search_results,
        total_results=total_results,
        # TODO: Passar variáveis de paginação, se aplicável
    )

@main_bp.route('/vulnerability_details.html', methods=['GET'])
def vulnerability_details_root_alias():
    """Alias para acessos a /vulnerability_details.html na raiz.
    Aceita 'cve'/'cve_id' ou 'severity' e redireciona para as rotas corretas.
    """
    cve_id = request.args.get('cve_id') or request.args.get('cve')
    if cve_id:
        return redirect(url_for('vulnerability_ui.vulnerability_details', cve_id=cve_id))
    severity = request.args.get('severity')
    if severity:
        severity_upper = severity.upper()
        if severity_upper in severity_levels.enums:
            return redirect(url_for('vulnerability_ui.vulnerability_details_by_severity', severity=severity_upper))
        flash(f'Severidade inválida: {severity}', 'warning')
    return redirect(url_for('vulnerability_ui.list_vulnerabilities_ui'))


@main_bp.route(ROUTES['newsletter']['path'], methods=ROUTES['newsletter']['methods'])
def newsletter() -> str:
    """Renders the newsletter page and processes the signup form."""
    logger.info(f"Accessing newsletter page with method: {request.method}")
    
    from app.services.newsletter_service import NewsletterService
    from app.services.email_service import EmailService
    from app.extensions import db
    
    form = NewsletterSubscriptionForm()
    newsletter_service = NewsletterService(db.session)
    email_service = EmailService()

    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data.strip().lower()
        preferences = form.preferences.data
        source = form.source.data
        
        logger.info(f"Newsletter signup attempt for email: '{email}'")
        
        try:
            # Check if email is already subscribed
            existing_subscriber = newsletter_service.get_subscriber_by_email(email)
            
            if existing_subscriber:
                if existing_subscriber.is_active:
                    flash(f"O email {email} já está inscrito na newsletter!", 'info')
                else:
                    # Reactivate subscription
                    newsletter_service.resubscribe(email)
                    flash(f"Bem-vindo de volta! Sua inscrição foi reativada para {email}.", 'success')
                    # Send welcome email
                    email_service.send_welcome_email(email)
            else:
                # Create new subscription
                success = newsletter_service.signup(email)
                if success:
                    flash(f"Obrigado por se inscrever na newsletter com {email}!", 'success')
                    # Send welcome email
                    email_service.send_welcome_email(email)
                    logger.info(f"Newsletter signup successful for {email}")
                else:
                    flash("Erro ao processar a inscrição. Tente novamente.", 'danger')
                    
        except ValueError as e:
            flash(f"Erro de validação: {str(e)}", 'danger')
            logger.error(f"Newsletter signup validation error for {email}: {e}")
        except Exception as e:
            flash(f"Erro ao processar a inscrição: {str(e)}", 'danger')
            logger.error(f"Newsletter signup failed for {email}: {e}")
            
        return redirect(url_for('main.newsletter'))
    
    elif request.method == 'POST':
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo {getattr(form, field).label.text}: {error}", 'danger')
        logger.debug("Newsletter form validation failed.")

    return render_template(
        ROUTES['newsletter']['template'],
        form=form
    )


@main_bp.route('/newsletter/unsubscribe', methods=['GET', 'POST'])
def newsletter_unsubscribe() -> str:
    """Handles newsletter unsubscription."""
    logger.info(f"Accessing newsletter unsubscribe page with method: {request.method}")
    
    from app.services.newsletter_service import NewsletterService
    from app.services.email_service import EmailService
    from app.extensions import db
    
    form = NewsletterUnsubscribeForm()
    newsletter_service = NewsletterService(db.session)
    email_service = EmailService()
    
    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data.strip().lower()
        
        logger.info(f"Newsletter unsubscribe attempt for email: '{email}'")
        
        try:
            existing_subscriber = newsletter_service.get_subscriber_by_email(email)
            
            if existing_subscriber and existing_subscriber.is_active:
                newsletter_service.unsubscribe(email)
                flash(f"Sua inscrição foi cancelada com sucesso para {email}.", 'success')
                # Send unsubscribe confirmation email
                email_service.send_unsubscribe_confirmation(email)
                logger.info(f"Newsletter unsubscribe successful for {email}")
            else:
                flash(f"O email {email} não está inscrito na newsletter.", 'info')
                
        except Exception as e:
            flash(f"Erro ao processar o cancelamento: {str(e)}", 'danger')
            logger.error(f"Newsletter unsubscribe failed for {email}: {e}")
            
        return redirect(url_for('main.newsletter_unsubscribe'))
    
    elif request.method == 'POST':
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo {getattr(form, field).label.text}: {error}", 'danger')
        logger.debug("Newsletter unsubscribe form validation failed.")
    
    return render_template('newsletter/unsubscribe.html', form=form)



@main_bp.route(ROUTES['analytics']['path'], methods=ROUTES['analytics']['methods'])
def analytics() -> str:
    """Renders the Analytics page quickly; metrics load via API."""
    logger.info("Accessing analytics page.")
    try:
        # Render without server-side heavy counts; frontend fetches overview asynchronously
        return render_page('analytics')
    except Exception as e:
        logger.error(f"Error rendering analytics page: {e}", exc_info=True)
        # Fallback to direct template render with minimal context
        return render_template('analytics/analytics.html')
    
    try:
        from app.extensions import db
        from app.models.vulnerability import Vulnerability
        from sqlalchemy import func, or_, text, desc
        from datetime import datetime, timedelta
        from flask_login import current_user
        from app.models.sync_metadata import SyncMetadata
        from app.models.cve_vendor import CVEVendor
        from app.models.cve_product import CVEProduct
        
        # Get database session and initialize service
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # Build base query and apply vendor preference filter if present
        selected_vendor_ids: List[int] = []
        try:
            if current_user.is_authenticated:
                key = f'user_vendor_preferences:{current_user.id}'
                pref = session.query(SyncMetadata).filter_by(key=key).first()
                if pref and pref.value:
                    selected_vendor_ids = [int(x) for x in pref.value.split(',') if x.strip().isdigit()]
        except Exception:
            selected_vendor_ids = []
        
        user_vulnerabilities = session.query(Vulnerability)
        if selected_vendor_ids:
            user_vulnerabilities = (
                user_vulnerabilities
                .join(CVEVendor, CVEVendor.cve_id == Vulnerability.cve_id)
                .filter(CVEVendor.vendor_id.in_(selected_vendor_ids))
                .distinct()
            )
        
        # Calculate counts for user's vulnerabilities (filtered if vendors selected)
        total_vulns = user_vulnerabilities.count()
        critical_vulns = user_vulnerabilities.filter(Vulnerability.base_severity == 'CRITICAL').count()
        high_vulns = user_vulnerabilities.filter(Vulnerability.base_severity == 'HIGH').count()
        medium_vulns = user_vulnerabilities.filter(Vulnerability.base_severity == 'MEDIUM').count()
        
        counts = {
            'total': total_vulns,
            'critical': critical_vulns,
            'high': high_vulns,
            'medium': medium_vulns
        }
        
        # Patched vs Unpatched - usando patch_available em base filtrada
        patched_cves = user_vulnerabilities.filter(Vulnerability.patch_available == True).count()
        unpatched_cves = user_vulnerabilities.filter(
            or_(
                Vulnerability.patch_available == False,
                Vulnerability.patch_available.is_(None)
            )
        ).count()
        
        # Active threats (exemplo: CVEs com cisa_exploit_add presentes)
        active_threats = user_vulnerabilities.filter(Vulnerability.cisa_exploit_add.isnot(None)).count()
        
        # Average CVSS
        avg_cvss_score = session.query(func.avg(Vulnerability.cvss_score)).select_from(user_vulnerabilities.subquery()).scalar() or 0.0
        avg_cvss_score = round(avg_cvss_score, 1)
        
        # Average exploit score (se houver campo/derivação)
        try:
            avg_exploit_score = session.query(func.avg(Vulnerability.cvss_score)).select_from(user_vulnerabilities.subquery()).scalar() or 0.0
            avg_exploit_score = round(avg_exploit_score, 1)
        except Exception:
            avg_exploit_score = 0.0
        
        # Patch coverage percentage
        patch_coverage = round((patched_cves / total_vulns * 100), 1) if total_vulns > 0 else 0.0
        
        # Count vendors/products considering preferences when present
        if selected_vendor_ids:
            vendor_count = len(selected_vendor_ids)
            try:
                product_count = session.query(func.count(func.distinct(CVEProduct.product_id)))\
                    .join(Vulnerability, Vulnerability.cve_id == CVEProduct.cve_id)\
                    .join(CVEVendor, CVEVendor.cve_id == Vulnerability.cve_id)\
                    .filter(CVEVendor.vendor_id.in_(selected_vendor_ids)).scalar() or 0
            except Exception:
                product_count = 0
        else:
            # Fallback original counts (sem filtro)
            from app.models.weakness import Weakness
            vendor_count = session.execute(text("""
                SELECT COUNT(DISTINCT vendor_data.value) as vendor_count
                FROM vulnerabilities vuln,
                     json_each(vuln.nvd_vendors_data) as vendor_data
                WHERE vuln.nvd_vendors_data IS NOT NULL 
                  AND vendor_data.value IS NOT NULL 
                  AND vendor_data.value != ''
            """)).scalar() or 0
            product_count = session.execute(text("""
                SELECT COUNT(DISTINCT product_data.value) as product_count
                FROM vulnerabilities vuln,
                     json_each(vuln.nvd_products_data) as product_data
                WHERE vuln.nvd_products_data IS NOT NULL 
                  AND product_data.value IS NOT NULL 
                  AND product_data.value != ''
            """)).scalar() or 0
            try:
                cwe_count = session.query(Weakness).count()
            except Exception:
                cwe_count = 0
        
        # Prepare analytics data
        analytics_data: Dict[str, Any] = {
            'total_cves': counts.get('total', 0),
            'critical_cves': counts.get('critical', 0),
            'high_cves': counts.get('high', 0),
            'medium_cves': counts.get('medium', 0),
            'severity_distribution': {
                'critical': counts.get('critical', 0),
                'high': counts.get('high', 0),
                'medium': counts.get('medium', 0)
            }
        }
        
        # No need to close session as it's managed by Flask-SQLAlchemy
        
        return render_page(
            'analytics',
            analytics_data=analytics_data,
            total_cves=counts.get('total', 0),
            critical_cves=counts.get('critical', 0),
            high_cves=counts.get('high', 0),
            medium_cves=counts.get('medium', 0),
            patched_cves=patched_cves,
            unpatched_cves=unpatched_cves,
            active_threats=active_threats,
            avg_cvss_score=avg_cvss_score,
            avg_exploit_score=avg_exploit_score,
            patch_coverage=patch_coverage,
            vendor_count=vendor_count,
            product_count=product_count,
            cwe_count=cwe_count if 'cwe_count' in locals() else 0
        )
        
    except Exception as e:
        logger.error(f"Error loading analytics page data: {e}", exc_info=True)
        # Fallback to placeholder data if database query fails
        analytics_data: Dict[str, Any] = {
            'total_cves': 0,
            'critical_cves': 0,
            'high_cves': 0,
            'medium_cves': 0,
            'severity_distribution': {'critical': 0, 'high': 0, 'medium': 0}
        }
        return render_page(
            'analytics',
            analytics_data=analytics_data,
            total_cves=0,
            critical_cves=0,
            high_cves=0,
            medium_cves=0,
            patched_cves=0,
            unpatched_cves=0,
            active_threats=0,
            avg_cvss_score=0.0,
            avg_exploit_score=0.0,
            patch_coverage=0.0,
            vendor_count=0,
            product_count=0,
            cwe_count=0
        )

@main_bp.route(ROUTES['assets']['path'], methods=ROUTES['assets']['methods'])
def assets() -> str:
    """Renders the Assets listing page."""
    logger.info("Accessing assets page.") # Logging mais informativo
    try:
        # Get assets data - filtrar por usuário atual
        from app.extensions.middleware import filter_by_user_assets
        assets_list = filter_by_user_assets(Asset.query).all()
        return render_page('assets', assets=assets_list)
    except Exception as e:
        logger.error(f"Error loading assets page: {e}", exc_info=True)
        flash('Erro ao carregar assets.', 'danger')
        return "Error: " + str(e)

@main_bp.route(ROUTES['insights']['path'], methods=ROUTES['insights']['methods'])
def insights() -> str:
    """Renders the Insights page."""
    logger.info("Accessing insights page.") # Logging mais informativo
    # TODO: Get insights data (e.g., from an InsightsService)
    insights_data: Dict[str, Any] = {} # Placeholder
    return render_page('insights', insights_data=insights_data)

# Exemplo na versão refatorada
@main_bp.route(ROUTES['monitoring']['path'], methods=ROUTES['monitoring']['methods'])
def monitoring() -> str:
    """Renders the Monitoring page."""
    logger.info("Accessing monitoring page.")
    return redirect(url_for('monitoring.monitoring_home'))


@main_bp.route(ROUTES['chat']['path'], methods=ROUTES['chat']['methods'])
def chat() -> str:
    """Renders the Chat page."""
    logger.info("Accessing chat page.")
    
    # Render the chat template
    return render_template(ROUTES['chat']['template'])

@main_bp.route('/chat-test', methods=['GET'])
def chat_test() -> str:
    """Renders the Chat test page without base template."""
    logger.info("Accessing chat test page.")
    
    # Render the chat test template
    return render_template('user/chat/chat-test.html')

# Removed duplicate route to avoid conflicts
# TODO: Add routes for Account, Vulnerability Details, etc., referencing ROUTES dictionary
# Example:
@main_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account() -> str:
    """
    Rota para a página da Conta do Usuário.

    Renders the account.html template e processa atualizações da conta.
    """
    logger.info(f"Accessing account page with method: {request.method}")
    
    # Inicializar formulários
    profile_form = ProfileForm()
    password_form = ChangePasswordForm()
    
    # Inicializar serviço de usuário
    user_service = UserService(db.session)
    
    try:
        # Carregar dados do usuário autenticado
        user_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'first_name': getattr(current_user, 'first_name', '') or '',
            'last_name': getattr(current_user, 'last_name', '') or '',
            'phone': getattr(current_user, 'phone', '') or '',
            'address': getattr(current_user, 'address', '') or '',
            'bio': getattr(current_user, 'bio', '') or '',
            'profile_picture': getattr(current_user, 'profile_picture', '') or ''
        }

        display_name = (user_data['first_name'] + ' ' + user_data['last_name']).strip()
        if not display_name:
            display_name = user_data['username']

        # Pré-preencher formulário com dados do usuário
        if request.method == 'GET':
            profile_form.first_name.data = user_data['first_name']
            profile_form.last_name.data = user_data['last_name']
            profile_form.email.data = user_data['email']
            profile_form.phone.data = user_data['phone']
            profile_form.address.data = user_data['address']
            profile_form.bio.data = user_data['bio']
        
        # Processar submissão do formulário de perfil
        if request.method == 'POST':
            form_type = request.form.get('form_type')
            
            if form_type == 'profile' and profile_form.validate_on_submit():
                try:
                    # Preparar dados para atualização
                    update_data = {
                        'first_name': profile_form.first_name.data,
                        'last_name': profile_form.last_name.data,
                        'email': profile_form.email.data,
                        'phone': profile_form.phone.data,
                        'address': profile_form.address.data,
                        'bio': profile_form.bio.data
                    }

                    # Atualizar dados do usuário no banco
                    user_service.update_user_data(current_user.id, update_data)
                    logger.info("Profile updated successfully")
                    if wants_json():
                        return jsonify({'success': True}), 200
                    flash('Perfil atualizado com sucesso!', 'success')
                    return redirect(url_for('main.account'))
                        
                except Exception as e:
                    logger.error(f"Error updating profile: {str(e)}")
                    if wants_json():
                        return jsonify({'success': False, 'message': 'Erro interno ao atualizar perfil.'}), 500
                    flash('Erro interno ao atualizar perfil.', 'error')
            
            elif form_type == 'password' and password_form.validate_on_submit():
                try:
                    # Simular alteração de senha
                    logger.info("Password changed successfully")
                    if wants_json():
                        return jsonify({'success': True}), 200
                    flash('Senha alterada com sucesso!', 'success')
                    return redirect(url_for('main.account'))
                        
                except Exception as e:
                    logger.error(f"Error changing password: {str(e)}")
                    if wants_json():
                        return jsonify({'success': False, 'message': 'Erro interno ao alterar senha.'}), 500
                    flash('Erro interno ao alterar senha.', 'error')
        
        # Dados para exibição
        return render_page(
            'account',
            user_account_data={**user_data, 'display_name': display_name},
            profile_form=profile_form,
            password_form=password_form
        )
        
    except Exception as e:
        logger.error(f"Error in account page: {str(e)}")
        flash('Erro ao carregar dados da conta.', 'error')
        return render_page(
            'account',
            user_account_data={},
            profile_form=ProfileForm(),
            password_form=ChangePasswordForm()
        )


# Rota removida - usar vulnerability_ui.vulnerability_details do vulnerability_controller
# para evitar conflito de rotas

# TODO: Adicionar outras rotas explicitamente aqui


# =============================================================================
# Handlers de Erro a Nível da Aplicação (Registrados via Blueprint)
# =============================================================================

# Usamos app_errorhandler para que esses handlers capturem erros que ocorram
# em qualquer lugar da aplicação, não apenas neste Blueprint.

@main_bp.app_errorhandler(404)
def page_not_found(error: Any) -> Tuple[str, int]:
    """
    Handler para erros 404 (Página Não Encontrada).

    Args:
        error: O objeto de erro.

    Returns:
        Uma tupla contendo a string renderizada do template 404 e o código de status 404.
    """
    # Registra o erro usando warning para 404
    logger.warning(f"Page not found: {request.url} - {error}")
    # Renderiza a página 404 usando a função render_page para manter o contexto básico
    # Passa a descrição do erro e o código para o template, se o template 404.html os usar
    return render_page('404.html', error=error, error_code=404), 404

@main_bp.app_errorhandler(500)
def internal_server_error(error: Any) -> Tuple[str, int]:
    """
    Handler para erros 500 (Erro Interno do Servidor).

    Args:
        error: O objeto de erro.

    Returns:
        Uma tupla contendo a string renderizada do template 500 e o código de status 500.
    """
    # Usa logger.exception para logar o traceback completo do erro original
    logger.exception(f"Internal server error: {request.url} - {error}")
    # Renderiza a página 500, passando o erro e o código para o template
    # Em produção, evite exibir detalhes sensíveis do erro.
    return render_page('500.html', error=error, error_code=500), 500

@main_bp.app_errorhandler(400)
def bad_request_error(error: Any) -> Tuple[str, int]:
    """
    Handler para erros 400 (Requisição Inválida).

    Args:
        error: O objeto de erro.

    Returns:
        Uma tupla contendo a string renderizada do template 400 e o código de status 400.
    """
    # Registra o erro usando warning para 400
    logger.warning(f"Bad request: {request.url} - {error}")
    # Renderiza a página 400, passando o erro e o código para o template
    return render_page('400', error=error, error_code=400), 400


# TODO: Adicionar handlers para outros erros comuns como 403 (Forbidden), 401 (Unauthorized), etc.
# Exemplo:
# @main_bp.app_errorhandler(403)
# def forbidden_error(error: Any) -> Tuple[str, int]:
#     logger.warning(f"Forbidden access: {request.url} - {error}")
#     return render_page('403.html', error=error, error_code=403), 403


# =============================================================================
# Rota de Teste para Debug
# =============================================================================

@main_bp.route('/test-debug-route')
def test_debug_route():
    """Rota de teste para verificar se o problema de redirecionamento é específico do blueprint de vulnerabilidades."""
    logger.info("Acessando rota de teste de debug")
    return """
    <html>
    <head><title>Teste de Debug</title></head>
    <body>
        <h1>Rota de Teste Funcionando</h1>
        <p>Esta rota está no main_controller e não deveria ter problemas de redirecionamento.</p>
        <p>Se você está vendo esta página, o problema é específico do blueprint de vulnerabilidades.</p>
    </body>
    </html>
    """

@main_bp.route(ROUTES['settings']['path'], methods=ROUTES['settings']['methods'])
def settings() -> str:
    """Renders the Settings page."""
    logger.info("Accessing settings page.")
    
    # TODO: Add settings logic here
    settings_data = {}
    
    return render_page('settings', settings_data=settings_data)


# TODO: Importar e registrar este Blueprint na sua aplicação Flask principal (ex: em app.py ou __init__.py)
# Exemplo:
# from utils.controllers.main_controller import main_bp
# app.register_blueprint(main_bp)

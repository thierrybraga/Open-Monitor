"""
Blueprints and routes for the main application pages.

This module defines the main routes using a Flask Blueprint,
configures page metadata in a ROUTES dictionary, and provides
a helper function for rendering templates. Basic error handling is included.
"""

import logging
from datetime import datetime # Importado do original, pode ser útil
import secrets # Importado do original, pode não ser usado diretamente
from typing import Any, Dict, Optional, List, Tuple

from flask import (
    Blueprint,
    render_template,
    abort,
    request,
    current_app,
    flash,
    redirect,
    url_for
)

# Import necessary services or models for data fetching
from services.vulnerability_service import VulnerabilityService
from services.user_service import UserService
from models.vulnerability import Vulnerability
from models.user import User
from models.asset import Asset
from models.asset_vulnerability import AssetVulnerability
from forms.search_forms import SearchForm
from forms.newsletter_forms import NewsletterSubscriptionForm, NewsletterUnsubscribeForm
from forms.profile_form import ProfileForm, ChangePasswordForm
from extensions import db
from flask_login import login_required, current_user


# Configuração do logger para este módulo
logger = logging.getLogger(__name__)
# Nível do logger pode ser configurado centralmente na sua aplicação Flask


# Criação do Blueprint para as rotas principais
main_bp = Blueprint('main', __name__)

ROUTES: Dict[str, Dict[str, Any]] = {
    # Rotas Principais
    'index':      {'template': 'index.html',               'label': 'Home',           'icon': 'house',             'path': '/',         'methods': ['GET']}, # path ajustado para '/' se for a homepage principal
    'monitoring': {'template': 'monitoring/monitoring.html', 'label': 'Monitoramento',  'icon': 'activity',          'path': '/monitoring','methods': ['GET']}, # <<-- AJUSTADO
    'analytics':  {'template': 'analytics/analytics.html',   'label': 'Analytics',      'icon': 'bar-chart',         'path': '/analytics', 'methods': ['GET']}, # <<-- AJUSTADO
    'reports':    {'template': 'reports/report.html',     'label': 'Reports',        'icon': 'file-earmark-text', 'path': '/reports',   'methods': ['GET']}, # <<-- AJUSTADO (assumindo reports/reports.html)
    'account':    {'template': 'account.html',             'label': 'Account',        'icon': 'person-circle',     'path': '/account',   'methods': ['GET', 'POST']}, # Adicionado se existir

    # Rotas de Ferramentas/Funcionalidades
    'search':     {'template': 'search.html',              'label': 'Search',         'icon': 'search',            'path': '/search',    'methods': ['GET', 'POST']},
    'chatbot':    {'template': 'chatbot/chatbot.html',     'label': 'Chatbot',        'icon': 'chat-dots',         'path': '/chatbot',   'methods': ['GET']}, # <<-- AJUSTADO
    'newsletter': {'template': 'newsletter/newsletter.html', 'label': 'Newsletter',   'icon': 'newspaper',         'path': '/newsletter','methods': ['GET', 'POST']}, # <<-- AJUSTADO (assumindo newsletter/newsletter.html)
    'assets':     {'template': 'assets.html',              'label': 'Assets',         'icon': 'server',            'path': '/assets',    'methods': ['GET']},
    'insights':   {'template': 'insights.html',            'label': 'Insights',       'icon': 'lightbulb',         'path': '/insights',  'methods': ['GET']},

    # Rotas de Detalhes/Itens Específicos (Exemplo)
    'vulnerability_details': {'template': 'vulnerability_details.html', 'label': 'Detalhes da Vulnerabilidade', 'icon': 'bug', 'path': '/vulnerabilities/<string:cve_id>', 'methods': ['GET']},

    # Rotas de Erro (Não navegáveis diretamente, usadas pelos handlers)
    '400':        {'template': 'errors/400.html',          'label': 'Bad Request',    'icon': 'x-circle',          'path': None,       'methods': None}, # <<-- AJUSTADO
    '404':        {'template': 'errors/404.html',          'label': 'Page Not Found', 'icon': 'exclamation-triangle','path': None,       'methods': None}, # <<-- AJUSTADO
    '403':        {'template': 'errors/403.html',          'label': 'Forbidden',      'icon': 'slash-circle',      'path': None,       'methods': None}, # Exemplo se tiver
    '500':        {'template': 'errors/500.html',          'label': 'Server Error',   'icon': 'x-octagon',         'path': None,       'methods': None}, # <<-- AJUSTADO

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
         logger.error(f"Error rendering template '{template_name}' for page '{page_key}': {e}", exc_info=True)
         # Aborta com erro 500 para ser capturado pelo handler de erro 500
         abort(500, description=f"Error rendering template: {template_name}")


# =============================================================================
# Definição das Rotas (Mantida a estrutura fornecida)
# =============================================================================
# As rotas são definidas explicitamente, usando o dicionário ROUTES para metadados.

@main_bp.route(ROUTES['index']['path'], methods=ROUTES['index']['methods'])
def index() -> str:
    """Renders the home page."""
    logger.info("Accessing index page.") # Logging mais informativo

    try:
        from extensions import db
        
        # Get database session and initialize service
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # Get dashboard counts
        counts = vuln_service.get_dashboard_counts()
        
        # Get weekly counts for new CVEs
        weekly_counts = vuln_service.get_weekly_counts()
        
        # Get pagination parameters
        page: int = request.args.get('page', 1, type=int)
        per_page: int = 10  # Number of vulnerabilities per page
        
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


@main_bp.route(ROUTES['newsletter']['path'], methods=ROUTES['newsletter']['methods'])
def newsletter() -> str:
    """Renders the newsletter page and processes the signup form."""
    logger.info(f"Accessing newsletter page with method: {request.method}")
    
    from services.newsletter_service import NewsletterService
    from services.email_service import EmailService
    from extensions.db import db
    
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
    
    from services.newsletter_service import NewsletterService
    from services.email_service import EmailService
    from extensions.db import db
    
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

@main_bp.route(ROUTES['chatbot']['path'], methods=ROUTES['chatbot']['methods'])
def chatbot() -> str:
    """Renders the Chatbot page."""
    logger.info("Accessing chatbot page.") # Logging mais informativo
    # TODO: Get any initial data needed for the chatbot.html template
    return render_page('chatbot')

@main_bp.route(ROUTES['analytics']['path'], methods=ROUTES['analytics']['methods'])
@login_required
def analytics() -> str:
    """Renders the Analytics page."""
    logger.info("Accessing analytics page.") # Logging mais informativo
    
    try:
        from extensions import db
        from models.vulnerability import Vulnerability
        from sqlalchemy import func, or_
        from datetime import datetime, timedelta
        
        # Get database session and initialize service
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # Get dashboard counts for analytics - filtered by user's assets
        user_vulnerabilities = session.query(Vulnerability).join(
            AssetVulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id
        ).join(
            Asset, AssetVulnerability.asset_id == Asset.id
        ).filter(
            Asset.owner_id == current_user.id
        )
        
        # Calculate counts for user's vulnerabilities
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
        
        # Calculate additional analytics data
        # Patched vs Unpatched - usando lógica mais realista
        # Consideramos "patched" CVEs mais antigos (>90 dias) com severidade baixa/média
        # e "unpatched" CVEs recentes ou críticos/altos
        old_date = datetime.now() - timedelta(days=90)
        
        # CVEs considerados "patched" (mais antigos e menos críticos) - filtered by user
        patched_cves = user_vulnerabilities.filter(
            Vulnerability.published_date < old_date,
            Vulnerability.base_severity.in_(['LOW', 'MEDIUM'])
        ).count()
        
        # CVEs considerados "unpatched" (recentes ou críticos/altos) - filtered by user
        unpatched_cves = user_vulnerabilities.filter(
            or_(
                Vulnerability.published_date >= old_date,
                Vulnerability.base_severity.in_(['CRITICAL', 'HIGH'])
            )
        ).count()
        
        # Active Threats (critical vulnerabilities from last 30 days) - filtered by user
        recent_date = datetime.now() - timedelta(days=30)
        active_threats = user_vulnerabilities.filter(
            Vulnerability.base_severity == 'CRITICAL',
            Vulnerability.published_date >= recent_date
        ).count()
        
        # Average CVSS Score - filtered by user
        avg_cvss_result = user_vulnerabilities.with_entities(func.avg(Vulnerability.cvss_score)).scalar()
        avg_cvss_score = round(float(avg_cvss_result), 2) if avg_cvss_result else 0.0
        
        # Average Exploitability (simulated as 80% of CVSS score) - filtered by user
        avg_exploit_result = user_vulnerabilities.with_entities(func.avg(Vulnerability.cvss_score * 0.8)).scalar()
        avg_exploit_score = round(float(avg_exploit_result), 2) if avg_exploit_result else 0.0
        
        # Patch Coverage
        total_vulns = counts.get('total', 0)
        patch_coverage = round((patched_cves / total_vulns * 100), 1) if total_vulns > 0 else 0.0
        
        # Vendor, Product and CWE counts (with error handling for schema issues)
        vendor_count = 0
        product_count = 0
        cwe_count = 0
        
        try:
            from models.vendor import Vendor
            vendor_count = session.query(Vendor).count()
        except Exception:
            vendor_count = 0
            
        try:
            from models.product import Product
            product_count = session.query(Product).count()
        except Exception:
            product_count = 0
            
        try:
            from models.weakness import Weakness
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
            cwe_count=cwe_count
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
@login_required
def assets() -> str:
    """Renders the Assets listing page."""
    logger.info("Accessing assets page.") # Logging mais informativo
    try:
        # Get assets data filtered by current user
        assets_list = Asset.query.filter_by(owner_id=current_user.id).all()
        return render_page(ROUTES['assets']['template'], assets_list=assets_list)
    except Exception as e:
        logger.error(f"Error loading assets page: {e}", exc_info=True)
        flash('Erro ao carregar assets.', 'danger')
        return render_page(ROUTES['assets']['template'], assets_list=[])

@main_bp.route(ROUTES['insights']['path'], methods=ROUTES['insights']['methods'])
def insights() -> str:
    """Renders the Insights page."""
    logger.info("Accessing insights page.") # Logging mais informativo
    # TODO: Get insights data (e.g., from an InsightsService)
    insights_data: Dict[str, Any] = {} # Placeholder
    return render_page(ROUTES['insights']['template'], insights_data=insights_data)

# Exemplo na versão refatorada
@main_bp.route(ROUTES['monitoring']['path'], methods=ROUTES['monitoring']['methods'])
def monitoring() -> str:
    """Renders the Monitoring page."""
    logger.info("Accessing monitoring page.")

    # TODO: Get monitoring data (rules, status, etc.) for the monitoring.html template
    monitoring_status: Dict[str, Any] = {} # Placeholder
    monitoring_rules: List[Any] = [] # Placeholder

    # Chama render_template diretamente, o contexto comum é adicionado pelo context processor
    return render_template(
        ROUTES['monitoring']['template'],
        monitoring_status=monitoring_status,
        monitoring_rules=monitoring_rules,
        # TODO: Pass other monitoring data (e.g., recent logs)
    )

# Reports route is handled by report_controller.py
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
        # Buscar dados do usuário atual
        user_data = user_service.get_user_data(current_user.id)
        
        # Pré-preencher formulário com dados atuais
        if request.method == 'GET':
            profile_form.first_name.data = user_data.get('first_name', '')
            profile_form.last_name.data = user_data.get('last_name', '')
            profile_form.email.data = user_data.get('email', '')
            profile_form.phone.data = user_data.get('phone', '')
            profile_form.address.data = user_data.get('address', '')
            profile_form.bio.data = user_data.get('bio', '')
        
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
                    
                    # Atualizar dados do usuário
                    success = user_service.update_user_data(current_user.id, update_data)
                    
                    if success:
                        flash('Perfil atualizado com sucesso!', 'success')
                        logger.info(f"Profile updated successfully for user {current_user.id}")
                        return redirect(url_for('main.account'))
                    else:
                        flash('Erro ao atualizar perfil. Tente novamente.', 'error')
                        
                except Exception as e:
                    logger.error(f"Error updating profile for user {current_user.id}: {str(e)}")
                    flash('Erro interno ao atualizar perfil.', 'error')
            
            elif form_type == 'password' and password_form.validate_on_submit():
                try:
                    # Verificar senha atual
                    if not current_user.check_password(password_form.current_password.data):
                        flash('Senha atual incorreta.', 'error')
                    else:
                        # Atualizar senha
                        current_user.set_password(password_form.new_password.data)
                        db.session.commit()
                        flash('Senha alterada com sucesso!', 'success')
                        logger.info(f"Password changed successfully for user {current_user.id}")
                        return redirect(url_for('main.account'))
                        
                except Exception as e:
                    logger.error(f"Error changing password for user {current_user.id}: {str(e)}")
                    flash('Erro interno ao alterar senha.', 'error')
                    db.session.rollback()
        
        # Buscar dados atualizados para exibição
        user_data = user_service.get_user_data(current_user.id)
        
        return render_page(
            ROUTES.get('account', {}).get('template', 'account.html'),
            user_account_data=user_data,
            profile_form=profile_form,
            password_form=password_form
        )
        
    except Exception as e:
        logger.error(f"Error in account page for user {current_user.id}: {str(e)}")
        flash('Erro ao carregar dados da conta.', 'error')
        return render_page(
            ROUTES.get('account', {}).get('template', 'account.html'),
            user_account_data={},
            profile_form=ProfileForm(),
            password_form=ChangePasswordForm()
        )


@main_bp.route('/vulnerabilities/<string:cve_id>', methods=['GET']) # Definido explicitamente. Ajuste path/methods conforme ROUTES
def vulnerability_details(cve_id: str) -> str:
    """
    Renders the vulnerability details page for a specific CVE with comprehensive analytics.
    
    Args:
        cve_id: The CVE ID to display details for.
    
    Returns:
        Rendered vulnerability details template.
    """
    logger.info(f"Accessing vulnerability details for CVE: {cve_id}")
    
    # Validação básica do formato do CVE ID
    import re
    cve_pattern = re.compile(r'^CVE-\d{4}-\d+$', re.IGNORECASE)

    if not cve_pattern.match(cve_id):
        logger.warning(f"Invalid CVE ID format received: '{cve_id}'")
        flash("O ID da vulnerabilidade fornecido tem um formato inválido.", 'danger')
        abort(400, description=f"Invalid CVE ID format: {cve_id}. Expected format: CVE-YYYY-NNNNN")
    
    try:
        from extensions import db
        
        # Get database session and initialize service
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # First try to get the vulnerability directly
        vulnerability = vuln_service.get_vulnerability_by_id(cve_id)
        
        if not vulnerability:
            logger.warning(f"Vulnerability with CVE ID {cve_id} not found.")
            abort(404)
        
        # Try to get analytics, but provide fallback if it fails
        try:
            analytics = vuln_service.get_vulnerability_analytics(cve_id)
        except Exception as analytics_error:
            logger.warning(f"Error getting analytics for {cve_id}: {analytics_error}")
            # Provide minimal analytics data as fallback
            analytics = {
                'vulnerability': vulnerability,
                'affected_assets_count': 0,
                'similar_vulnerabilities_count': 0,
                'calculated_risk_score': 0.0,
                'severity_level': vulnerability.base_severity,
                'cvss_score': vulnerability.cvss_score,
                'published_date': vulnerability.published_date,
                'last_modified': vulnerability.last_update
            }
        
        # Get related vulnerabilities with same severity
        related_vulns, _ = vuln_service.get_recent_paginated(1, 5)
        related_vulns = [v for v in related_vulns if v.base_severity == vulnerability.base_severity and v.cve_id != cve_id][:3]
        
        # Additional context for the template
        context = {
            'vulnerability': vulnerability,
            'analytics': analytics,
            'related_vulnerabilities': related_vulns,
            'cve_id': cve_id,
            'page_title': f'Detalhes - {cve_id}',
            'moment': datetime.now  # Adiciona função para calcular tempo
        }
        
        return render_page('vulnerability_details', **context)
        
    except Exception as e:
        logger.error(f"Error loading vulnerability details for {cve_id}: {e}", exc_info=True)
        abort(500)

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
    return render_page('400.html', error=error, error_code=400), 400


# TODO: Adicionar handlers para outros erros comuns como 403 (Forbidden), 401 (Unauthorized), etc.
# Exemplo:
# @main_bp.app_errorhandler(403)
# def forbidden_error(error: Any) -> Tuple[str, int]:
#     logger.warning(f"Forbidden access: {request.url} - {error}")
#     return render_page('403.html', error=error, error_code=403), 403


# TODO: Importar e registrar este Blueprint na sua aplicação Flask principal (ex: em app.py ou __init__.py)
# Exemplo:
# from .controllers.main_controller import main_bp
# app.register_blueprint(main_bp)
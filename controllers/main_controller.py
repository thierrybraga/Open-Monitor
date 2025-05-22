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

# TODO: Import necessary services or models for data fetching
from ..services.vulnerability_service import VulnerabilityService
from ..models.vulnerability import Vulnerability
from ..forms.search_forms import SearchForm # Exemplo de importação de formulários
from ..forms.newsletter_forms import NewsletterForm # Exemplo


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

    # TODO: Add logic to get data for the index page (e.g., critical vulnerability count, recent vulnerabilities)
    critical_count: int = 0 # Placeholder
    vulnerabilities: List[Any] = [] # Placeholder
    total_pages: int = 1 # Placeholder
    page: int = request.args.get('page', 1, type=int) # Exemplo de parâmetro de paginação


    return render_page(
        'index', # Passa a chave da rota
        critical_count=critical_count,
        page=page,
        vulnerabilities=vulnerabilities,
        total_pages=total_pages,
        # TODO: Passar outros dados específicos da página index
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

    # TODO: Initialize NewsletterForm if using Flask-WTF
    # form = NewsletterForm()

    if request.method == 'POST':
        # TODO: Process form submission and validation
        # if form.validate_on_submit():
        #     email = form.email.data.strip()
        #     logger.info(f"Newsletter signup attempt for email: '{email}'")
        #     try:
        #         # TODO: Add logic to process newsletter signup via a service
        #         NewsletterService.signup(email) # Exemplo de chamada de serviço
        #         flash(f"Obrigado por subscrever a newsletter com {email}!", 'success')
        #         # return redirect(url_for('main.newsletter')) # Opcional: redirecionar após sucesso
        #     except Exception as e: # Capturar exceções específicas do serviço
        #          logger.error(f"Newsletter signup failed for {email}: {e}")
        #          flash(f"Erro ao processar a subscrição: {e}", 'danger')
        # else:
        #     for field, errors in form.errors.items():
        #         for error in errors:
        #              flash(f"Erro no campo {getattr(form, field).label.text}: {error}", 'danger')
        #     logger.debug("Newsletter form validation failed.")
        #     # Permite exibir a página com erros de validação

        # Exemplo básico sem form (manter se não usar Flask-WTF por enquanto)
        email: Optional[str] = request.form.get('email', '').strip()
        if email:
             flash(f"Pedido de subscrição para {email} recebido. Funcionalidade não totalmente implementada/validada.", 'info')
        else:
            flash("Por favor, insira um endereço de e-mail.", 'warning')
            logger.debug("Newsletter signup form submitted without email (basic).")

    # Para método GET ou após POST sem redirecionamento
    # Chama render_template diretamente
    return render_template(
        ROUTES['newsletter']['template'], # Usará 'newsletter/newsletter.html' conforme o ROUTES
        # form=form # Passa o formulário para o template se estiver usando Flask-WTF
    )

@main_bp.route(ROUTES['chatbot']['path'], methods=ROUTES['chatbot']['methods'])
def chatbot() -> str:
    """Renders the Chatbot page."""
    logger.info("Accessing chatbot page.") # Logging mais informativo
    # TODO: Get any initial data needed for the chatbot.html template
    return render_page('chatbot')

@main_bp.route(ROUTES['analytics']['path'], methods=ROUTES['analytics']['methods'])
def analytics() -> str:
    """Renders the Analytics page."""
    logger.info("Accessing analytics page.") # Logging mais informativo
    # TODO: Get analytical data for the analytics.html template
    analytics_data: Dict[str, Any] = {} # Placeholder
    return render_page('analytics', analytics_data=analytics_data)

@main_bp.route(ROUTES['assets']['path'], methods=ROUTES['assets']['methods'])
def assets() -> str:
    """Renders the Assets listing page."""
    logger.info("Accessing assets page.") # Logging mais informativo
    # TODO: Get assets data (e.g., from an AssetService), possibly with pagination
    assets_list: List[Any] = [] # Placeholder
    return render_page(ROUTES['assets']['template'], assets_list=assets_list)

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

# Route for the Reports page
# Uses a variable parameter <period> in the URL
# Also includes a route without a parameter for a default period
@main_bp.route(ROUTES['reports']['path'] + '/<period>', methods=ROUTES['reports']['methods'])
@main_bp.route(ROUTES['reports']['path'], methods=ROUTES['reports']['methods'])
def reports(period: Optional[str] = None) -> str:
    """
    Renders the Reports page for a given period.

    Args:
        period: The report period (e.g., 'daily', 'weekly', 'monthly').
                Defaults to 'weekly' if not specified in the URL.
    """
    logger.info(f"Accessing reports page for period: {period}")

    if period is None:
        period = 'weekly'
        logger.debug("No period specified, defaulting to 'weekly'.")

    valid_periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
    if period not in valid_periods:
        logger.warning(f"Invalid period '{period}' requested for reports.")
        flash(f"Período de relatório inválido: '{period}'. Exibindo relatório semanal.", 'warning')
        period = 'weekly'

    # TODO: Add logic to get report data based on the 'period' (from a reports service)
    report_data: Dict[str, Any] = {} # Placeholder
    flash(f"Exibindo relatório: {period.capitalize()}", 'info')

    # Chama render_template diretamente
    return render_template(
        ROUTES['reports']['template'], # <-- Aqui usará 'reports/report.html' se o ROUTES estiver correto
        period=period,
        report_data=report_data,
        valid_periods=valid_periods,
        # TODO: Add other report-specific context variables
    )
# TODO: Add routes for Account, Vulnerability Details, etc., referencing ROUTES dictionary
# Example:
@main_bp.route('/account', methods=['GET', 'POST']) # Definido explicitamente. Ajuste path/methods conforme ROUTES
# TODO: Add login_required decorator if using Flask-Login
# @login_required
def account() -> str:
    """
    Rota para a página da Conta do Usuário.

    Renders the account.html template e processa atualizações da conta.
    """
    logger.info(f"Accessing account page with method: {request.method}")
    user_account_data: Dict[str, Any] = {} # Placeholder

    if request.method == 'POST':
         # TODO: Integrate with an account form (e.g., Flask-WTF) for validation
         logger.info("Processing account update (not fully implemented).")
         flash("Atualização da conta não totalmente implementada/validada.", 'info')
         # TODO: Add logic to update user account data via a service
         # return redirect(url_for('main.account')) # Optional redirect

    # TODO: Get user account data (e.g., from a UserService)
    # user_account_data = UserService.get_user_data(current_user.id)

    return render_page(ROUTES.get('account', {}).get('template', 'account.html'), user_account_data=user_account_data) # Referencia ROUTES mas usa fallback


@main_bp.route('/vulnerabilities/<string:cve_id>', methods=['GET']) # Definido explicitamente. Ajuste path/methods conforme ROUTES
def vulnerability_details(cve_id: str) -> str:
    """
    Rota para a página de Detalhes da Vulnerabilidade.

    Renders the vulnerability_details.html template para um CVE ID específico.
    Inclui validação básica do formato do CVE ID.

    Args:
        cve_id: O ID da vulnerabilidade (e.g., 'CVE-YYYY-NNNNN').
    """
    logger.info(f"Accessing vulnerability details page for CVE ID: {cve_id}")

    # Validação básica do formato do CVE ID (exemplo)
    # Importado re localmente para este exemplo. Mova para imports se usado globalmente.
    import re
    cve_pattern = re.compile(r'^CVE-\d{4}-\d+$', re.IGNORECASE) # Formato CVE padrão

    if not cve_pattern.match(cve_id):
        logger.warning(f"Invalid CVE ID format received: '{cve_id}'")
        flash("O ID da vulnerabilidade fornecido tem um formato inválido.", 'danger')
        # Aborta com 400 (Bad Request) que será capturado pelo handler de erro
        abort(400, description=f"Invalid CVE ID format: {cve_id}. Expected format: CVE-YYYY-NNNNN")


    # TODO: Obter dados da vulnerabilidade com base no cve_id (e.g., de um VulnerabilityService)
    # vulnerability_data = VulnerabilityService.get_vulnerability_by_id(cve_id)
    vulnerability_data: Optional[Dict[str, Any]] = None # Placeholder

    # Verificar se a vulnerabilidade foi encontrada
    if vulnerability_data is None:
        logger.warning(f"Vulnerability with ID '{cve_id}' not found.")
        flash(f"Vulnerabilidade com ID '{cve_id}' não encontrada.", 'warning')
        # Aborta com 404 (Not Found) que será capturado pelo handler de erro
        abort(404, description=f"Vulnerability with ID {cve_id} not found.")

    return render_page(
        ROUTES.get('vulnerability_details', {}).get('template', 'vulnerability_details.html'), # Referencia ROUTES mas usa fallback
        cve_id=cve_id,
        vulnerability_data=vulnerability_data,
        # TODO: Adicionar outras variáveis de contexto específicas aqui (e.g., dados relacionados)
    )

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
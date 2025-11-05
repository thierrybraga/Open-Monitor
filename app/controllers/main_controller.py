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
    jsonify,
    session,
    send_file
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
    accept_header = request.headers.get('Accept', '')
    fmt = (request.args.get('format') or '').strip().lower()
    if fmt in {'json', 'true', '1'}:
        return True
    return ('application/json' in accept_header) or request.is_json


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
        # Lista de itens de navegação derivada das rotas configuradas
        'nav_items': [
            {
                'endpoint': key,
                'label': value.get('label', key.title()),
                'icon': value.get('icon', 'dot')
            }
            for key, value in ROUTES.items()
            if value.get('path') # apenas rotas navegáveis
        ],
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
    """Serve a Home via template (pages/index.html) usando a estrutura de templates."""
    logger.info("Rendering template-based Home 'pages/index.html'.")

    try:
        # Contexto seguro para evitar erros 500 por variáveis indefinidas
        try:
            page = int(request.args.get('page', 1))
        except Exception:
            page = 1
        try:
            per_page = int(request.args.get('per_page', 10))
        except Exception:
            per_page = 10

        # vendor_ids=1,2,3 -> lista de strings/ints
        raw_vendor_ids = (request.args.get('vendor_ids') or '').strip()
        selected_vendor_ids: List[int] = []
        if raw_vendor_ids:
            try:
                selected_vendor_ids = [int(v) for v in raw_vendor_ids.split(',') if v.strip().isdigit()]
            except Exception:
                selected_vendor_ids = []

        # Se nenhum vendor foi passado na URL, tentar preferências do usuário autenticado
        try:
            if not selected_vendor_ids and getattr(current_user, 'is_authenticated', False):
                from app.models.sync_metadata import SyncMetadata
                key = f'user_vendor_preferences:{current_user.id}'
                pref = db.session.query(SyncMetadata).filter_by(key=key).first()
                if pref and pref.value:
                    parsed = [int(x) for x in str(pref.value).split(',') if str(x).strip().isdigit()]
                    selected_vendor_ids = parsed
        except Exception:
            # Ignorar falhas de leitura de preferências
            pass

        # Buscar dados reais via serviço, aplicando filtro por vendors selecionados quando presente
        vulnerabilities: List[Vulnerability] = []
        total_count: int = 0
        critical_count = high_count = medium_count = 0
        weekly_critical = weekly_high = weekly_medium = weekly_total = 0

        selected_vendor_map: List[Dict[str, Any]] = []
        try:
            session = db.session
            vuln_service = VulnerabilityService(session)

            # Lista paginada de vulnerabilidades recentes, escopadas por vendors quando fornecidos
            vulnerabilities, total_count = vuln_service.get_recent_paginated(
                page=page,
                per_page=per_page,
                vendor_ids=selected_vendor_ids or None
            )

            # Contagens gerais por severidade (escopadas por vendors quando fornecidos)
            counts = vuln_service.get_dashboard_counts(vendor_ids=selected_vendor_ids or None)
            critical_count = int(counts.get('critical', 0))
            high_count = int(counts.get('high', 0))
            medium_count = int(counts.get('medium', 0))
            # Total pode não ser apenas soma; use valor retornado
            total_count_overview = int(counts.get('total', 0))
            # Se overview total estiver disponível, preferir para o card "Total"
            if total_count_overview:
                total_card_value = total_count_overview
            else:
                total_card_value = total_count

            # Contagens semanais por severidade
            weekly_counts = vuln_service.get_weekly_counts(vendor_ids=selected_vendor_ids or None)
            weekly_critical = int(weekly_counts.get('critical', 0))
            weekly_high = int(weekly_counts.get('high', 0))
            weekly_medium = int(weekly_counts.get('medium', 0))
            weekly_total = int(weekly_counts.get('total', 0))

            # Obter nomes dos vendors selecionados para exibir chips na Home
            if selected_vendor_ids:
                try:
                    from app.models.vendor import Vendor
                    vendors = (
                        session.query(Vendor.id, Vendor.name)
                        .filter(Vendor.id.in_(selected_vendor_ids))
                        .all()
                    )
                    selected_vendor_map = [
                        {'id': int(vid), 'name': (vname or '').strip()}
                        for vid, vname in vendors
                    ]
                except Exception:
                    selected_vendor_map = []
        except Exception as e:
            logger.error(f"Error fetching Home data: {e}", exc_info=True)
            # Mantém valores padrão já inicializados

        # Calcular páginas totais com aritmética inteira robusta
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 1
        if total_pages <= 0:
            total_pages = 1

        # Usa helper para renderizar com contexto da aplicação
        return render_page(
            'index',
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            total_count=total_card_value,
            weekly_critical=weekly_critical,
            weekly_high=weekly_high,
            weekly_medium=weekly_medium,
            weekly_total=weekly_total,
            vulnerabilities=vulnerabilities,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            selected_vendor_ids=selected_vendor_ids,
            selected_vendor_map=selected_vendor_map,
        )
    except Exception as e:
        logger.error(f"Error rendering Home template: {e}", exc_info=True)
        # Fallback mínimo
        return render_page('index',
                           critical_count=0,
                           high_count=0,
                           medium_count=0,
                           total_count=0,
                           weekly_critical=0,
                           weekly_high=0,
                           weekly_medium=0,
                           weekly_total=0,
                           vulnerabilities=[],
                           page=1,
                           per_page=10,
                           total_pages=1,
                           selected_vendor_ids=[])

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

    # GeoIP: posição padrão baseada no IP 8.8.8.8
    try:
        from app.services.geoip_service import GeoIPService
        default_ip = "8.8.8.8"
        geo = GeoIPService.get_location_for_ip(default_ip) or {}
        map_center_lat = geo.get('lat') or -23.5505  # Fallback: São Paulo
        map_center_lng = geo.get('lon') or -46.6333
        map_center_label = f"{geo.get('city') or ''} {geo.get('country') or ''}".strip()
    except Exception:
        map_center_lat = -23.5505
        map_center_lng = -46.6333
        map_center_label = ""

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
        map_center_lat=map_center_lat,
        map_center_lng=map_center_lng,
        map_center_label=map_center_label,
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
    """Renderiza o feed de notícias com filtros, ordenação e paginação simples."""
    logger.info(f"Accessing newsletter (news feed) with method: {request.method}")

    # Query params para UX
    q = (request.args.get('q') or '').strip()
    tag = (request.args.get('tag') or '').strip()
    source = (request.args.get('source') or '').strip()
    sort = (request.args.get('sort') or 'newest').strip()  # 'newest' | 'oldest' | 'relevance'
    # Filtros por data (ISO 8601: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS)
    start_str = (request.args.get('start') or '').strip()
    end_str = (request.args.get('end') or '').strip()
    start_dt = None
    end_dt = None
    try:
        if start_str:
            start_dt = datetime.fromisoformat(start_str)
        if end_str:
            end_dt = datetime.fromisoformat(end_str)
    except Exception:
        start_dt, end_dt = None, None
    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = max(min(int(request.args.get('per_page', 10)), 50), 1)
    except ValueError:
        page, per_page = 1, 10

    # Carregar itens reais da CyberNews API e feeds RSS
    try:
        from app.services.cybernews_service import CyberNewsService
        base_items = CyberNewsService.get_news(limit=60)
        base_count = len(base_items)
        logger.info(f"Newsletter: itens carregados da CyberNews = {base_count}")
    except Exception as e:
        logger.error(f"Erro ao carregar notícias da CyberNews: {e}")
        base_items = []
        base_count = 0

    try:
        from app.services.rss_feed_service import RSSFeedService
        rss_items = RSSFeedService.get_news(limit=60)
        rss_count = len(rss_items)
        logger.info(f"Newsletter: itens carregados de RSS = {rss_count}")
    except Exception as e:
        logger.error(f"Erro ao carregar notícias de RSS: {e}")
        rss_items = []

    # Vendor Release Notes (interface unificada - Fortinet FortiGate 7.0/7.2/7.4)
    try:
        from app.services.vendor_release_notes_service import VendorReleaseNotesService
        vendor_release_items = VendorReleaseNotesService.get_vendor_release_notes(limit=60, vendor_filter=["fortinet"])
        vendor_release_count = len(vendor_release_items)
        logger.info(f"Newsletter: itens carregados vendor release notes = {vendor_release_count}")
    except Exception as e:
        logger.error(f"Erro ao carregar notas de release de vendors: {e}")
        vendor_release_items = []

    aggregated_items = (base_items or []) + (rss_items or []) + (vendor_release_items or [])

    # Enriquecer/normalizar tags para todos os itens
    try:
        from app.services.tagging_service import TaggingService
        for it in aggregated_items:
            it['tags'] = TaggingService.enrich_tags(
                existing_tags=it.get('tags') or [],
                title=it.get('title') or '',
                summary=it.get('summary') or '',
                source=str(it.get('source') or '')
            )
    except Exception:
        pass

    # Filtragem e pontuação de busca
    def score_query(item):
        if not q:
            return 0.0
        text_title = (item.get('title') or '')
        text_summary = (item.get('summary') or '')
        text_source = str(item.get('source') or '')
        q_lower = q.lower()
        score = 0.0
        # Pesos simples: título tem maior peso, depois resumo, depois fonte
        if q_lower in text_title.lower():
            score += 3.0
        if q_lower in text_summary.lower():
            score += 1.5
        if q_lower in text_source.lower():
            score += 0.5
        # Tokens individuais aumentam mais a chance de match parcial
        for token in [t for t in q_lower.split() if t]:
            if token in text_title.lower():
                score += 1.0
            if token in text_summary.lower():
                score += 0.5
        return score

    def matches_tag(item):
        if not tag:
            return True
        return tag in (item.get('tags') or [])

    def matches_source(item):
        if not source:
            return True
        return source.lower() == str(item.get('source','')).lower()

    def matches_date(item):
        if not start_dt and not end_dt:
            return True
        pub = item.get('published_at')
        try:
            if start_dt and pub < start_dt:
                return False
            if end_dt and pub > end_dt:
                return False
        except Exception:
            return True
        return True

    # Aplica filtros e calcula score
    scored: List[Dict] = []
    for i in aggregated_items:
        if matches_tag(i) and matches_source(i) and matches_date(i):
            s = score_query(i)
            # Se há consulta, exige score > 0; caso contrário, inclui
            if not q or s > 0:
                i_copy = dict(i)
                i_copy['__score'] = s
                scored.append(i_copy)

    if not aggregated_items:
        logger.warning("Newsletter: nenhum item retornado (CyberNews/RSS). Verifique conectividade e dependências.")
    logger.info(
        f"Newsletter: itens após filtro = {len(scored)} | q='{q}' tag='{tag}' source='{source}' sort='{sort}' "
        f"| base={len(base_items)} rss={len(rss_items)}"
    )

    # Ordenação
    try:
        if sort == 'relevance' and q:
            scored.sort(key=lambda i: (i.get('__score') or 0.0, i.get('published_at')), reverse=True)
        else:
            scored.sort(key=lambda i: i.get('published_at'), reverse=(sort != 'oldest'))
    except Exception:
        pass

    # Paginação
    total_items = len(scored)
    start = (page - 1) * per_page
    end = start + per_page
    news_items = scored[start:end]

    # Metadados para filtros
    all_tags = sorted({t for i in aggregated_items for t in (i.get('tags') or [])})
    all_sources = sorted({str(i.get('source','')) for i in aggregated_items if i.get('source')})
    # Log distribuição básica para diagnóstico
    try:
        tag_counts = {t: 0 for t in all_tags}
        for i in base_items:
            for t in (i.get('tags') or []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        source_counts = {}
        for s in all_sources:
            source_counts[s] = sum(1 for i in base_items if str(i.get('source','')) == s)
        logger.debug(f"Newsletter: distribuição por tag = {tag_counts}")
        logger.debug(f"Newsletter: distribuição por fonte = {source_counts}")
    except Exception:
        pass

    page_title = 'Cybersecurity News Feed'

    # Se o cliente solicitar JSON, retornar a resposta serializada
    if wants_json():
        def serialize_item(i: Dict[str, Any]) -> Dict[str, Any]:
            pub = i.get('published_at')
            if isinstance(pub, datetime):
                pub_str = pub.isoformat()
            else:
                pub_str = str(pub) if pub is not None else ''
            return {
                'title': i.get('title', ''),
                'summary': i.get('summary', ''),
                'source': i.get('source', ''),
                'link': i.get('link', ''),
                'published_at': pub_str,
                'tags': i.get('tags', []),
            }

        return jsonify({
            'items': [serialize_item(i) for i in news_items],
            'items_base_count': base_count,
            'items_filtered_count': total_items,
            'page': page,
            'per_page': per_page,
            'total_items': total_items,
            'filters': {'q': q, 'tag': tag, 'source': source, 'sort': sort},
            'all_tags': all_tags,
            'all_sources': all_sources,
        })
    return render_page(
        'newsletter',
        page_title=page_title,
        news_items=news_items,
        base_count=base_count,
        # Filtros e estado atual
        q=q, tag=tag, source=source, sort=sort,
        all_tags=all_tags, all_sources=all_sources,
        # Paginação
        page=page, per_page=per_page, total_items=total_items,
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
    try:
        from app.extensions import db
        from sqlalchemy import func, desc, or_, distinct
        from datetime import datetime, timedelta
        from app.models.vulnerability import Vulnerability
        from app.models.asset import Asset
        from app.models.asset_vulnerability import AssetVulnerability
        from app.models.monitoring_rule import MonitoringRule

        session = db.session
        from flask_login import current_user
        owner_id = current_user.id if getattr(current_user, 'is_authenticated', False) else None

        # Contagem de vulnerabilidades críticas APENAS entre as vinculadas a ativos
        q_critical = session.query(func.count(distinct(AssetVulnerability.vulnerability_id)))\
            .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)\
            .filter(Vulnerability.base_severity == 'CRITICAL')
        if owner_id:
            q_critical = q_critical.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                   .filter(Asset.owner_id == owner_id)
        critical_count = q_critical.scalar() or 0

        # Contagem de assets monitorados
        q_assets = session.query(func.count(Asset.id))
        if owner_id:
            q_assets = q_assets.filter(Asset.owner_id == owner_id)
        assets_count = q_assets.scalar() or 0

        # Contagem de regras de monitoramento
        q_rules = session.query(func.count(MonitoringRule.id))
        if owner_id:
            q_rules = q_rules.filter(MonitoringRule.user_id == owner_id)
        monitoring_rules_count = q_rules.scalar() or 0

        # Métricas adicionais baseadas em ativos
        q_assets_with_vulns = session.query(func.count(distinct(AssetVulnerability.asset_id)))
        if owner_id:
            q_assets_with_vulns = q_assets_with_vulns.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                               .filter(Asset.owner_id == owner_id)
        assets_with_vulns_count = q_assets_with_vulns.scalar() or 0

        q_assets_with_critical = session.query(func.count(distinct(AssetVulnerability.asset_id)))\
            .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)\
            .filter(Vulnerability.base_severity == 'CRITICAL')
        if owner_id:
            q_assets_with_critical = q_assets_with_critical.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                                   .filter(Asset.owner_id == owner_id)
        assets_with_critical_count = q_assets_with_critical.scalar() or 0

        q_assets_without_vendor = session.query(func.count(Asset.id)).filter(Asset.vendor_id.is_(None))
        if owner_id:
            q_assets_without_vendor = q_assets_without_vendor.filter(Asset.owner_id == owner_id)
        assets_without_vendor_count = q_assets_without_vendor.scalar() or 0

        q_assets_without_owner = session.query(func.count(Asset.id)).filter(Asset.owner_id.is_(None))
        if owner_id:
            q_assets_without_owner = q_assets_without_owner.filter(Asset.owner_id == owner_id)
        assets_without_owner_count = q_assets_without_owner.scalar() or 0

        # Insights recentes baseados em ativos: últimos 10 por atualização
        q_recent_assets = session.query(Asset)
        if owner_id:
            q_recent_assets = q_recent_assets.filter(Asset.owner_id == owner_id)
        recent_assets = (
            q_recent_assets
            .order_by(desc(Asset.updated_at), desc(Asset.created_at))
            .limit(10)
            .all()
        )

        # Função util para pegar severidade máxima do ativo
        severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        def max_severity_for_asset(asset: Asset) -> str:
            max_val = 0
            max_sev = None
            try:
                for av in asset.vulnerabilities:
                    v = av.vulnerability
                    sev = getattr(v, 'base_severity', None)
                    rank = severity_order.get(sev or '', 0)
                    if rank > max_val:
                        max_val = rank
                        max_sev = sev
            except Exception:
                pass
            return max_sev or 'NONE'

        recent_insights = []
        for a in recent_assets:
            date_obj = a.updated_at or a.created_at
            date_str = date_obj.strftime('%Y-%m-%d') if date_obj else ''
            highest_sev = max_severity_for_asset(a)
            has_vulns = bool(a.vulnerabilities)
            status = 'Sem vulnerabilidades'
            try:
                if has_vulns:
                    # Se houver alguma vulnerabilidade em aberto
                    open_exists = any((getattr(av, 'status', 'OPEN') or 'OPEN') == 'OPEN' for av in a.vulnerabilities)
                    status = 'Aberto' if open_exists else 'Mitigado'
            except Exception:
                pass
            vendor_name = getattr(a.vendor, 'name', None)
            desc_vendor = vendor_name if vendor_name else 'Sem fornecedor'
            description = f"Asset {a.name} ({a.ip_address}) - {desc_vendor}"
            sev_display = highest_sev if highest_sev != 'NONE' else 'LOW'
            recent_insights.append({
                'date': date_str,
                'type': 'Ativo',
                'description': description,
                'severity': sev_display,
                'status': status
            })

        insights_data: Dict[str, Any] = {
            'critical_count': int(critical_count),
            'assets_count': int(assets_count),
            'monitoring_rules_count': int(monitoring_rules_count),
            'assets_with_vulns_count': int(assets_with_vulns_count),
            'assets_with_critical_count': int(assets_with_critical_count),
            'assets_without_vendor_count': int(assets_without_vendor_count),
            'assets_without_owner_count': int(assets_without_owner_count),
            'recent_insights': recent_insights
        }

        return render_page('insights', insights_data=insights_data)
    except Exception as e:
        logger.error(f"Error rendering insights page: {e}", exc_info=True)
        # Fallback seguro
        insights_data: Dict[str, Any] = {
            'critical_count': 0,
            'assets_count': 0,
            'monitoring_rules_count': 0,
            'recent_insights': []
        }
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
    newsletter_form = NewsletterSubscriptionForm()
    
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
            # Pré-preencher newsletter com email do usuário
            try:
                newsletter_form.email.data = user_data['email']
            except Exception:
                pass
        
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
            
            # Processar formulário de notificações/newsletter
            elif form_type == 'newsletter':
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                from app.services.newsletter_service import NewsletterService
                from app.services.email_service import EmailService
                newsletter_service = NewsletterService(db.session)
                email_service = EmailService()
                
                if newsletter_form.validate_on_submit():
                    try:
                        email = newsletter_form.email.data.strip().lower()
                        # Aqui poderíamos salvar preferências adicionais (futuro)
                        existing_subscriber = newsletter_service.get_subscriber_by_email(email)
                        
                        if existing_subscriber:
                            if existing_subscriber.is_active:
                                msg = f"O email {email} já está inscrito na newsletter."
                            else:
                                newsletter_service.resubscribe(email)
                                email_service.send_welcome_email(email)
                                msg = f"Bem-vindo de volta! Sua inscrição foi reativada para {email}."
                        else:
                            success = newsletter_service.signup(email)
                            if success:
                                email_service.send_welcome_email(email)
                                msg = f"Obrigado por se inscrever na newsletter com {email}!"
                            else:
                                if is_ajax:
                                    return jsonify({'success': False, 'message': 'Erro ao processar a inscrição.'}), 400
                                flash('Erro ao processar a inscrição.', 'danger')
                                return redirect(url_for('main.account'))
                        
                        if is_ajax:
                            return jsonify({'success': True, 'message': msg}), 200
                        flash(msg, 'success')
                        return redirect(url_for('main.account'))
                    except ValueError as e:
                        if is_ajax:
                            return jsonify({'success': False, 'message': str(e)}), 400
                        flash(f"Erro de validação: {str(e)}", 'danger')
                    except Exception as e:
                        logger.error(f"Newsletter processing failed: {e}")
                        if is_ajax:
                            return jsonify({'success': False, 'message': 'Erro interno ao salvar preferências.'}), 500
                        flash('Erro interno ao salvar preferências.', 'danger')
                else:
                    # Validação falhou
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Erro de validação.', 'errors': newsletter_form.errors}), 400
                    for field, errors in newsletter_form.errors.items():
                        for error in errors:
                            flash(f"Erro no campo {getattr(newsletter_form, field).label.text}: {error}", 'danger')
        
        # Dados para exibição
        return render_page(
            'account',
            user_account_data={**user_data, 'display_name': display_name},
            profile_form=profile_form,
            password_form=password_form,
            newsletter_form=newsletter_form,
            user_preferences=None
        )
        
    except Exception as e:
        logger.error(f"Error in account page: {str(e)}")
        flash('Erro ao carregar dados da conta.', 'error')
        return render_page(
            'account',
            user_account_data={},
            profile_form=ProfileForm(),
            password_form=ChangePasswordForm(),
            newsletter_form=NewsletterSubscriptionForm(),
            user_preferences=None
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
    return render_page('404', error=error, error_code=404), 404

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
    return render_page('500', error=error, error_code=500), 500

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
@login_required
def settings() -> str:
    """Renders and updates the Settings page preferences stored in session."""
    logger.info(f"Accessing settings page via {request.method}.")

    # Default settings structure
    default_settings: Dict[str, Any] = {
        'general': {
            'theme': 'auto',
            'language': current_app.config.get('HTML_LANG', 'pt-BR'),
            'timezone': 'UTC',
        },
        'security': {
            'two_factor': False,
            'login_notifications': False,
            'session_timeout': 30,
        },
        'notifications': {
            'email_notifications': True,
            'vulnerability_alerts': True,
            'report_notifications': True,
        },
        'reports': {
            'default_format': 'pdf',
            'auto_export': False,
            'include_charts': True,
        },
    }

    # Ensure settings exist in session
    settings_state: Dict[str, Any] = session.get('settings') or default_settings.copy()

    def checkbox_enabled(name: str) -> bool:
        return name in request.form

    if request.method == 'POST':
        section: str = (request.form.get('section') or '').strip()
        logger.debug(f"Settings POST section: '{section}'")
        try:
            if section == 'general':
                theme = request.form.get('theme') or settings_state['general']['theme']
                language = request.form.get('language') or settings_state['general']['language']
                timezone = request.form.get('timezone') or settings_state['general']['timezone']
                settings_state['general'].update({
                    'theme': theme,
                    'language': language,
                    'timezone': timezone,
                })
                flash('Preferências gerais salvas.', 'success')

            elif section == 'security':
                settings_state['security'].update({
                    'two_factor': checkbox_enabled('two_factor'),
                    'login_notifications': checkbox_enabled('login_notifications'),
                    'session_timeout': int(request.form.get('session_timeout') or settings_state['security']['session_timeout']),
                })
                flash('Configurações de segurança salvas.', 'success')

            elif section == 'notifications':
                settings_state['notifications'].update({
                    'email_notifications': checkbox_enabled('email_notifications'),
                    'vulnerability_alerts': checkbox_enabled('vulnerability_alerts'),
                    'report_notifications': checkbox_enabled('report_notifications'),
                })
                flash('Preferências de notificações salvas.', 'success')

            elif section == 'reports':
                default_format = request.form.get('default_format') or settings_state['reports']['default_format']
                settings_state['reports'].update({
                    'default_format': default_format,
                    'auto_export': checkbox_enabled('auto_export'),
                    'include_charts': checkbox_enabled('include_charts'),
                })
                flash('Configurações de relatórios salvas.', 'success')

            else:
                flash('Seção inválida nas configurações.', 'warning')

            # Persist to session
            session['settings'] = settings_state
            logger.debug(f"Settings updated in session: {settings_state}")

            # PRG pattern
            return redirect(url_for('main.settings'))
        except Exception as e:
            logger.error(f"Failed to update settings: {e}", exc_info=True)
            flash('Erro ao salvar configurações.', 'danger')
            return redirect(url_for('main.settings'))

    # GET: render with current settings
    settings_data = settings_state
    return render_page('settings', settings_data=settings_data)


# TODO: Importar e registrar este Blueprint na sua aplicação Flask principal (ex: em app.py ou __init__.py)
# Exemplo:
# from utils.controllers.main_controller import main_bp
# app.register_blueprint(main_bp)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from app.extensions.middleware import require_asset_ownership, audit_log
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, load_only
from sqlalchemy import text, inspect, func

from app.models.asset import Asset
from app.extensions import db
from app.forms.asset_form import AssetForm
from app.models.user import User
from app.models.asset_product import AssetProduct
from app.models.product import Product

asset_bp = Blueprint('asset', __name__, url_prefix='/assets')


@asset_bp.route('/')
@login_required
def list_assets():
    # Exibir todos os ativos cadastrados, independentemente do usuário

    # Parse seguro de vendor_ids na URL (suporta múltiplos parâmetros e CSV)
    selected_vendor_ids = []
    # Flag: parâmetro vendor_ids foi explicitamente fornecido na URL (mesmo vazio)
    vendor_filter_provided = False
    try:
        raw_list = request.args.getlist('vendor_ids') or []
        raw_param = request.args.get('vendor_ids', '')
        vendor_filter_provided = (
            ('vendor_ids' in request.args)
            or (raw_param is not None)
            or (isinstance(request.query_string, (bytes, bytearray)) and b'vendor_ids' in request.query_string)
            or ('vendor_ids=' in (request.url or ''))
        )
        parsed: list[int] = []
        if raw_list:
            for item in raw_list:
                for part in str(item).split(','):
                    part = part.strip()
                    if part.isdigit():
                        parsed.append(int(part))
        elif raw_param:
            for part in str(raw_param).split(','):
                part = part.strip()
                if part.isdigit():
                    parsed.append(int(part))
        selected_vendor_ids = sorted(set(parsed))
    except Exception:
        selected_vendor_ids = []

    # Não retornar lista vazia quando vendor_ids estiver vazio; tratar como "sem filtro"
    # Mantemos selected_vendor_ids apenas para refletir estado da UI, sem bloquear a listagem.

    # Detecta se as colunas de tipo existem no banco atual (agnóstico de SGBD)
    try:
        insp = inspect(db.engine)
        colnames = [c['name'] for c in insp.get_columns('assets')]
        has_asset_type_col = ('asset_type' in colnames)
        has_catalog_tag_col = ('catalog_tag' in colnames)
    except Exception:
        has_asset_type_col = True
        has_catalog_tag_col = False

    # Detecta se a tabela asset_products existe para evitar falha de eager load
    try:
        insp = inspect(db.engine)
        has_asset_products_table = ('asset_products' in insp.get_table_names())
    except Exception:
        has_asset_products_table = True

    # Construir opções de carregamento de forma resiliente
    if has_asset_products_table:
        query = Asset.query.options(
            selectinload(Asset.vendor),
            selectinload(Asset.owner),
            selectinload(Asset.asset_products).selectinload(AssetProduct.product),
        )
    else:
        query = Asset.query.options(
            selectinload(Asset.vendor),
            selectinload(Asset.owner),
        )

    # Se colunas específicas não existirem, evita carregá-las para não quebrar em SELECT
    try:
        if not has_asset_type_col and not has_catalog_tag_col:
            query = query.options(
                load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id)
            )
        elif has_catalog_tag_col and not has_asset_type_col:
            # Catalog tag presente: incluir no load_only para acesso seguro
            query = query.options(
                load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id, Asset.catalog_tag)
            )
        # Caso ambas existam, manter o carregamento padrão com relationships
    except Exception:
        pass

    # Escopo por usuário: retornar apenas ativos do usuário autenticado
    try:
        query = query.filter(Asset.owner_id == current_user.id)
    except Exception:
        # Se a coluna não existir ou houver erro, não bloquear a listagem
        pass

    # Se houver vendor_ids válidos, aplicar filtro por fornecedor
    if selected_vendor_ids:
        try:
            query = query.filter(Asset.vendor_id.in_(selected_vendor_ids))
        except Exception:
            # Não bloquear se o filtro falhar; prosseguir sem filtro
            pass

    # Parâmetros de paginação
    try:
        page = request.args.get('page', None, type=int)
    except Exception:
        page = None
    try:
        per_page = request.args.get('per_page', None, type=int)
    except Exception:
        per_page = None

    # Defaults e limites
    try:
        default_page = current_app.config.get('PAGINATION_DEFAULT_PAGE', 1)
        default_per = current_app.config.get('PAGINATION_DEFAULT_PER_PAGE', 20)
        max_per = current_app.config.get('PAGINATION_MAX_PER_PAGE', 100)
        page = page if isinstance(page, int) and page > 0 else default_page
        per_page = per_page if isinstance(per_page, int) and per_page > 0 else default_per
        per_page = min(per_page, max_per)
    except Exception:
        page = 1
        per_page = 20

    # Ordenação estável e paginação
    try:
        query = query.order_by(Asset.id.desc())
    except Exception:
        pass

    try:
        from app.utils.pagination import paginate_query
        pag = paginate_query(query, page=page, per_page=per_page, error_out=False)
        assets = pag.items
    except Exception:
        # Fallback: sem paginação
        pag = None
        assets = query.all()

    # Expõe um campo seguro para o template, usando catalog_tag como fonte do "tipo" quando disponível
    for a in assets:
        try:
            if has_catalog_tag_col:
                a.asset_type_safe = getattr(a, 'catalog_tag', None)
            elif has_asset_type_col:
                a.asset_type_safe = getattr(a, 'asset_type', None)
            else:
                a.asset_type_safe = None
        except Exception:
            a.asset_type_safe = None

    return render_template(
        'assets/asset_list.html',
        assets=assets,
        selected_vendor_ids=selected_vendor_ids,
        pagination=pag,
        page=page,
        per_page=per_page
    )


@asset_bp.route('/<int:asset_id>', methods=['GET'])
@login_required
@require_asset_ownership
def asset_detail(asset_id):
    """Renderiza a página de detalhes do ativo (apenas do proprietário ou admin)."""
    # Detecta colunas de forma agnóstica ao banco
    try:
        current_app.logger.debug(f"asset_detail start: asset_id={asset_id}")
        inspector = inspect(db.engine)
        asset_columns = {col.get('name') for col in inspector.get_columns('assets')}
        has_asset_type_col = 'asset_type' in asset_columns
        has_catalog_tag_col = 'catalog_tag' in asset_columns
    except Exception:
        has_asset_type_col = True
        has_catalog_tag_col = False

    # Detecta existência de tabela de forma agnóstica ao banco
    try:
        inspector = inspect(db.engine)
        has_asset_products_table = inspector.has_table('asset_products')
    except Exception:
        has_asset_products_table = False

    opts = []
    try:
        if has_asset_products_table:
            opts.append(selectinload(Asset.vendor))
            opts.append(selectinload(Asset.owner))
            opts.append(selectinload(Asset.asset_products).selectinload(AssetProduct.product))
        else:
            opts.append(selectinload(Asset.vendor))
            opts.append(selectinload(Asset.owner))
        if not has_asset_type_col:
            try:
                safe_cols = [Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id]
                try:
                    inspector = inspect(db.engine)
                    asset_columns = {col.get('name') for col in inspector.get_columns('assets')}
                except Exception:
                    asset_columns = set()
                if 'created_at' in asset_columns:
                    safe_cols.append(Asset.created_at)
                if 'updated_at' in asset_columns:
                    safe_cols.append(Asset.updated_at)
                opts.append(load_only(*safe_cols))
            except Exception:
                pass
    except Exception:
        opts = []

    try:
        asset = (
            db.session.query(Asset)
            .options(*tuple(opts))
            .filter(Asset.id == asset_id)
            .first()
        )
    except Exception:
        asset = (
            db.session.query(Asset)
            .filter(Asset.id == asset_id)
            .first()
        )
    if asset is None:
        abort(404)
    try:
        current_app.logger.debug(f"asset_detail loaded asset id={asset.id} name={asset.name}")
    except Exception:
        pass

    # Campo seguro para template (prioriza catalog_tag)
    try:
        if has_catalog_tag_col:
            try:
                asset.asset_type_safe = asset.catalog_tag
            except Exception:
                asset.asset_type_safe = None
        elif has_asset_type_col:
            asset.asset_type_safe = asset.asset_type
        else:
            asset.asset_type_safe = None
    except Exception:
        asset.asset_type_safe = None

    # Campos de auditoria seguros (created_at / updated_at)
    try:
        inspector = inspect(db.engine)
        asset_columns = {col.get('name') for col in inspector.get_columns('assets')}
    except Exception:
        asset_columns = set()
    try:
        asset.created_at_safe = (getattr(asset, 'created_at', None) if 'created_at' in asset_columns else None)
    except Exception:
        asset.created_at_safe = None
    try:
        asset.updated_at_safe = (getattr(asset, 'updated_at', None) if 'updated_at' in asset_columns else None)
    except Exception:
        asset.updated_at_safe = None

    # Campos opcionais seguros para evitar AttributeError quando colunas não existem
    try:
        asset.hostname_safe = getattr(asset, 'hostname', None)
    except Exception:
        asset.hostname_safe = None
    try:
        asset.location_safe = getattr(asset, 'location', None)
    except Exception:
        asset.location_safe = None
    try:
        asset.description_safe = getattr(asset, 'description', None)
    except Exception:
        asset.description_safe = None

    # Lista segura de produtos vinculados para evitar lazy-load quando tabela não existe
    try:
        if has_asset_products_table:
            asset_products_safe = list(asset.asset_products or [])
        else:
            asset_products_safe = []
    except Exception:
        asset_products_safe = []

    # Contagem segura de produtos do fornecedor do ativo
    vendor_product_count = 0
    try:
        if getattr(asset, 'vendor', None) and getattr(asset.vendor, 'id', None):
            vendor_product_count = db.session.query(func.count(Product.id)).filter(Product.vendor_id == asset.vendor.id).scalar() or 0
    except Exception:
        vendor_product_count = 0

    # Parse seguro de vendor_ids na URL (suporta múltiplos parâmetros e CSV)
    selected_vendor_ids = []
    try:
        raw_list = request.args.getlist('vendor_ids') or []
        raw_param = request.args.get('vendor_ids')
        parsed: list[int] = []
        if raw_list:
            for item in raw_list:
                for part in str(item).split(','):
                    part = part.strip()
                    if part.isdigit():
                        parsed.append(int(part))
        elif raw_param:
            for part in str(raw_param).split(','):
                part = part.strip()
                if part.isdigit():
                    parsed.append(int(part))
        selected_vendor_ids = sorted(set(parsed))
    except Exception:
        selected_vendor_ids = []

    # Parâmetros de paginação
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', None, type=int)
    try:
        if per_page is None:
            per_page = min(current_app.config.get('PAGINATION_DEFAULT_PER_PAGE', 20), 50)
        else:
            per_page = min(per_page, current_app.config.get('PAGINATION_MAX_PER_PAGE', 100), 50)
    except Exception:
        per_page = 20

    # Vulnerabilidades: exibir todas do fornecedor (vendor) do ativo quando disponível;
    # caso contrário, usar as vulnerabilidades vinculadas ao ativo.
    try:
        from app.models.vulnerability import Vulnerability
        from app.utils.pagination import paginate_query
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

        if getattr(asset, 'vendor', None) and getattr(asset.vendor, 'id', None):
            from sqlalchemy import union
            from app.models.cve_vendor import CVEVendor
            from app.models.cve_product import CVEProduct

            base_vuln_query = db.session.query(Vulnerability)
            cves_por_vendor = (
                db.session
                .query(CVEVendor.cve_id)
                .filter(CVEVendor.vendor_id == asset.vendor.id)
            )
            cves_por_produto_vendor = (
                db.session
                .query(CVEProduct.cve_id)
                .join(Product, Product.id == CVEProduct.product_id)
                .filter(Product.vendor_id == asset.vendor.id)
            )
            cves_unificados_sq = union(cves_por_vendor, cves_por_produto_vendor).subquery()
            base_vuln_query = (
                base_vuln_query
                .filter(Vulnerability.cve_id.in_(db.session.query(cves_unificados_sq.c.cve_id)))
                .distinct()
                .order_by(Vulnerability.published_date.desc())
            )

            pag = paginate_query(base_vuln_query, page=page, per_page=per_page, error_out=False)
            vuln_count = pag.total

            try:
                for v in (pag.items or []):
                    sev = (getattr(v, 'base_severity', None) or '').upper().strip()
                    if sev == 'CRITICAL':
                        severity_counts['critical'] += 1
                    elif sev == 'HIGH':
                        severity_counts['high'] += 1
                    elif sev == 'MEDIUM':
                        severity_counts['medium'] += 1
                    elif sev == 'LOW':
                        severity_counts['low'] += 1
            except Exception:
                pass
        else:
            # Fallback: vulnerabilidades associadas ao ativo
            from app.models.asset_vulnerability import AssetVulnerability
            from sqlalchemy.orm import joinedload
            base_query = (
                db.session.query(AssetVulnerability)
                .options(joinedload(AssetVulnerability.vulnerability))
                .join(Vulnerability, AssetVulnerability.vulnerability_id == Vulnerability.cve_id)
                .filter(AssetVulnerability.asset_id == asset.id)
                .order_by(Vulnerability.published_date.desc())
            )
            pag = paginate_query(base_query, page=page, per_page=per_page, error_out=False)
            vuln_count = pag.total
            try:
                for av in (pag.items or []):
                    v = getattr(av, 'vulnerability', None)
                    sev = (getattr(v, 'base_severity', None) or '').upper().strip()
                    if sev == 'CRITICAL':
                        severity_counts['critical'] += 1
                    elif sev == 'HIGH':
                        severity_counts['high'] += 1
                    elif sev == 'MEDIUM':
                        severity_counts['medium'] += 1
                    elif sev == 'LOW':
                        severity_counts['low'] += 1
            except Exception:
                pass
    except Exception:
        # Fallback seguro: tenta usar len() da relação se houver falha na consulta
        try:
            vuln_count = len(asset.vulnerabilities)
            pag = None
            severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            try:
                for av in (asset.vulnerabilities or []):
                    v = getattr(av, 'vulnerability', None)
                    sev = (getattr(v, 'base_severity', None) or '').upper().strip()
                    if sev == 'CRITICAL':
                        severity_counts['critical'] += 1
                    elif sev == 'HIGH':
                        severity_counts['high'] += 1
                    elif sev == 'MEDIUM':
                        severity_counts['medium'] += 1
                    elif sev == 'LOW':
                        severity_counts['low'] += 1
            except Exception:
                pass
        except Exception:
            vuln_count = 0
            pag = None
            severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

    # Correlacionar CVEs por produto/versão/SO vinculados ao ativo (lista completa)
    try:
        from app.services.vulnerability_service import VulnerabilityService
        vs = VulnerabilityService(db.session)
        vuln_correlated = vs.get_vulnerabilities_by_asset(asset.id) or []
        if len(vuln_correlated) > 200:
            vuln_correlated = vuln_correlated[:200]
        vuln_correlated_count = len(vuln_correlated)
    except Exception:
        vuln_correlated = []
        vuln_correlated_count = 0

    try:
        current_app.logger.debug(f"asset_detail render: vuln_count={vuln_count} correlated={vuln_correlated_count} page={page} per_page={per_page}")
        return render_template(
            'assets/asset_detail.html',
            asset=asset,
            asset_products_safe=asset_products_safe,
            vendor_product_count=vendor_product_count,
            vuln_count=vuln_count,
            vuln_pagination=pag,
            vuln_correlated=vuln_correlated,
            vuln_correlated_count=vuln_correlated_count,
            severity_counts=severity_counts,
            selected_vendor_ids=selected_vendor_ids,
            page=page,
            per_page=(per_page if per_page else None)
        )
    except Exception:
        # Logar stack trace completo para facilitar diagnóstico do erro 500
        try:
            current_app.logger.exception(f"Error rendering asset_detail for asset_id={getattr(asset, 'id', asset_id)}")
        except Exception:
            pass
        # Propagar a exceção para manter o status 500 e o comportamento padrão do Flask
        raise


@asset_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_asset():
    # Em modo público, garantir que login esteja habilitado e exigir autenticação
    try:
        public_mode = current_app.config.get('PUBLIC_MODE', False)
        if public_mode and not current_user.is_authenticated:
            flash('Faça login para cadastrar ativos.', 'error')
            return redirect(url_for('auth.login'))
    except Exception:
        pass
    form = AssetForm()
    # Detecta se a coluna asset_type existe para ajustar exibição do formulário
    try:
        insp = inspect(db.engine)
        colnames = [c['name'] for c in insp.get_columns('assets')]
        has_asset_type_col = ('asset_type' in colnames)
    except Exception:
        has_asset_type_col = True
    # Popular opções de proprietário
    if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
        display_name = (current_user.username or (f"{getattr(current_user, 'first_name', '')} {getattr(current_user, 'last_name', '')}".strip() if (getattr(current_user, 'first_name', '') or getattr(current_user, 'last_name', '')) else current_user.email))
        form.owner_id.choices = [(current_user.id, display_name)]
    else:
        users = User.query.all()
        form.owner_id.choices = [(u.id, (u.username or (f"{u.first_name} {u.last_name}".strip() if (u.first_name or u.last_name) else u.email))) for u in users]
    if form.validate_on_submit():
        # Resolver fornecedor selecionado (apenas vendors Cisco/Fortinet)
        vendor = None
        vendor_id_raw = (form.vendor_id.data.strip() if hasattr(form, 'vendor_id') and form.vendor_id.data else '')
        vendor_name = (form.vendor_name.data.strip() if hasattr(form, 'vendor_name') and form.vendor_name.data else '')
        from sqlalchemy import func
        from app.models.vendor import Vendor
        allowed_vendors = {
            'cisco',
            'fortinet',
            'sophos',
            'palo alto',
            'paloalto',
            'palo alto networks'
        }
        if vendor_id_raw:
            try:
                vendor_id_int = int(vendor_id_raw)
            except ValueError:
                vendor_id_int = None
            if vendor_id_int:
                vendor = Vendor.query.get(vendor_id_int)
                if not vendor:
                    form.vendor_name.errors.append('Fornecedor inválido. Selecione um fornecedor existente.')
                    flash('Fornecedor inválido. Selecione um fornecedor existente.', 'error')
                    return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)
                # Validar nome permitido
                if (vendor.name or '').strip().lower() not in allowed_vendors:
                    form.vendor_name.errors.append('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.')
                    flash('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.', 'error')
                    return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)
        elif vendor_name:
            # Tentar resolver por nome (case-insensitive); se não existir, criar
            existing = Vendor.query.filter(func.lower(Vendor.name) == vendor_name.lower()).first()
            if existing:
                vendor = existing
            else:
                # Permitir criação apenas para vendors especificados
                if vendor_name.strip().lower() not in allowed_vendors:
                    form.vendor_name.errors.append('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.')
                    flash('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.', 'error')
                    return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)
                try:
                    vendor = Vendor(name=vendor_name)
                    db.session.add(vendor)
                    db.session.flush()
                except Exception:
                    vendor = None
                    form.vendor_name.errors.append('Não foi possível criar o fornecedor informado.')
                    flash('Não foi possível criar o fornecedor informado.', 'error')
                    return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)

        # Determinar o owner_id alvo (usuário atual se não-admin, senão escolha do formulário)
        target_owner_id = (
            current_user.id
            if (current_user.is_authenticated and not getattr(current_user, 'is_admin', False))
            else (
                (form.owner_id.data if (hasattr(form, 'owner_id') and form.owner_id.data) else (current_user.id if current_user.is_authenticated else None))
            )
        )

        # Validação proativa: impedir IP duplicado para o mesmo proprietário
        try:
            existing = Asset.query.filter_by(owner_id=target_owner_id, ip_address=form.ip_address.data).first()
        except Exception:
            existing = None
        if existing:
            try:
                conflict_msg = f"Endereço IP já cadastrado nos seus assets: {existing.ip_address} (Ativo: {existing.name} | ID {existing.id})."
            except Exception:
                conflict_msg = 'Endereço IP já cadastrado nos seus assets.'
            flash(conflict_msg, 'error')
            if hasattr(form, 'ip_address'):
                try:
                    form.ip_address.errors.append(
                        f"Este IP já está em uso nos seus assets (Ativo: {getattr(existing, 'name', 'desconhecido')} | ID {getattr(existing, 'id', '?')})."
                    )
                except Exception:
                    form.ip_address.errors.append('Este IP já está em uso nos seus assets.')
            return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)

        # Detecta se a coluna asset_type existe para evitar INSERT com coluna inexistente
        try:
            insp = inspect(db.engine)
            colnames = [c['name'] for c in insp.get_columns('assets')]
            has_asset_type_col = ('asset_type' in colnames)
        except Exception:
            has_asset_type_col = True

        if has_asset_type_col:
            asset = Asset(
                name=form.name.data,
                ip_address=form.ip_address.data,
                status=form.status.data if hasattr(form, 'status') else 'active',
                asset_type=(form.asset_type.data if hasattr(form, 'asset_type') else None),
                owner_id=target_owner_id,
                vendor_id=(vendor.id if vendor else None)
            )
            db.session.add(asset)
        else:
            # Inserção direta via SQL sem a coluna asset_type
            insert_cols = ['name', 'ip_address', 'status', 'owner_id', 'vendor_id']
            params = {
                'name': form.name.data,
                'ip_address': form.ip_address.data,
                'status': (form.status.data if hasattr(form, 'status') else 'active'),
                'owner_id': target_owner_id,
                'vendor_id': (vendor.id if vendor else None),
            }
            placeholders = ', '.join([f":{c}" for c in insert_cols])
            colnames = ', '.join(insert_cols)
            db.session.execute(text(f"INSERT INTO assets ({colnames}) VALUES ({placeholders})"), params)
            # Recupera o ID gerado (SQLite)
            new_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()
            # Carrega o objeto asset sem tentar selecionar a coluna ausente
            try:
                asset = (
                    Asset.query.options(
                        load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id)
                    ).get(new_id)
                )
            except Exception:
                asset = Asset(id=new_id, name=form.name.data, ip_address=form.ip_address.data, status=(form.status.data if hasattr(form, 'status') else 'active'), vendor_id=(vendor.id if vendor else None), owner_id=target_owner_id)
        try:
            # Flush to obtain asset.id before creating linkage
            db.session.flush()

            # Vincular produto ao ativo, com metadados (modelo/SO/versão)
            try:
                # Detecta se a tabela asset_products existe para evitar falhas de vínculo
                try:
                    has_asset_products_table = bool(
                        db.session.execute(
                            text("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_products'")
                        ).scalar()
                    )
                except Exception:
                    has_asset_products_table = True  # fallback conservador

                from app.models.asset_product import AssetProduct
                from app.models.product import Product
                raw_pid = (form.product_id.data or '').strip() if hasattr(form, 'product_id') else ''
                product_id = int(raw_pid) if (raw_pid and raw_pid.isdigit()) else None
                model_name = (form.model_name.data or '').strip() if hasattr(form, 'model_name') else None
                operating_system = (form.operating_system.data or '').strip() if hasattr(form, 'operating_system') else None
                installed_version = (form.installed_version.data or '').strip() if hasattr(form, 'installed_version') else None

                if (product_id or model_name or operating_system or installed_version) and has_asset_products_table:
                    if not product_id and form.product_name.data:
                        # Tentar resolver por nome se ID não foi definido
                        pname = (form.product_name.data or '').strip()
                        if pname and vendor:
                            prod = db.session.query(Product).filter(Product.vendor_id == vendor.id, Product.name == pname).first()
                            product_id = prod.id if prod else None
                    if product_id:
                        link = db.session.query(AssetProduct).filter_by(asset_id=asset.id, product_id=product_id).first()
                        if not link:
                            link = AssetProduct(asset_id=asset.id, product_id=product_id)
                            db.session.add(link)
                        # Atualizar metadados
                        link.model_name = model_name or link.model_name
                        link.operating_system = operating_system or link.operating_system
                        link.installed_version = installed_version or link.installed_version
                    else:
                        # Se não houver product_id, criar link parcial usando product_id nulo não é permitido; apenas registrar metadados no asset via audit log
                        pass
            except Exception:
                # Não bloquear criação caso vínculo falhe
                pass

            db.session.commit()
            # Pós-criação: sincronizar CVEs associadas ao fornecedor do ativo
            try:
                from app.services.vulnerability_service import VulnerabilityService
                vuln_service = VulnerabilityService(db.session)
                created_links = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
                audit_log('sync', 'asset_vulnerabilities', str(asset.id), {'created': created_links})
            except Exception:
                # Não bloquear criação do ativo em caso de falha na sincronização
                pass

            audit_log('create', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
            flash('Ativo criado com sucesso.', 'success')
            return redirect(url_for('asset.asset_detail', asset_id=asset.id))
        except IntegrityError:
            db.session.rollback()
            # Tentar identificar o ativo existente que causou o conflito
            conflict = None
            try:
                conflict = Asset.query.filter_by(owner_id=target_owner_id, ip_address=form.ip_address.data).first()
            except Exception:
                conflict = None
            if conflict:
                flash(
                    f"Endereço IP já cadastrado nos seus assets: {conflict.ip_address} (Ativo: {conflict.name} | ID {conflict.id}).",
                    'error'
                )
                if hasattr(form, 'ip_address'):
                    try:
                        form.ip_address.errors.append(
                            f"Este IP já está em uso nos seus assets (Ativo: {getattr(conflict, 'name', 'desconhecido')} | ID {getattr(conflict, 'id', '?')})."
                        )
                    except Exception:
                        form.ip_address.errors.append('Este IP já está em uso nos seus assets.')
            else:
                flash('Endereço IP já cadastrado nos seus assets.', 'error')
                if hasattr(form, 'ip_address'):
                    form.ip_address.errors.append('Este IP já está em uso nos seus assets.')
    return render_template('assets/asset_form.html', form=form, action='adicionar', has_asset_type_col=has_asset_type_col)


@asset_bp.route('/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
@require_asset_ownership
def edit_asset(asset_id):
    # Detecta se a coluna asset_type existe no banco atual
    try:
        insp = inspect(db.engine)
        colnames = [c['name'] for c in insp.get_columns('assets')]
        has_asset_type_col = ('asset_type' in colnames)
    except Exception:
        has_asset_type_col = True

    opts = []
    if not has_asset_type_col:
        try:
            opts.append(load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id))
        except Exception:
            pass
    try:
        asset = (
            db.session.query(Asset)
            .options(*tuple(opts))
            .filter(Asset.id == asset_id)
            .first()
        )
    except Exception:
        asset = (
            db.session.query(Asset)
            .filter(Asset.id == asset_id)
            .first()
        )
    if asset is None:
        abort(404)

    # Construir formulário evitando acessar asset_type quando a coluna não existe
    if has_asset_type_col:
        form = AssetForm(obj=asset)
    else:
        form = AssetForm()
        try:
            form.name.data = asset.name
            form.ip_address.data = asset.ip_address
            form.status.data = asset.status
            # Não definir form.asset_type
        except Exception:
            pass
    # Preencher defaults de fornecedor no formulário
    try:
        if asset.vendor_id:
            form.vendor_id.data = str(asset.vendor_id)
            if getattr(asset, 'vendor', None):
                form.vendor_name.data = asset.vendor.name
    except Exception:
        pass
    # Popular opções de proprietário
    if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
        display_name = (current_user.username or (f"{getattr(current_user, 'first_name', '')} {getattr(current_user, 'last_name', '')}".strip() if (getattr(current_user, 'first_name', '') or getattr(current_user, 'last_name', '')) else current_user.email))
        form.owner_id.choices = [(current_user.id, display_name)]
    else:
        users = User.query.all()
        form.owner_id.choices = [(u.id, (u.username or (f"{u.first_name} {u.last_name}".strip() if (u.first_name or u.last_name) else u.email))) for u in users]
    if form.validate_on_submit():
        # Preencher campos no objeto (evitar asset_type se coluna ausente)
        if has_asset_type_col:
            form.populate_obj(asset)
        else:
            # Atualização manual segura
            asset.name = form.name.data
            asset.ip_address = form.ip_address.data
            asset.status = form.status.data if hasattr(form, 'status') else asset.status
        # Converter 0 para None no owner_id ou forçar vínculo ao usuário não-admin
        if hasattr(form, 'owner_id'):
            if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
                asset.owner_id = current_user.id
            else:
                asset.owner_id = (form.owner_id.data if form.owner_id.data else (current_user.id if current_user.is_authenticated else asset.owner_id))
        # Resolver fornecedor selecionado (apenas vendors Cisco/Fortinet)
        vendor = None
        vendor_id_raw = (form.vendor_id.data.strip() if hasattr(form, 'vendor_id') and form.vendor_id.data else '')
        vendor_name = (form.vendor_name.data.strip() if hasattr(form, 'vendor_name') and form.vendor_name.data else '')
        from sqlalchemy import func
        from app.models.vendor import Vendor
        allowed_vendors = {'cisco', 'fortinet'}
        if vendor_id_raw:
            try:
                vendor_id_int = int(vendor_id_raw)
            except ValueError:
                vendor_id_int = None
            if vendor_id_int:
                vendor = Vendor.query.get(vendor_id_int)
                if not vendor:
                    form.vendor_name.errors.append('Fornecedor inválido. Selecione um fornecedor existente.')
                    flash('Fornecedor inválido. Selecione um fornecedor existente.', 'error')
                    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
                # Validar nome permitido
                if (vendor.name or '').strip().lower() not in allowed_vendors:
                    form.vendor_name.errors.append('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.')
                    flash('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.', 'error')
                    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
        elif vendor_name:
            # Tentar resolver por nome (case-insensitive); se não existir, criar
            existing = Vendor.query.filter(func.lower(Vendor.name) == vendor_name.lower()).first()
            if existing:
                vendor = existing
            else:
                # Permitir criação apenas para vendors especificados
                if vendor_name.strip().lower() not in allowed_vendors:
                    vendor = None
                    form.vendor_name.errors.append('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.')
                    flash('Apenas Cisco, Fortinet, Sophos e Palo Alto são permitidos no cadastro de ativos.', 'error')
                    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
                try:
                    vendor = Vendor(name=vendor_name)
                    db.session.add(vendor)
                    db.session.flush()
                except Exception:
                    vendor = None
                    form.vendor_name.errors.append('Não foi possível criar o fornecedor informado.')
                    flash('Não foi possível criar o fornecedor informado.', 'error')
                    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')

        # Validação proativa: impedir IP duplicado para o mesmo proprietário ao editar
        try:
            duplicate = (
                Asset.query
                .filter(Asset.owner_id == asset.owner_id)
                .filter(Asset.ip_address == form.ip_address.data)
                .filter(Asset.id != asset.id)
                .first()
            )
        except Exception:
            duplicate = None
        if duplicate:
            try:
                conflict_msg = f"Endereço IP duplicado nos seus assets: {duplicate.ip_address} (Ativo: {duplicate.name} | ID {duplicate.id})."
            except Exception:
                conflict_msg = 'Endereço IP duplicado nos seus assets.'
            flash(conflict_msg, 'error')
            if hasattr(form, 'ip_address'):
                try:
                    form.ip_address.errors.append(
                        f"Este IP já está em uso nos seus assets (Ativo: {getattr(duplicate, 'name', 'desconhecido')} | ID {getattr(duplicate, 'id', '?')})."
                    )
                except Exception:
                    form.ip_address.errors.append('Este IP já está em uso nos seus assets.')
            return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
        asset.vendor_id = vendor.id if vendor else None
        try:
            db.session.flush()
            # Upsert vínculo AssetProduct
            try:
                # Detecta se a tabela asset_products existe para evitar falhas de vínculo
                try:
                    has_asset_products_table = bool(
                        db.session.execute(
                            text("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_products'")
                        ).scalar()
                    )
                except Exception:
                    has_asset_products_table = True  # fallback conservador
                from app.models.asset_product import AssetProduct
                from app.models.product import Product
                raw_pid = (form.product_id.data or '').strip() if hasattr(form, 'product_id') else ''
                product_id = int(raw_pid) if (raw_pid and raw_pid.isdigit()) else None
                model_name = (form.model_name.data or '').strip() if hasattr(form, 'model_name') else None
                operating_system = (form.operating_system.data or '').strip() if hasattr(form, 'operating_system') else None
                installed_version = (form.installed_version.data or '').strip() if hasattr(form, 'installed_version') else None

                if (product_id or model_name or operating_system or installed_version) and has_asset_products_table:
                    if not product_id and form.product_name.data:
                        pname = (form.product_name.data or '').strip()
                        if pname and asset.vendor_id:
                            prod = db.session.query(Product).filter(Product.vendor_id == asset.vendor_id, Product.name == pname).first()
                            product_id = prod.id if prod else None
                    if product_id:
                        link = db.session.query(AssetProduct).filter_by(asset_id=asset.id, product_id=product_id).first()
                        if not link:
                            link = AssetProduct(asset_id=asset.id, product_id=product_id)
                            db.session.add(link)
                        link.model_name = model_name or link.model_name
                        link.operating_system = operating_system or link.operating_system
                        link.installed_version = installed_version or link.installed_version
            except Exception:
                pass

            db.session.commit()
            # Pós-atualização: re-sincronizar CVEs associadas ao fornecedor
            try:
                from app.services.vulnerability_service import VulnerabilityService
                vuln_service = VulnerabilityService(db.session)
                created_links = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
                audit_log('sync', 'asset_vulnerabilities', str(asset.id), {'created': created_links})
            except Exception:
                pass
            audit_log('update', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
            flash('Ativo atualizado com sucesso.', 'success')
            return redirect(url_for('asset.list_assets'))
        except IntegrityError:
            db.session.rollback()
            # Tentar identificar o ativo existente que causou o conflito
            conflict = None
            try:
                conflict = (
                    Asset.query
                    .filter(Asset.owner_id == asset.owner_id)
                    .filter(Asset.ip_address == form.ip_address.data)
                    .filter(Asset.id != asset.id)
                    .first()
                )
            except Exception:
                conflict = None
            if conflict:
                flash(
                    f"Endereço IP já cadastrado para outro ativo: {conflict.ip_address} (Ativo: {conflict.name} | ID {conflict.id}).",
                    'error'
                )
                if hasattr(form, 'ip_address'):
                    try:
                        form.ip_address.errors.append(
                            f"Endereço IP já está em uso (Ativo: {getattr(conflict, 'name', 'desconhecido')} | ID {getattr(conflict, 'id', '?')})."
                        )
                    except Exception:
                        form.ip_address.errors.append('Endereço IP já está em uso.')
            else:
                flash('Endereço IP já cadastrado para outro ativo.', 'error')
                if hasattr(form, 'ip_address'):
                    form.ip_address.errors.append('Endereço IP já está em uso.')
    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar', has_asset_type_col=has_asset_type_col)


@asset_bp.route('/<int:asset_id>/delete', methods=['POST'])
@login_required
@require_asset_ownership
def delete_asset(asset_id):
    wants_json = False
    try:
        wants_json = (
            'application/json' in ((request.headers.get('Accept', '') or '').lower())
        ) or (
            request.headers.get('X-Requested-With', '') == 'XMLHttpRequest'
        )
    except Exception:
        wants_json = False

    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)
    try:
        audit_log('delete', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
        db.session.delete(asset)
        db.session.commit()
        flash('Ativo removido com sucesso.', 'success')
        if wants_json:
            return jsonify({'status': 'success', 'message': 'Ativo removido com sucesso.', 'asset_id': asset_id}), 200
        return redirect(url_for('asset.list_assets'))
    except IntegrityError:
        db.session.rollback()
        if wants_json:
            return jsonify({'status': 'error', 'message': 'Erro ao remover ativo.'}), 400
        flash('Erro ao remover ativo.', 'danger')
        return redirect(url_for('asset.asset_detail', asset_id=asset_id))


@asset_bp.route('/<int:asset_id>/sync_vulnerabilities', methods=['POST'])
@login_required
@require_asset_ownership
def sync_asset_vulnerabilities(asset_id):
    from app.services.vulnerability_service import VulnerabilityService
    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)
    vuln_service = VulnerabilityService(db.session)
    try:
        created = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
        audit_log('sync', 'asset_vulnerabilities', str(asset.id), {'created': created})
        return jsonify({'status': 'success', 'created': created}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@asset_bp.route('/<int:asset_id>/analysis', methods=['GET'])
@login_required
@require_asset_ownership
def asset_analysis(asset_id):
    from app.services.vulnerability_service import VulnerabilityService
    from app.models.asset_product import AssetProduct
    from app.models.product import Product
    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)
    svc = VulnerabilityService(db.session)
    try:
        vulns = svc.get_vulnerabilities_by_asset(asset.id)
        products = (
            db.session.query(AssetProduct, Product)
            .join(Product, Product.id == AssetProduct.product_id)
            .filter(AssetProduct.asset_id == asset.id)
            .all()
        )
        product_evidence = []
        for ap, p in products:
            product_evidence.append({
                'product_id': p.id,
                'product_name': p.name,
                'vendor_id': getattr(p, 'vendor_id', None),
                'installed_version': ap.installed_version,
                'model_name': ap.model_name,
                'operating_system': ap.operating_system,
            })
        items = []
        for v in vulns:
            items.append({
                'cve_id': v.cve_id,
                'severity': v.base_severity,
                'cvss_score': v.cvss_score,
                'patch_available': bool(getattr(v, 'patch_available', False)),
                'description': v.description,
            })
        return jsonify({
            'status': 'success',
            'asset': {
                'id': asset.id,
                'name': asset.name,
                'ip_address': asset.ip_address,
            },
            'evidence': {
                'products': product_evidence
            },
            'vulnerabilities': items,
            'count': len(items)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@asset_bp.route('/<int:asset_id>/link-product', methods=['POST'])
@login_required
@require_asset_ownership
def link_product(asset_id):
    """Vincula um produto existente ao ativo e atualiza metadados opcionais.

    Espera os campos: product_id (obrigatório), model_name, operating_system, installed_version (opcionais).
    """
    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)

    # Detectar intenção de resposta JSON para AJAX
    wants_json = False
    try:
        wants_json = (
            'application/json' in ((request.headers.get('Accept', '') or '').lower())
        ) or (
            request.headers.get('X-Requested-With', '') == 'XMLHttpRequest'
        )
    except Exception:
        wants_json = False

    # Extrair dados do formulário ou JSON
    raw_pid = None
    model_name = None
    operating_system = None
    installed_version = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        raw_pid = (str(data.get('product_id')) if data.get('product_id') is not None else None)
        model_name = (data.get('model_name') or '').strip() or None
        operating_system = (data.get('operating_system') or '').strip() or None
        installed_version = (data.get('installed_version') or '').strip() or None
    else:
        raw_pid = (request.form.get('product_id') or '').strip() or None
        model_name = (request.form.get('model_name') or '').strip() or None
        operating_system = (request.form.get('operating_system') or '').strip() or None
        installed_version = (request.form.get('installed_version') or '').strip() or None

    # Validar product_id
    product_id = None
    try:
        if raw_pid and str(raw_pid).isdigit():
            product_id = int(raw_pid)
    except Exception:
        product_id = None

    if not product_id:
        msg = 'Produto inválido. Selecione um produto existente do fornecedor.'
        if wants_json:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('asset.asset_detail', asset_id=asset.id))

    # Resolver produto e validar fornecedor
    from app.models.product import Product
    from app.models.asset_product import AssetProduct
    product = db.session.query(Product).get(product_id)
    if not product:
        msg = 'Produto não encontrado.'
        if wants_json:
            return jsonify({'status': 'error', 'message': msg}), 404
        flash(msg, 'error')
        return redirect(url_for('asset.asset_detail', asset_id=asset.id))

    # Se o ativo tem fornecedor definido, o produto deve pertencer ao mesmo fornecedor
    if asset.vendor_id and product.vendor_id != asset.vendor_id:
        msg = 'Produto não pertence ao fornecedor do ativo.'
        if wants_json:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('asset.asset_detail', asset_id=asset.id))

    # Verificar existência da tabela asset_products para evitar falhas em ambientes sem migração
    try:
        has_asset_products_table = bool(
            db.session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_products'")
            ).scalar()
        )
    except Exception:
        has_asset_products_table = True  # fallback conservador

    # Upsert do vínculo AssetProduct
    try:
        if not has_asset_products_table:
            msg = 'Tabela de vínculos asset_products ausente. Execute a migração primeiro.'
            if wants_json:
                return jsonify({'status': 'error', 'message': msg}), 503
            flash(msg, 'error')
            return redirect(url_for('asset.asset_detail', asset_id=asset.id))

        link = db.session.query(AssetProduct).filter_by(asset_id=asset.id, product_id=product.id).first()
        if not link:
            link = AssetProduct(asset_id=asset.id, product_id=product.id)
            db.session.add(link)
        # Atualizar metadados opcionais
        link.model_name = model_name or link.model_name
        link.operating_system = operating_system or link.operating_system
        link.installed_version = installed_version or link.installed_version

        db.session.commit()

        # Sincronizar CVEs associadas ao fornecedor após vínculo
        try:
            from app.services.vulnerability_service import VulnerabilityService
            vuln_service = VulnerabilityService(db.session)
            created_links = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
            audit_log('sync', 'asset_vulnerabilities', str(asset.id), {'created': created_links})
        except Exception:
            pass

        audit_log('link', 'asset_product', f"{asset.id}:{product.id}", {
            'asset_id': asset.id,
            'product_id': product.id,
            'model_name': link.model_name,
            'operating_system': link.operating_system,
            'installed_version': link.installed_version,
        })

        if wants_json:
            return jsonify({'status': 'success', 'message': 'Produto vinculado ao ativo com sucesso.'}), 200
        flash('Produto vinculado ao ativo com sucesso.', 'success')
        return redirect(url_for('asset.asset_detail', asset_id=asset.id))
    except IntegrityError:
        db.session.rollback()
        msg = 'Erro ao vincular produto ao ativo.'
        if wants_json:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('asset.asset_detail', asset_id=asset.id))


@asset_bp.route('/<int:asset_id>/ping', methods=['POST'])
@login_required
@require_asset_ownership
def ping_asset(asset_id):
    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    ip = (payload.get('ip') or asset.ip_address or '').strip()
    try:
        import ipaddress
        ipaddress.ip_address(ip)
    except Exception:
        return jsonify({'status': 'error', 'message': 'IP inválido', 'reachable': False}), 400
    reachable = False
    latency_ms = None
    import platform, subprocess, time
    try:
        if platform.system().lower().startswith('win'):
            args = ["ping", "-n", "1", "-w", "2000", ip]
        else:
            args = ["ping", "-c", "1", "-W", "2", ip]
        t0 = time.time()
        proc = subprocess.run(args, capture_output=True, timeout=5)
        dt = (time.time() - t0) * 1000.0
        reachable = (proc.returncode == 0)
        latency_ms = round(dt, 1)
    except Exception:
        reachable = False
    if not reachable:
        try:
            import socket
            for p in (80, 443, 22):
                try:
                    s = socket.create_connection((ip, p), timeout=1.0)
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    s.close()
                    reachable = True
                    break
                except Exception:
                    continue
        except Exception:
            pass
    audit_log('network', 'ping', str(asset.id), {'ip': ip, 'reachable': reachable, 'latency_ms': latency_ms})
    return jsonify({'reachable': reachable, 'latency_ms': latency_ms}), 200


@asset_bp.route('/<int:asset_id>/scan_ports', methods=['POST'])
@login_required
@require_asset_ownership
def scan_ports(asset_id):
    asset = db.session.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        abort(404)
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    ip = (payload.get('ip') or asset.ip_address or '').strip()
    try:
        import ipaddress
        ipaddress.ip_address(ip)
    except Exception:
        return jsonify({'success': False, 'status': 'error', 'error': 'IP inválido'}), 400
    ports = payload.get('ports') or [22, 80, 443, 53, 3389, 25, 110]
    results = []
    open_count = 0
    try:
        import socket
        for p in ports:
            status = 'closed'
            try:
                s = socket.create_connection((ip, int(p)), timeout=0.7)
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                s.close()
                status = 'open'
                open_count += 1
            except Exception:
                status = 'closed'
            results.append({'port': int(p), 'status': status})
        audit_log('network', 'port_scan', str(asset.id), {'ip': ip, 'open_count': open_count})
        return jsonify({'success': True, 'results': results, 'open_count': open_count}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'status': 'error', 'error': str(e)}), 500

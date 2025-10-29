from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions.middleware import require_asset_ownership, audit_log
from sqlalchemy.exc import IntegrityError

from app.models.asset import Asset
from app.extensions import db
from app.forms.asset_form import AssetForm
from app.models.user import User

asset_bp = Blueprint('asset', __name__, url_prefix='/assets')


@asset_bp.route('/')
def list_assets():
    # Mostrar apenas assets do usuário atual (ou nenhum se não autenticado)
    from app.extensions.middleware import filter_by_user_assets
    query = filter_by_user_assets(Asset.query)
    assets = query.all()
    return render_template('assets/asset_list.html', assets=assets)


@asset_bp.route('/<int:asset_id>', methods=['GET'])
@login_required
@require_asset_ownership
def asset_detail(asset_id):
    """Renderiza a página de detalhes do ativo (apenas do proprietário ou admin)."""
    asset = Asset.query.get_or_404(asset_id)
    return render_template('assets/asset_detail.html', asset=asset)


@asset_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_asset():
    form = AssetForm()
    # Popular opções de proprietário
    if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
        display_name = (current_user.username or (f"{getattr(current_user, 'first_name', '')} {getattr(current_user, 'last_name', '')}".strip() if (getattr(current_user, 'first_name', '') or getattr(current_user, 'last_name', '')) else current_user.email))
        form.owner_id.choices = [(current_user.id, display_name)]
    else:
        users = User.query.all()
        form.owner_id.choices = [(0, 'Nenhum')] + [(u.id, (u.username or (f"{u.first_name} {u.last_name}".strip() if (u.first_name or u.last_name) else u.email))) for u in users]
    if form.validate_on_submit():
        # Resolver fornecedor selecionado (apenas vendors existentes)
        vendor = None
        vendor_id_raw = (form.vendor_id.data.strip() if hasattr(form, 'vendor_id') and form.vendor_id.data else '')
        vendor_name = (form.vendor_name.data.strip() if hasattr(form, 'vendor_name') and form.vendor_name.data else '')
        if vendor_id_raw:
            try:
                vendor_id_int = int(vendor_id_raw)
            except ValueError:
                vendor_id_int = None
            if vendor_id_int:
                from app.models.vendor import Vendor
                vendor = Vendor.query.get(vendor_id_int)
                if not vendor:
                    form.vendor_name.errors.append('Fornecedor inválido. Selecione um fornecedor existente.')
                    flash('Fornecedor inválido. Selecione um fornecedor existente.', 'error')
                    return render_template('assets/asset_form.html', form=form, action='adicionar')
        elif vendor_name:
            form.vendor_name.errors.append('Selecione um fornecedor existente da lista.')
            flash('Selecione um fornecedor existente da lista.', 'error')
            return render_template('assets/asset_form.html', form=form, action='adicionar')

        asset = Asset(
            name=form.name.data,
            ip_address=form.ip_address.data,
            status=form.status.data if hasattr(form, 'status') else 'active',
            owner_id=(current_user.id if (current_user.is_authenticated and not getattr(current_user, 'is_admin', False)) else (None if (not hasattr(form, 'owner_id') or not form.owner_id.data or form.owner_id.data == 0) else form.owner_id.data)),
            vendor_id=(vendor.id if vendor else None)
        )
        db.session.add(asset)
        try:
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
            flash('Endereço IP já cadastrado para outro ativo.', 'error')
            if hasattr(form, 'ip_address'):
                form.ip_address.errors.append('Endereço IP já está em uso.')
    return render_template('assets/asset_form.html', form=form, action='adicionar')


@asset_bp.route('/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
@require_asset_ownership
def edit_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    form = AssetForm(obj=asset)
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
        form.owner_id.choices = [(0, 'Nenhum')] + [(u.id, (u.username or (f"{u.first_name} {u.last_name}".strip() if (u.first_name or u.last_name) else u.email))) for u in users]
    if form.validate_on_submit():
        # Preencher campos no objeto
        form.populate_obj(asset)
        # Converter 0 para None no owner_id ou forçar vínculo ao usuário não-admin
        if hasattr(form, 'owner_id'):
            if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
                asset.owner_id = current_user.id
            else:
                asset.owner_id = None if (not form.owner_id.data or form.owner_id.data == 0) else form.owner_id.data
        # Resolver fornecedor selecionado (apenas vendors existentes)
        vendor = None
        vendor_id_raw = (form.vendor_id.data.strip() if hasattr(form, 'vendor_id') and form.vendor_id.data else '')
        vendor_name = (form.vendor_name.data.strip() if hasattr(form, 'vendor_name') and form.vendor_name.data else '')
        if vendor_id_raw:
            try:
                vendor_id_int = int(vendor_id_raw)
            except ValueError:
                vendor_id_int = None
            if vendor_id_int:
                from app.models.vendor import Vendor
                vendor = Vendor.query.get(vendor_id_int)
                if not vendor:
                    form.vendor_name.errors.append('Fornecedor inválido. Selecione um fornecedor existente.')
                    flash('Fornecedor inválido. Selecione um fornecedor existente.', 'error')
                    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
        elif vendor_name:
            form.vendor_name.errors.append('Selecione um fornecedor existente da lista.')
            flash('Selecione um fornecedor existente da lista.', 'error')
            return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')
        asset.vendor_id = vendor.id if vendor else None
        try:
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
            flash('Endereço IP já cadastrado para outro ativo.', 'error')
            if hasattr(form, 'ip_address'):
                form.ip_address.errors.append('Endereço IP já está em uso.')
    return render_template('assets/asset_form.html', form=form, asset=asset, action='editar')


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

    asset = Asset.query.get_or_404(asset_id)
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
    """Sincroniza vulnerabilidades associadas ao fornecedor do ativo."""
    from app.services.vulnerability_service import VulnerabilityService
    asset = Asset.query.get_or_404(asset_id)
    vuln_service = VulnerabilityService(db.session)
    try:
        created = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
        audit_log('sync', 'asset_vulnerabilities', str(asset.id), {'created': created})
        return jsonify({'status': 'success', 'created': created}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

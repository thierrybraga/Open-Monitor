from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions.middleware import require_asset_ownership, audit_log

from models.asset import Asset
from extensions import db
from forms.asset_form import AssetForm

asset_bp = Blueprint('asset', __name__, url_prefix='/assets')


@asset_bp.route('/')
@login_required
def list_assets():
    # Filtrar assets apenas do usuário logado
    assets = Asset.query.filter_by(owner_id=current_user.id).all()
    return render_template('assets/asset_list.html', assets=assets)


@asset_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_asset():
    form = AssetForm()
    if form.validate_on_submit():
        asset = Asset(
            name=form.name.data,
            ip_address=form.ip_address.data,
            status=form.status.data if hasattr(form, 'status') else 'active',
            owner_id=current_user.id  # Associar ao usuário logado
        )
        db.session.add(asset)
        db.session.commit()
        audit_log('create', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
        flash('Ativo criado com sucesso.', 'success')
        return redirect(url_for('asset.list_assets'))
    return render_template('assets/asset_form.html', form=form)


@asset_bp.route('/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
@require_asset_ownership
def edit_asset(asset_id):
    # Garantir que o usuário só pode editar seus próprios assets
    asset = Asset.query.filter_by(id=asset_id, owner_id=current_user.id).first_or_404()
    form = AssetForm(obj=asset)
    if form.validate_on_submit():
        form.populate_obj(asset)
        db.session.commit()
        audit_log('update', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
        flash('Ativo atualizado com sucesso.', 'success')
        return redirect(url_for('asset.list_assets'))
    return render_template('assets/asset_form.html', form=form, asset=asset)


@asset_bp.route('/<int:asset_id>/delete', methods=['POST'])
@login_required
@require_asset_ownership
def delete_asset(asset_id):
    # Garantir que o usuário só pode deletar seus próprios assets
    asset = Asset.query.filter_by(id=asset_id, owner_id=current_user.id).first_or_404()
    audit_log('delete', 'asset', str(asset.id), {'name': asset.name, 'ip': asset.ip_address})
    db.session.delete(asset)
    db.session.commit()
    flash('Ativo removido com sucesso.', 'success')
    return redirect(url_for('asset.list_assets'))
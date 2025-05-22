from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..models.asset import Asset
from ..extensions import db
from ..forms.asset_form import AssetForm

asset_bp = Blueprint('asset', __name__, url_prefix='/assets')


@asset_bp.route('/')
@login_required
def list_assets():
    assets = Asset.query.all()
    return render_template('assets/asset_list.html', assets=assets)


@asset_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_asset():
    form = AssetForm()
    if form.validate_on_submit():
        asset = Asset(
            name=form.name.data,
            description=form.description.data,
            ip_address=form.ip_address.data,
            hostname=form.hostname.data,
            owner=form.owner.data,
        )
        db.session.add(asset)
        db.session.commit()
        flash('Ativo criado com sucesso.', 'success')
        return redirect(url_for('asset.list_assets'))
    return render_template('assets/asset_form.html', form=form)


@asset_bp.route('/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    form = AssetForm(obj=asset)
    if form.validate_on_submit():
        form.populate_obj(asset)
        db.session.commit()
        flash('Ativo atualizado com sucesso.', 'success')
        return redirect(url_for('asset.list_assets'))
    return render_template('assets/asset_form.html', form=form, asset=asset)


@asset_bp.route('/<int:asset_id>/delete', methods=['POST'])
@login_required
def delete_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    db.session.delete(asset)
    db.session.commit()
    flash('Ativo removido com sucesso.', 'success')
    return redirect(url_for('asset.list_assets'))
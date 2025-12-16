# controllers/monitoring_controller.py

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.monitoring_rule import MonitoringRule
from app.models.asset import Asset
from app.forms.monitoring_form import MonitoringRuleForm
from typing import Any

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

@monitoring_bp.route('/', methods=['GET'])
@login_required
def monitoring_home() -> Any:
    """
    Dashboard de monitoramento: lista todas as regras do usuário.
    """
    try:
        rules = MonitoringRule.query.filter(MonitoringRule.user_id == current_user.id).order_by(MonitoringRule.id.desc()).all()
        from app.extensions.middleware import filter_by_user_assets
        assets = filter_by_user_assets(Asset.query).order_by(Asset.ip_address.asc()).all()
        current_app.logger.info(f"[Monitoring] fetched {len(rules)} rules and {len(assets)} assets")

        online_aliases = {'active', 'online', 'up'}
        offline_aliases = {'inactive', 'offline', 'down'}
        warning_aliases = {'warning', 'degraded', 'maintenance'}
        norm = lambda s: (s or '').strip().lower()
        metrics_counts = {
            'total': len(assets),
            'online': sum(1 for a in assets if norm(a.status) in online_aliases),
            'offline': sum(1 for a in assets if norm(a.status) in offline_aliases),
            'warning': sum(1 for a in assets if norm(a.status) in warning_aliases),
        }
    except SQLAlchemyError as e:
        current_app.logger.error("DB error fetching monitoring data", exc_info=e)
        flash('Erro ao carregar dados de monitoramento.', 'danger')
        rules = []
        assets = []
        metrics_counts = {'total': 0, 'online': 0, 'offline': 0, 'warning': 0}
    return render_template(
        'monitoring/monitoring.html',
        monitoring_rules=rules,
        assets=assets,
        metrics_counts=metrics_counts,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY', '')
    )

@monitoring_bp.route('/rules/<int:rule_id>', methods=['GET'])
@login_required
def view_rule(rule_id: int) -> Any:
    """
    Exibe detalhes de uma regra específica.
    """
    rule = MonitoringRule.query.get_or_404(rule_id)
    if rule.user_id != current_user.id:
        flash('Acesso negado à regra solicitada.', 'danger')
        return redirect(url_for('monitoring.monitoring_home'))
    current_app.logger.info(f"[Monitoring] view rule={rule_id}")
    flash('Visualização detalhada ainda não disponível. Redirecionando para a página de monitoramento.', 'warning')
    return redirect(url_for('monitoring.monitoring_home'))

@monitoring_bp.route('/rules/create', methods=['GET', 'POST'])
@login_required
def create_rule() -> Any:
    """
    Cria uma nova regra de monitoramento via formulário.
    """
    form = MonitoringRuleForm()
    if form.validate_on_submit():
        rule = MonitoringRule(
            name=form.name.data,
            parameters=form.parameters.data,
            user_id=current_user.id
        )
        try:
            with db.session.begin():
                db.session.add(rule)
            flash('Regra de monitoramento criada com sucesso.', 'success')
            current_app.logger.info(f"[Monitoring] created rule={rule.id}")
            return redirect(url_for('monitoring.monitoring_home'))
        except SQLAlchemyError as e:
            flash('Erro ao criar regra.', 'danger')
            current_app.logger.error("DB error creating monitoring rule", exc_info=e)
    return render_template('monitoring/monitoring_rule_form.html', form=form, action='create')

@monitoring_bp.route('/rules/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_rule(rule_id: int) -> Any:
    """
    Edita uma regra existente.
    """
    rule = MonitoringRule.query.get_or_404(rule_id)
    if rule.user_id != current_user.id:
        flash('Acesso negado à regra solicitada.', 'danger')
        return redirect(url_for('monitoring.monitoring_home'))
    form = MonitoringRuleForm(obj=rule)
    if form.validate_on_submit():
        form.populate_obj(rule)
        try:
            with db.session.begin():
                db.session.merge(rule)
            flash('Regra atualizada com sucesso.', 'success')
            current_app.logger.info(f"[Monitoring] updated rule={rule_id}")
            return redirect(url_for('monitoring.view_rule', rule_id=rule_id))
        except SQLAlchemyError as e:
            flash('Erro ao atualizar regra.', 'danger')
            current_app.logger.error("DB error updating monitoring rule", exc_info=e)
    return render_template('monitoring/monitoring_rule_form.html', form=form, action='edit', rule=rule)

@monitoring_bp.route('/rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete_rule(rule_id: int) -> Any:
    """
    Exclui uma regra de monitoramento.
    """
    rule = MonitoringRule.query.get_or_404(rule_id)
    if rule.user_id != current_user.id:
        flash('Acesso negado à regra solicitada.', 'danger')
        return redirect(url_for('monitoring.monitoring_home'))
    try:
        with db.session.begin():
            db.session.delete(rule)
        flash('Regra removida.', 'success')
        current_app.logger.info(f"[Monitoring] deleted rule={rule_id}")
    except SQLAlchemyError as e:
        flash('Erro ao remover regra.', 'danger')
        current_app.logger.error("DB error deleting monitoring rule", exc_info=e)
    return redirect(url_for('monitoring.monitoring_home'))

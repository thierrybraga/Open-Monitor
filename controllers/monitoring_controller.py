# controllers/monitoring_controller.py

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..models.monitoring_rule import MonitoringRule
from ..forms.monitoring_form import MonitoringRuleForm  # novo Flask-WTF form
from typing import Any

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

@monitoring_bp.route('/', methods=['GET'])
@login_required
def monitoring_home() -> Any:
    """
    Dashboard de monitoramento: lista todas as regras do usuário.
    """
    try:
        rules = MonitoringRule.query.filter_by(user_id=current_user.id).order_by(MonitoringRule.id.desc()).all()
        current_app.logger.info(f"[Monitoring] user={current_user.id} fetched {len(rules)} rules")
    except SQLAlchemyError as e:
        current_app.logger.error("DB error fetching monitoring rules", exc_info=e)
        flash('Erro ao carregar regras de monitoramento.', 'danger')
        rules = []
    return render_template(
        'monitoring.html',
        monitoring_rules=rules,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY', '')
    )

@monitoring_bp.route('/rules/<int:rule_id>', methods=['GET'])
@login_required
def view_rule(rule_id: int) -> Any:
    """
    Exibe detalhes de uma regra específica.
    """
    rule = MonitoringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    current_app.logger.info(f"[Monitoring] user={current_user.id} view rule={rule_id}")
    return render_template('monitoring_rule_detail.html', rule=rule)

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
            current_app.logger.info(f"[Monitoring] user={current_user.id} created rule={rule.id}")
            return redirect(url_for('monitoring.monitoring_home'))
        except SQLAlchemyError as e:
            flash('Erro ao criar regra.', 'danger')
            current_app.logger.error("DB error creating monitoring rule", exc_info=e)
    return render_template('monitoring_rule_form.html', form=form, action='create')

@monitoring_bp.route('/rules/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_rule(rule_id: int) -> Any:
    """
    Edita uma regra existente.
    """
    rule = MonitoringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    form = MonitoringRuleForm(obj=rule)
    if form.validate_on_submit():
        form.populate_obj(rule)
        try:
            with db.session.begin():
                db.session.merge(rule)
            flash('Regra atualizada com sucesso.', 'success')
            current_app.logger.info(f"[Monitoring] user={current_user.id} updated rule={rule_id}")
            return redirect(url_for('monitoring.view_rule', rule_id=rule_id))
        except SQLAlchemyError as e:
            flash('Erro ao atualizar regra.', 'danger')
            current_app.logger.error("DB error updating monitoring rule", exc_info=e)
    return render_template('monitoring_rule_form.html', form=form, action='edit', rule=rule)

@monitoring_bp.route('/rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete_rule(rule_id: int) -> Any:
    """
    Exclui uma regra de monitoramento.
    """
    rule = MonitoringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    try:
        with db.session.begin():
            db.session.delete(rule)
        flash('Regra removida.', 'success')
        current_app.logger.info(f"[Monitoring] user={current_user.id} deleted rule={rule_id}")
    except SQLAlchemyError as e:
        flash('Erro ao remover regra.', 'danger')
        current_app.logger.error("DB error deleting monitoring rule", exc_info=e)
    return redirect(url_for('monitoring.monitoring_home'))

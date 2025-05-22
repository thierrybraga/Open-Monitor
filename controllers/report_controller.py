# controllers/report_controller.py

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from ..extensions.db import db
from ..models.report import Report
from ..services.report_service import generate_report as svc_generate_report
from ..forms.report_form import ReportFilterForm  # Flask-WTF form
from typing import Any
from werkzeug.datastructures import MultiDict

report_bp = Blueprint('report', __name__, url_prefix='/reports')

@report_bp.route('/', methods=['GET'])
@login_required
def list_reports() -> Any:
    """
    Lista todos os relatórios gerados pelo usuário.
    """
    reports = Report.query.filter_by(owner_id=current_user.id)\
                         .order_by(Report.created_at.desc())\
                         .all()
    current_app.logger.info(f"[Reports] user={current_user.id} list {len(reports)} reports")
    return render_template('report.html', reports=reports)


@report_bp.route('/<int:report_id>', methods=['GET'])
@login_required
def view_report(report_id: int) -> Any:
    """
    Exibe detalhes de um relatório específico.
    """
    report = Report.query.filter_by(id=report_id, owner_id=current_user.id).first()
    if not report:
        flash('Relatório não encontrado.', 'danger')
        current_app.logger.warning(f"[Reports] user={current_user.id} report={report_id} not found")
        return redirect(url_for('report.list_reports'))
    return render_template('report_detail.html', report=report)


@report_bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate_report_view() -> Any:
    """
    Formulário para gerar novo relatório. Em POST, invoca o serviço e salva o Report.
    """
    form = ReportFilterForm(formdata=MultiDict(request.form) if request.method == 'POST' else None)
    if form.validate_on_submit():
        filters = {
            'start_date': form.start_date.data,
            'end_date':   form.end_date.data,
            'severity':   form.severity.data,
            'vendor':     form.vendor.data
        }
        current_app.logger.info(f"[Reports] user={current_user.id} generating with {filters}")
        try:
            # chama a camada de serviço que retorna instância Report
            new_report = svc_generate_report(owner_id=current_user.id, filters=filters)
            with db.session.begin():
                db.session.add(new_report)
            flash('Relatório gerado com sucesso.', 'success')
            return redirect(url_for('report.view_report', report_id=new_report.id))
        except SQLAlchemyError as db_err:
            flash('Erro ao salvar relatório.', 'danger')
            current_app.logger.error("DB error saving report", exc_info=db_err)
        except Exception as srv_err:
            flash('Falha ao gerar relatório. Tente novamente.', 'danger')
            current_app.logger.error("Service error generating report", exc_info=srv_err)

    # em GET ou validação falha
    if form.errors:
        for field, errs in form.errors.items():
            for e in errs:
                flash(f"{getattr(form, field).label.text}: {e}", 'danger')

    return render_template('report_form.html', form=form)

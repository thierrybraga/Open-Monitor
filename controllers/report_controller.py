# controllers/report_controller.py

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from extensions.db import db
from models.vulnerability import Vulnerability
from models.report import Report
from models.affected_product import AffectedProduct
from models.product import Product
from models.vendor import Vendor
from services.report_service import generate_report as svc_generate_report
from forms.report_form import ReportFilterForm
from typing import Any
from werkzeug.datastructures import MultiDict

report_bp = Blueprint('report', __name__, url_prefix='/reports')

@report_bp.route('/', methods=['GET'])
@login_required
def list_reports() -> Any:
    """
    List all reports with filtering and pagination.
    """
    from models.vulnerability import Vulnerability
    from datetime import datetime
    
    # Get filter parameters from request
    severity = request.args.get('severity', '')
    vendor = request.args.get('vendor', '')
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query with filters
    query = Vulnerability.query
    
    if severity:
        query = query.filter(Vulnerability.base_severity == severity)
    
    if vendor:
        # Filter by vendor through the relationship with affected_products
        query = query.join(Vulnerability.affected_products).join(AffectedProduct.product).join(Product.vendor).filter(
            Vendor.name.ilike(f'%{vendor}%')
        )
    
    if date_start:
        try:
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date >= start_date)
        except ValueError:
            pass
    
    if date_end:
        try:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date <= end_date)
        except ValueError:
            pass
    
    # Get paginated results
    pagination = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    vulnerabilities = pagination.items
    total_pages = pagination.pages
    total_vuln_count = pagination.total
    
    # Get unique vendors for filter dropdown
    vendors_query = db.session.query(Vendor.name).join(Vendor.products).join(Product.affected_products).distinct()
    vendors = sorted([v[0] for v in vendors_query.all() if v[0]])
    
    # Prepare filter data
    filters = {
        'severity': severity,
        'vendor': vendor,
        'date_start': date_start,
        'date_end': date_end
    }
    
    # Current args for pagination links
    current_args = {k: v for k, v in request.args.items() if k != 'page'}
    
    return render_template('reports/report.html', 
                         vulnerabilities=vulnerabilities,
                         total_vuln_count=total_vuln_count,
                         vendors=vendors,
                         filters=filters,
                         page=page,
                         total_pages=total_pages,
                         current_args=current_args,
                         last_updated=datetime.now().strftime('%Y-%m-%d %H:%M'))


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
    return render_template('reports/report_view.html', report=report)


@report_bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate_report() -> Any:
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

    return render_template('reports/report_form.html', form=form)


@report_bp.route('/export/csv', methods=['GET'])
@login_required
def export_csv() -> Any:
    """
    Exporta relatórios em formato CSV.
    """
    from flask import make_response
    import csv
    from io import StringIO
    from models.vulnerability import Vulnerability
    
    # Get filter parameters
    severity = request.args.get('severity', '')
    vendor = request.args.get('vendor', '')
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    
    # Build query with same filters as list_reports
    query = Vulnerability.query
    
    if severity:
        query = query.filter(Vulnerability.base_severity == severity)
    
    if vendor:
        query = query.join(Vulnerability.affected_products).join(AffectedProduct.product).join(Product.vendor).filter(
            Vendor.name.ilike(f'%{vendor}%')
        )
    
    if date_start:
        try:
            from datetime import datetime
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date >= start_date)
        except ValueError:
            pass
    
    if date_end:
        try:
            from datetime import datetime
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date <= end_date)
        except ValueError:
            pass
    
    vulnerabilities = query.all()
    
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['CVE ID', 'Descrição', 'Severidade', 'CVSS Score', 'Fornecedor', 'Data de Publicação'])
    
    # Write data
    for vuln in vulnerabilities:
        writer.writerow([
            vuln.cve_id,
            vuln.description[:100] + '...' if len(vuln.description) > 100 else vuln.description,
            vuln.base_severity,
            vuln.cvss_score,
            ', '.join([p.product.vendor.name for p in vuln.affected_products]),
            vuln.published_date.strftime('%Y-%m-%d') if vuln.published_date else ''
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=vulnerabilities_report.csv'
    
    current_app.logger.info(f"[Reports] user={current_user.id} exported CSV with {len(vulnerabilities)} records")
    return response


@report_bp.route('/export/pdf', methods=['GET'])
@login_required
def export_pdf() -> Any:
    """
    Exporta relatórios em formato PDF.
    """
    from flask import make_response
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from io import BytesIO
    from models.vulnerability import Vulnerability
    from datetime import datetime
    
    # Get filter parameters
    severity = request.args.get('severity', '')
    vendor = request.args.get('vendor', '')
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    
    # Build query with same filters as list_reports
    query = Vulnerability.query
    
    if severity:
        query = query.filter(Vulnerability.base_severity == severity)
    
    if vendor:
        query = query.join(Vulnerability.affected_products).join(AffectedProduct.product).join(Product.vendor).filter(
            Vendor.name.ilike(f'%{vendor}%')
        )
    
    if date_start:
        try:
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date >= start_date)
        except ValueError:
            pass
    
    if date_end:
        try:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            query = query.filter(Vulnerability.published_date <= end_date)
        except ValueError:
            pass
    
    vulnerabilities = query.all()
    
    # Create PDF content
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Title
    title = Paragraph("Relatório de Vulnerabilidades", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Report info
    report_info = Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(report_info)
    elements.append(Spacer(1, 12))
    
    # Table data
    data = [['CVE ID', 'Severidade', 'CVSS', 'Fornecedor', 'Data']]
    
    for vuln in vulnerabilities:
        data.append([
            vuln.cve_id,
            vuln.base_severity,
            str(vuln.cvss_score) if vuln.cvss_score else 'N/A',
            ', '.join([p.product.vendor.name for p in vuln.affected_products])[:20] + '...' if len(', '.join([p.product.vendor.name for p in vuln.affected_products])) > 20 else ', '.join([p.product.vendor.name for p in vuln.affected_products]),
            vuln.published_date.strftime('%d/%m/%Y') if vuln.published_date else 'N/A'
        ])
    
    # Create table
    table = Table(data, colWidths=[1.5*inch, 1*inch, 0.8*inch, 1.5*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    # Create response
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=vulnerabilities_report.pdf'
    
    current_app.logger.info(f"[Reports] user={current_user.id} exported PDF with {len(vulnerabilities)} records")
    return response

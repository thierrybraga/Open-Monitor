import os
import sys
from datetime import datetime, timedelta

def main():
    # Garantir que o pacote 'app' seja importável
    # Base_dir aponta para 'app'; precisamos adicionar a raiz do projeto
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app.app import create_app
    from app.extensions import db
    from app.models.report import Report, ReportType, ReportScope, DetailLevel, ReportStatus
    from app.services.pdf_export_service import PDFExportService

    app = create_app()
    with app.app_context():
        # Criar relatório de teste pendente
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=7)

        report = Report(
            title=f"Relatório Teste - {ReportType.EXECUTIVE.value}",
            description="Relatório de teste criado via script para validação de exportação PDF.",
            report_type=ReportType.EXECUTIVE,
            scope=ReportScope.ALL_ASSETS,
            detail_level=DetailLevel.SUMMARY,
            period_start=period_start,
            period_end=period_end,
            status=ReportStatus.PENDING,
            generated_by_id=1
        )

        db.session.add(report)
        db.session.commit()

        # Definir dados mínimos e concluir
        report.content = {
            'summary': 'Resumo executivo gerado para validação.',
            'details': 'Conteúdo de teste para geração de PDF.'
        }
        report.ai_analysis = {'executive_summary': 'Análise executiva de teste.'}
        # Atributos não persistentes usados pelo serviço/controlador
        report.include_charts = True
        report.chart_types = ['cvss_distribution']
        report.export_formats = ['html', 'pdf']
        report.status = ReportStatus.COMPLETED
        report.generated_at = datetime.utcnow()
        db.session.commit()

        # Exportar PDF via serviço
        pdf_service = PDFExportService()
        file_path = pdf_service.export_to_pdf(report)
        print({'id': report.id, 'status': report.status.value, 'pdf_file': file_path})


if __name__ == '__main__':
    main()
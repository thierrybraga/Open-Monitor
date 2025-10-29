import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.app import create_app
from app.services.pdf_export_service import PDFExportService
from app.models.report import ReportType, ReportScope, ReportStatus

def main():
    app = create_app(os.getenv('FLASK_ENV') or 'development')
    with app.app_context():
        # Criar um relatório simulado mínimo para teste de exportação
        class DummyReport:
            def __init__(self):
                from datetime import datetime
                self.id = 9999
                self.title = 'Relatório de Teste'
                self.description = 'Relatório gerado automaticamente para validar exportação PDF.'
                self.report_type = ReportType.TECHNICAL
                self.scope = ReportScope.ALL_ASSETS
                self.detail_level = None
                self.period_start = datetime.now()
                self.period_end = datetime.now()
                self.scope_config = None
                self.status = ReportStatus.COMPLETED
                self.generated_at = datetime.now()
                self.generated_by_id = 1
                self.content = None
                self.charts_data = None
                self.ai_analysis = None
                self.executive_summary = None
                self.recommendations = None
                self.impact_level = None
                self.urgency_level = None
                self.completeness_score = None
                self.maturity_level = None
                self.tags = None
                self.file_path = None
                self.file_size = None
                self.export_format = None
                self.report_metadata = None
                self.created_at = datetime.now()
                self.updated_at = datetime.now()

        report = DummyReport()
        service = PDFExportService()
        try:
            filepath = service.export_to_pdf(report)
            print(f'PDF exported: {filepath}')
        except Exception as e:
            print(f'Export failed: {e}')

if __name__ == '__main__':
    main()
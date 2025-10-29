import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Garantir que o diretório raiz esteja no sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.app import create_app
from app.extensions import db
from app.models.report import (
    Report,
    ReportType,
    ReportScope,
    DetailLevel,
    ReportStatus,
)
from app.controllers.report_controller import _generate_report_async


def create_and_generate_report(report_type: ReportType, days: int = 30) -> dict:
    """Cria e gera um relatório para o tipo especificado.

    Retorna um dict com resumo de geração.
    """
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # Incluir gráficos e evitar análise de IA (para não depender de serviços externos)
    report_metadata = {
        'include_charts': True,
        'chart_types': ['cvss_distribution', 'top_assets_risk', 'vulnerability_trend', 'kpi_timeline'],
        'include_ai_analysis': False,
        'ai_analysis_types': [],
        'export_format': 'html',
    }

    title = f"Teste Automático - {report_type.value} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

    report = Report(
        title=title,
        description=f"Relatório de teste automático para os últimos {days} dias",
        report_type=report_type,
        scope=ReportScope.ALL_ASSETS,
        detail_level=DetailLevel.SUMMARY,
        period_start=period_start,
        period_end=period_end,
        scope_config={},
        status=ReportStatus.PENDING,
        generated_by_id=1,
        export_format='html',
        ai_analysis_types=[],
        report_metadata=report_metadata,
    )

    db.session.add(report)
    db.session.commit()

    # Geração do conteúdo e gráficos
    _generate_report_async(report.id)

    # Recarregar estado atualizado
    report = Report.query.get(report.id)

    # Resumo do resultado
    charts_keys = list((report.charts_data or {}).keys())
    content_keys = list((report.content or {}).keys())

    return {
        'id': report.id,
        'title': report.title,
        'type': report.report_type.value,
        'status': report.status.value if hasattr(report.status, 'value') else str(report.status),
        'generated_at': report.generated_at.isoformat() if report.generated_at else None,
        'charts': charts_keys,
        'content_sections': content_keys,
        'error': getattr(report, 'error_message', None),
    }


def main(days: int = 30):
    app = create_app('development')
    app.testing = True
    results = []
    with app.app_context():
        types = [
            ReportType.EXECUTIVE,
            ReportType.TECHNICAL,
            ReportType.TECHNICAL_STUDY,
            ReportType.PENTEST,
            ReportType.BIA,
            ReportType.KPI_KRI,
        ]

        for t in types:
            try:
                summary = create_and_generate_report(t, days=days)
                results.append(summary)
            except Exception as e:
                results.append({
                    'type': t.value,
                    'status': 'falhou',
                    'error': str(e),
                })

    # Saída legível
    print(json.dumps({
        'success': True,
        'days': days,
        'results': results
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    # Permitir passar número de dias pela linha de comando
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except Exception:
            days = 30
    else:
        days = 30
    main(days=days)
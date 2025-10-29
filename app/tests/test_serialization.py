"""
Testes de serialização para conteúdo e gráficos de relatório
"""

import unittest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from app.controllers import report_controller as rc


class TestSerialization(unittest.TestCase):
    """Valida que funções de geração retornam estruturas JSON-serializáveis."""

    def test_cvss_distribution_serializable(self):
        vulnerabilities = {'cvss_detailed': {'Low': 10, 'High': 5}}
        data = rc._generate_cvss_distribution_data(vulnerabilities)
        # Não deve lançar
        json.dumps(data)

    def test_top_assets_risk_serializable(self):
        class AssetObj:
            pass
        asset_obj = AssetObj()
        asset_obj.id = 123
        asset_obj.name = 'Servidor 1'
        report_data = {
            'top_assets_by_risk': [
                {'asset': asset_obj, 'total_risk': 12.5, 'risk_count': 3, 'avg_risk': 4.17},
                {'asset': None, 'total_risk': '7.5', 'risk_count': '2', 'avg_risk': '3.75'},
            ]
        }
        data = rc._generate_top_assets_risk_data(report_data)
        json.dumps(data)

        # Verifica conversões numéricas
        self.assertIsInstance(data['data'][0]['total_risk'], float)
        self.assertIsInstance(data['data'][0]['risk_count'], int)
        self.assertIsInstance(data['data'][1]['total_risk'], float)
        self.assertIsInstance(data['data'][1]['risk_count'], int)

    def test_vulnerability_trends_serializable(self):
        report_data = {'trends': {'trend_data': [{'date': '2024-01-01', 'count': 10}]}}
        data = rc._generate_vulnerability_trends_data(report_data)
        json.dumps(data)

    def test_risk_matrix_serializable(self):
        report_data = {'risk_matrix': [{'x': 3, 'y': 7, 'value': 'Asset 1'}]}
        data = rc._generate_risk_matrix_data(report_data)
        json.dumps(data)

    def test_heatmap_serializable(self):
        report_data = {'asset_vulnerability_matrix': [[1, 2], [3, 4]]}
        data = rc._generate_heatmap_data(report_data)
        json.dumps(data)

    def test_kpi_timeline_serializable(self):
        timeline = {'kpi_timeline': [{'label': 'Disponibilidade', 'value': 99.99}]}
        data = rc._generate_kpi_timeline_data(timeline)
        json.dumps(data)

    def test_security_maturity_serializable(self):
        report_data = {'security_maturity': {'IAM': 3, 'Network': 4}}
        data = rc._generate_security_maturity_data(report_data)
        json.dumps(data)

    def test_base_content_serializable(self):
        mock_report = Mock()
        mock_report.period_start = datetime(2024, 1, 1)
        mock_report.period_end = datetime(2024, 1, 31)
        mock_report.scope = Mock()
        mock_report.scope.value = 'GLOBAL'
        mock_report.detail_level = Mock()
        mock_report.detail_level.value = 'SUMMARY'
        mock_report.report_type = Mock()
        mock_report.report_type.value = 'pentest'

        report_data = {
            'assets': {
                'total_assets': 10,
                'assets_with_vulnerabilities': 5,
                'assets_by_status': {'online': 8},
            },
            'vulnerabilities': {
                'total_vulnerabilities': 20,
                'by_severity': {'critical': 2, 'high': 5},
                'cvss_stats': {'avg': 7.2},
                'epss_stats': {'avg': 0.3},
            },
            'risks': {
                'risk_statistics': {'avg_risk': 4.2},
                'total_assessments': 12,
            },
            'timeline': {
                'vulnerability_timeline': [
                    {'date': datetime(2024, 1, 5), 'count': 3},
                    {'date': '2024-01-10', 'count': 2},
                ],
                'risk_timeline': [
                    {'date': datetime(2024, 1, 6), 'avg_risk': 3.2, 'count': 1},
                ],
                'kpi_timeline': {'labels': ['A'], 'kpis': [1]},
            },
        }
        content = rc._generate_base_content(mock_report, report_data)
        json.dumps(content)

    @patch('app.controllers.report_controller.cache_service')
    def test_aggregate_chart_data_serializable(self, mock_cache):
        # Força geração ao invés de cache
        mock_cache.get_chart_data.return_value = None
        mock_cache.set_chart_data.return_value = True

        mock_report = Mock()
        mock_report.id = 99
        mock_report.chart_types = [
            'cvss_distribution',
            'top_assets_risk',
            'vulnerability_trend',
            'risk_matrix',
            'asset_vulnerability_heatmap',
            'kpi_timeline',
            'security_maturity',
        ]

        class AssetObj2:
            pass
        asset_obj2 = AssetObj2()
        asset_obj2.id = 1
        asset_obj2.name = 'A'

        report_data = {
            'vulnerabilities': {'cvss_detailed': {'Low': 5}},
            'top_assets_by_risk': [
                {'asset': asset_obj2, 'total_risk': 1, 'risk_count': 1, 'avg_risk': 1}
            ],
            'trends': {'trend_data': [{'date': '2024-01', 'count': 1}]},
            'risk_matrix': [{'x': 1, 'y': 2, 'value': 'A'}],
            'asset_vulnerability_matrix': [[0, 1], [2, 3]],
            'timeline': {'kpi_timeline': [{'label': 'SLA', 'value': 95}]},
            'security_maturity': {'IAM': 2}
        }

        charts = rc._generate_chart_data(mock_report, report_data)
        for ct in mock_report.chart_types:
            self.assertIn(ct, charts)
        json.dumps(charts)


if __name__ == '__main__':
    unittest.main()
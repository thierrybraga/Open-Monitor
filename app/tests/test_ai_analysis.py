import pytest

from app.controllers.report_controller import _generate_ai_analysis


class StubAIService:
    def __init__(self):
        self.calls = {}

    def generate_executive_summary(self, report_data, report_type):
        self.calls['executive_summary'] = (report_data, report_type)
        return 'EXEC'

    def generate_cisa_kev_analysis(self, cisa_kev_data, vuln_data):
        self.calls['cisa_kev'] = (cisa_kev_data, vuln_data)
        return 'CISA'

    def generate_epss_analysis(self, epss_data, vuln_data):
        self.calls['epss'] = (epss_data, vuln_data)
        return 'EPSS'

    def generate_vendor_product_analysis(self, vendor_product_data, vuln_data):
        self.calls['vendor'] = (vendor_product_data, vuln_data)
        return 'VENDOR'

    def generate_technical_analysis(self, vuln_data, cve_details):
        self.calls['technical'] = (vuln_data, cve_details)
        return 'TECH'


class DummyReportType:
    value = 'tecnico'


class DummyReport:
    ai_analysis_types = [
        'executive_summary',
        'cisa_kev_analysis',
        'epss_analysis',
        'vendor_product_analysis',
        'technical_analysis'
    ]
    report_type = DummyReportType()


def test_generate_ai_analysis_mappings(monkeypatch):
    # Prepare stub AI service and monkeypatch controller reference
    stub = StubAIService()
    monkeypatch.setattr('app.controllers.report_controller.ai_service', stub, raising=True)

    report_data = {
        'vulnerabilities': {
            'cisa_kev_data': {'total_kev': 2},
            'epss_data': {'scores': [0.1]},
            'vendor_product_data': {'vendors': ['Acme']},
            'cve_details': [{'id': 'CVE-1'}]
        },
        'assets': {}
    }

    result = _generate_ai_analysis(DummyReport(), report_data)

    # Validate executive summary mapping
    assert 'executive_summary' in stub.calls
    assert stub.calls['executive_summary'][1] == 'tecnico'

    # Validate CISA KEV mapping
    assert 'cisa_kev' in stub.calls
    assert stub.calls['cisa_kev'][0] == report_data['vulnerabilities']['cisa_kev_data']
    assert stub.calls['cisa_kev'][1] == report_data['vulnerabilities']

    # Validate EPSS mapping
    assert 'epss' in stub.calls
    assert stub.calls['epss'][0] == report_data['vulnerabilities']['epss_data']
    assert stub.calls['epss'][1] == report_data['vulnerabilities']

    # Validate vendor/product mapping
    assert 'vendor' in stub.calls
    assert stub.calls['vendor'][0] == report_data['vulnerabilities']['vendor_product_data']
    assert stub.calls['vendor'][1] == report_data['vulnerabilities']

    # Validate technical analysis mapping
    assert 'technical' in stub.calls
    assert stub.calls['technical'][0] == report_data['vulnerabilities']
    assert stub.calls['technical'][1] == report_data['vulnerabilities']['cve_details']

    # Ensure result contains expected keys
    assert isinstance(result, dict)
    for key in ['executive_summary', 'cisa_kev_analysis', 'epss_analysis', 'vendor_product_analysis', 'technical_analysis']:
        assert key in result
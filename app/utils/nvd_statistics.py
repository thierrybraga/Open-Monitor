#!/usr/bin/env python3
"""
Módulo de estatísticas da NVD e banco de dados local.
Fornece informações sobre contagem de CVEs, status de sincronização e métricas.
"""

import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import func, text
from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.sync_metadata import SyncMetadata
from app.models.references import Reference
from app.models.weakness import Weakness
from app.utils.terminal_feedback import terminal_feedback

logger = logging.getLogger(__name__)

class NVDStatistics:
    """
    Classe para obter estatísticas da NVD e banco local.
    """
    
    def __init__(self):
        self.nvd_base_url = os.getenv('NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0')
        self.api_key = os.getenv('NVD_API_KEY')
        try:
            self.timeout = int(os.getenv('NVD_REQUEST_TIMEOUT', '30'))
        except Exception:
            self.timeout = 30
        self.user_agent = os.getenv('NVD_USER_AGENT', 'Open-Monitor/1.0')
    
    def get_nvd_total_count(self) -> Optional[int]:
        """
        Obtém o total de CVEs disponíveis na NVD.
        
        Returns:
            int: Total de CVEs na NVD ou None se houver erro
        """
        try:
            terminal_feedback.info("🔍 Consultando total de CVEs na NVD...")
            
            # Consultar com janela de publicação ampla para obter totalResults confiável
            from datetime import timezone as _tz, timedelta as _td
            now = datetime.now(_tz.utc)
            earliest = datetime(1999, 1, 1, tzinfo=_tz.utc)
            total_results_sum = 0

            headers = {'User-Agent': self.user_agent}
            if self.api_key:
                headers['apiKey'] = self.api_key

            cursor = earliest
            while cursor <= now:
                window_end = min(cursor + _td(days=120), now)
                params = {
                    'resultsPerPage': 1,
                    'startIndex': 0,
                    'pubStartDate': cursor.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                    'pubEndDate': window_end.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                }
                try:
                    response = requests.get(
                        self.nvd_base_url,
                        params=params,
                        timeout=self.timeout,
                        headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        total_results_sum += int(data.get('totalResults', 0) or 0)
                    elif response.status_code == 404:
                        # Janela inválida (excedeu limite ou sem dados); avançar
                        pass
                    else:
                        terminal_feedback.error(f"❌ Erro HTTP {response.status_code} ao consultar janela {cursor} → {window_end}")
                except requests.RequestException as e:
                    terminal_feedback.error(f"❌ Erro de conexão com NVD na janela {cursor} → {window_end}: {str(e)}")
                except Exception as e:
                    terminal_feedback.error(f"❌ Erro inesperado ao consultar janela {cursor} → {window_end}: {str(e)}")
                # Avança 1 segundo para evitar reprocessar o mesmo registro no limite inclusivo
                cursor = window_end + _td(seconds=1)

            terminal_feedback.success(f"📊 Total de CVEs na NVD (somatório por janelas): {total_results_sum:,}")
            return total_results_sum
                
        except requests.RequestException as e:
            terminal_feedback.error(f"❌ Erro de conexão com NVD: {str(e)}")
            return None
        except Exception as e:
            terminal_feedback.error(f"❌ Erro inesperado: {str(e)}")
            return None
    
    def get_local_cve_count(self) -> int:
        """
        Obtém o total de CVEs no banco de dados local.
        
        Returns:
            int: Total de CVEs no banco local
        """
        try:
            count = db.session.query(func.count(Vulnerability.cve_id)).scalar()
            terminal_feedback.info(f"💾 CVEs no banco local: {count:,}")
            return count or 0
        except Exception as e:
            terminal_feedback.error(f"❌ Erro ao contar CVEs locais: {str(e)}")
            return 0
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas detalhadas de sincronização.
        
        Returns:
            Dict com estatísticas de sincronização
        """
        try:
            # Obter última sincronização
            last_sync = db.session.query(SyncMetadata).order_by(
                SyncMetadata.last_modified.desc()
            ).first()
            
            # Contar CVEs por ano
            cve_by_year = db.session.query(
                func.substr(Vulnerability.cve_id, 5, 4).label('year'),
                func.count(Vulnerability.cve_id).label('count')
            ).group_by(
                func.substr(Vulnerability.cve_id, 5, 4)
            ).order_by('year').all()
            
            # Contar CVEs por severidade
            severity_counts = db.session.query(
                Vulnerability.base_severity,
                func.count(Vulnerability.cve_id).label('count')
            ).group_by(Vulnerability.base_severity).all()
            
            stats = {
                'last_sync': {
                    'timestamp': last_sync.last_modified if last_sync else None,
                    'type': last_sync.sync_type if last_sync else None,
                    'status': last_sync.status if last_sync else None
                },
                'cve_by_year': {year: count for year, count in cve_by_year},
                'severity_distribution': {severity or 'Unknown': count for severity, count in severity_counts},
                'total_local': self.get_local_cve_count()
            }
            
            return stats
            
        except Exception as e:
            terminal_feedback.error(f"❌ Erro ao obter estatísticas: {str(e)}")
            return {}
    
    def get_sync_progress_info(self) -> Dict[str, Any]:
        """
        Obtém informações sobre o progresso atual da sincronização.
        
        Returns:
            Dict com informações de progresso
        """
        try:
            # Verificar se há sincronização em andamento
            active_sync = db.session.query(SyncMetadata).filter(
                SyncMetadata.status == 'in_progress'
            ).first()
            
            if active_sync:
                # Calcular progresso estimado
                nvd_total = self.get_nvd_total_count()
                local_total = self.get_local_cve_count()
                
                if nvd_total:
                    progress_percentage = (local_total / nvd_total) * 100
                    remaining = nvd_total - local_total
                    
                    return {
                        'is_syncing': True,
                        'progress_percentage': round(progress_percentage, 2),
                        'processed': local_total,
                        'total': nvd_total,
                        'remaining': remaining,
                        'sync_start': active_sync.last_modified
                    }
            
            return {
                'is_syncing': False,
                'last_sync': self.get_sync_statistics()['last_sync']
            }
            
        except Exception as e:
            terminal_feedback.error(f"❌ Erro ao obter progresso: {str(e)}")
            return {'is_syncing': False}
    
    def get_data_quality_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas de qualidade dos dados.
        
        Returns:
            Dict com métricas de qualidade
        """
        try:
            # CVEs com descrição
            with_description = db.session.query(func.count(Vulnerability.cve_id)).filter(
                Vulnerability.description.isnot(None),
                Vulnerability.description != ''
            ).scalar() or 0
            
            # CVEs com CVSS
            with_cvss = db.session.query(func.count(Vulnerability.cve_id)).filter(
                Vulnerability.cvss_score.isnot(None)
            ).scalar() or 0
            
            # CVEs com CWE
            with_cwe = db.session.query(func.count(Vulnerability.cve_id)).join(
                Weakness, Vulnerability.cve_id == Weakness.cve_id
            ).scalar() or 0
            
            # CVEs com referências
            with_references = db.session.query(func.count(Vulnerability.cve_id)).join(
                Reference, Vulnerability.cve_id == Reference.cve_id
            ).scalar() or 0
            
            return {
                'with_description': with_description,
                'with_cvss': with_cvss,
                'with_cwe': with_cwe,
                'with_references': with_references
            }
            
        except Exception as e:
            terminal_feedback.error(f"❌ Erro ao obter métricas de qualidade: {str(e)}")
            return {}
    
    def display_comprehensive_stats(self) -> None:
        """
        Exibe estatísticas abrangentes do sistema.
        """
        terminal_feedback.info("📊 Gerando relatório de estatísticas...")
        
        # Obter todas as estatísticas
        nvd_total = self.get_nvd_total_count()
        local_total = self.get_local_cve_count()
        sync_stats = self.get_sync_statistics()
        progress_info = self.get_sync_progress_info()
        quality_metrics = self.get_data_quality_metrics()
        
        # Exibir cabeçalho
        terminal_feedback.info("\n" + "="*60)
        terminal_feedback.info("📈 RELATÓRIO DE ESTATÍSTICAS - OPEN MONITOR")
        terminal_feedback.info("="*60)
        
        # Estatísticas gerais
        terminal_feedback.info("\n🌐 ESTATÍSTICAS GERAIS:")
        if nvd_total:
            terminal_feedback.info(f"   📡 CVEs na NVD: {nvd_total:,}")
            terminal_feedback.info(f"   💾 CVEs locais: {local_total:,}")
            
            if nvd_total > 0:
                coverage = (local_total / nvd_total) * 100
                terminal_feedback.info(f"   📊 Cobertura: {coverage:.1f}%")
                terminal_feedback.info(f"   🔄 Faltam: {nvd_total - local_total:,} CVEs")
        else:
            terminal_feedback.warning("   ⚠️ Não foi possível obter total da NVD")
            terminal_feedback.info(f"   💾 CVEs locais: {local_total:,}")
        
        # Métricas de qualidade dos dados
        if quality_metrics and local_total > 0:
            terminal_feedback.info("\n🔍 QUALIDADE DOS DADOS:")
            desc_count = quality_metrics.get('with_description', 0)
            cvss_count = quality_metrics.get('with_cvss', 0)
            cwe_count = quality_metrics.get('with_cwe', 0)
            ref_count = quality_metrics.get('with_references', 0)
            
            desc_pct = (desc_count / local_total) * 100
            cvss_pct = (cvss_count / local_total) * 100
            cwe_pct = (cwe_count / local_total) * 100
            ref_pct = (ref_count / local_total) * 100
            
            terminal_feedback.info(f"   📝 Com descrição: {desc_count:,} ({desc_pct:.1f}%)")
            terminal_feedback.info(f"   📊 Com CVSS: {cvss_count:,} ({cvss_pct:.1f}%)")
            terminal_feedback.info(f"   🏷️ Com CWE: {cwe_count:,} ({cwe_pct:.1f}%)")
            terminal_feedback.info(f"   🔗 Com referências: {ref_count:,} ({ref_pct:.1f}%)")
            
            overall_quality = (desc_pct + cvss_pct + cwe_pct + ref_pct) / 4
            terminal_feedback.info(f"   ⭐ Qualidade geral: {overall_quality:.1f}%")
        
        # Status de sincronização
        terminal_feedback.info("\n🔄 STATUS DE SINCRONIZAÇÃO:")
        if progress_info.get('is_syncing', False):
            terminal_feedback.info(f"   🟢 Sincronização em andamento")
            terminal_feedback.info(f"   📈 Progresso: {progress_info.get('progress_percentage', 0):.1f}%")
            terminal_feedback.info(f"   ⏱️ Processados: {progress_info.get('processed', 0):,}")
            terminal_feedback.info(f"   📋 Restantes: {progress_info.get('remaining', 0):,}")
        else:
            last_sync = sync_stats.get('last_sync', {})
            if last_sync and last_sync.get('timestamp'):
                terminal_feedback.info(f"   🕐 Última sincronização: {last_sync['timestamp']}")
                terminal_feedback.info(f"   📝 Tipo: {last_sync.get('type', 'N/A')}")
                terminal_feedback.info(f"   ✅ Status: {last_sync.get('status', 'N/A')}")
            else:
                terminal_feedback.warning("   ⚠️ Nenhuma sincronização encontrada")
        
        # Distribuição por ano
        cve_by_year = sync_stats.get('cve_by_year', {})
        if cve_by_year:
            terminal_feedback.info("\n📅 DISTRIBUIÇÃO POR ANO:")
            for year, count in sorted(cve_by_year.items()):
                terminal_feedback.info(f"   {year}: {count:,} CVEs")
        
        # Distribuição por severidade
        severity_distribution = sync_stats.get('severity_distribution', {})
        if severity_distribution:
            terminal_feedback.info("\n⚠️ DISTRIBUIÇÃO POR SEVERIDADE:")
            severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'Unknown']
            for severity in severity_order:
                if severity in severity_distribution:
                    count = severity_distribution[severity]
                    terminal_feedback.info(f"   {severity}: {count:,} CVEs")
        
        terminal_feedback.info("\n" + "="*60)
        terminal_feedback.success("✅ Relatório de estatísticas concluído!")

# Instância global
nvd_stats = NVDStatistics()

# Funções de conveniência
def get_nvd_total() -> Optional[int]:
    """Obtém total de CVEs na NVD."""
    return nvd_stats.get_nvd_total_count()

def get_local_total() -> int:
    """Obtém total de CVEs no banco local."""
    return nvd_stats.get_local_cve_count()

def show_stats() -> None:
    """Exibe estatísticas completas."""
    nvd_stats.display_comprehensive_stats()

def get_sync_progress() -> Dict[str, Any]:
    """Obtém informações de progresso da sincronização."""
    return nvd_stats.get_sync_progress_info()

if __name__ == "__main__":
    # Teste do módulo
    show_stats()

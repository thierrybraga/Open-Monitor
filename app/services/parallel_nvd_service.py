#!/usr/bin/env python3
"""
Serviço de processamento paralelo para requisições NVD.
Otimiza a performance através de processamento concorrente e em lotes.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
import aiohttp
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.vulnerability import Vulnerability
from app.models.sync_metadata import SyncMetadata
from app.extensions import db
from app.utils.rate_limiter import NVDRateLimiter
from app.utils.severity_mapper import map_cvss_score_to_severity
from app.utils.memory_monitor import memory_monitor

logger = logging.getLogger(__name__)

@dataclass
class ProcessingMetrics:
    """Métricas de performance do processamento"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_cves_processed: int = 0
    total_cves_saved: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def requests_per_second(self) -> float:
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration
    
    @property
    def cves_per_second(self) -> float:
        if self.duration == 0:
            return 0.0
        return self.total_cves_processed / self.duration

@dataclass
class BatchRequest:
    """Representa uma requisição em lote"""
    start_index: int
    page_size: int
    last_modified_start: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

class ParallelNVDService:
    """
    Serviço para processamento paralelo de requisições NVD.
    
    Características:
    - Processamento concorrente de múltiplas páginas
    - Controle inteligente de rate limiting
    - Processamento em lotes otimizado
    - Retry automático com backoff exponencial
    - Métricas de performance detalhadas
    """
    
    def __init__(self, config: Dict[str, Any], max_concurrent_requests: int = 5):
        """
        Inicializa o serviço de processamento paralelo.
        
        Args:
            config: Configurações da API NVD
            max_concurrent_requests: Número máximo de requisições concorrentes
        """
        self.config = config
        self.max_concurrent_requests = max_concurrent_requests
        
        # Configurações da API
        self.api_base = config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0")
        self.api_key = config.get("NVD_API_KEY")
        self.page_size = config.get("NVD_PAGE_SIZE", 2000)
        self.request_timeout = config.get("NVD_REQUEST_TIMEOUT", 30)
        self.user_agent = config.get("NVD_USER_AGENT", "Sec4all.co Parallel NVD Fetcher")
        
        # Headers para requisições
        self.headers = {"User-Agent": self.user_agent}
        if self.api_key:
            self.headers["apiKey"] = self.api_key
        
        # Rate limiter inteligente
        self.rate_limiter = NVDRateLimiter.create_for_nvd(has_api_key=bool(self.api_key))
        
        # Semáforo para controlar concorrência
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Métricas de performance
        self.metrics = ProcessingMetrics()
        
        # Cache em memória otimizado para evitar requisições duplicadas
        self.memory_cache: Dict[str, Dict] = {}
        self._cache_max_size = 50  # Limite reduzido do cache para economizar memória
        self._cache_access_order = []  # Para implementar LRU
        
        # Configurações de batch processing
        self.batch_size = config.get("BATCH_SIZE", 100)  # CVEs por lote para DB
        self.db_batch_size = config.get("DB_BATCH_SIZE", 500)  # Operações DB por transação
        
    async def fetch_page_parallel(self, session: aiohttp.ClientSession, 
                                 batch_request: BatchRequest) -> Optional[Dict]:
        """
        Busca uma página da API NVD com controle de concorrência e cache LRU otimizado.
        
        Args:
            session: Sessão HTTP assíncrona
            batch_request: Requisição em lote
            
        Returns:
            Dados da página ou None em caso de falha
        """
        import gc
        
        async with self.semaphore:  # Controla concorrência
            cache_key = f"{batch_request.start_index}_{batch_request.last_modified_start or 'full'}"
            
            # Verificar cache em memória com LRU
            if cache_key in self.memory_cache:
                logger.debug(f"Cache hit para página {batch_request.start_index}")
                # Atualizar ordem de acesso para LRU
                if cache_key in self._cache_access_order:
                    self._cache_access_order.remove(cache_key)
                self._cache_access_order.append(cache_key)
                return self.memory_cache[cache_key]
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Construir URL
            url = f"{self.api_base}?startIndex={batch_request.start_index}&resultsPerPage={batch_request.page_size}"
            
            if batch_request.last_modified_start:
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                last_mod = batch_request.last_modified_start
                if last_mod.endswith('+00:00'):
                    last_mod = last_mod.replace('+00:00', 'Z')
                elif not last_mod.endswith('Z') and 'T' in last_mod and '+' not in last_mod:
                    last_mod += 'Z'
                url += f"&lastModStartDate={last_mod}&lastModEndDate={current_time}"
            
            # Tentar requisição com retry
            for attempt in range(batch_request.max_retries):
                try:
                    self.metrics.total_requests += 1
                    
                    async with session.get(url, headers=self.headers, 
                                         timeout=self.request_timeout) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            # Gerenciar cache com LRU para otimizar memória
                            if len(self.memory_cache) >= self._cache_max_size:
                                # Remover item mais antigo (LRU)
                                if self._cache_access_order:
                                    oldest_key = self._cache_access_order.pop(0)
                                    if oldest_key in self.memory_cache:
                                        del self.memory_cache[oldest_key]
                            
                            # Armazenar no cache
                            self.memory_cache[cache_key] = data
                            self._cache_access_order.append(cache_key)
                            
                            # Garbage collection periódico
                            if len(self.memory_cache) % 10 == 0:
                                gc.collect()
                            
                            self.metrics.successful_requests += 1
                            logger.debug(f"Página {batch_request.start_index} buscada com sucesso")
                            return data
                        
                        elif response.status == 429:  # Rate limit
                            should_retry = await self.rate_limiter.handle_http_error(
                                response.status, dict(response.headers)
                            )
                            if should_retry and attempt < batch_request.max_retries - 1:
                                continue
                            else:
                                break
                        
                        elif response.status >= 500:  # Server error
                            should_retry = await self.rate_limiter.handle_http_error(
                                response.status, dict(response.headers)
                            )
                            if should_retry and attempt < batch_request.max_retries - 1:
                                wait_time = 2 ** attempt
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                break
                        
                        else:
                            logger.error(f"Erro HTTP {response.status} para página {batch_request.start_index}")
                            break
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Erro de rede na página {batch_request.start_index} (tentativa {attempt + 1}): {e}")
                    if attempt < batch_request.max_retries - 1:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        break
                
                except Exception as e:
                    logger.error(f"Erro inesperado na página {batch_request.start_index}: {e}")
                    break
            
            self.metrics.failed_requests += 1
            logger.error(f"Falha ao buscar página {batch_request.start_index} após {batch_request.max_retries} tentativas")
            return None
    
    async def process_cves_batch(self, cves_data: List[Dict]) -> List[Dict]:
        """
        Processa um lote de CVEs em paralelo.
        
        Args:
            cves_data: Lista de dados brutos de CVEs
            
        Returns:
            Lista de CVEs processados
        """
        processed_cves = []
        
        # Usar ThreadPoolExecutor para processamento CPU-intensivo
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submeter tarefas de processamento
            futures = {
                executor.submit(self._process_single_cve, cve_data): cve_data 
                for cve_data in cves_data
            }
            
            # Coletar resultados
            for future in as_completed(futures):
                try:
                    processed_cve = future.result(timeout=30)
                    if processed_cve:
                        processed_cves.append(processed_cve)
                        self.metrics.total_cves_processed += 1
                except Exception as e:
                    cve_data = futures[future]
                    cve_id = cve_data.get('id', 'unknown')
                    logger.error(f"Erro ao processar CVE {cve_id}: {e}")
        
        return processed_cves
    
    def _process_single_cve(self, cve_data: Dict) -> Optional[Dict]:
        """
        Processa um único CVE (método síncrono para ThreadPoolExecutor).
        
        Args:
            cve_data: Dados brutos do CVE
            
        Returns:
            CVE processado ou None
        """
        try:
            cve_id = cve_data.get('id')
            if not cve_id:
                return None
            
            # Extrair descrição
            description = "No description available."
            for desc in cve_data.get('descriptions', []):
                if desc.get('lang') == 'en':
                    description = desc.get('value', description)
                    break
            
            # Extrair datas
            published_date = None
            published_str = cve_data.get('published')
            if published_str:
                try:
                    published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Data de publicação inválida para {cve_id}: {published_str}")
            
            last_modified = None
            last_modified_str = cve_data.get('lastModified')
            if last_modified_str:
                try:
                    last_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Data de modificação inválida para {cve_id}: {last_modified_str}")
            
            # Extrair CVSS com mapeamento aprimorado de severidade
            cvss_score = None
            base_severity = 'N/A'
            
            metrics = cve_data.get('metrics', {})
            # Priorizar CVSS v3.1 > v3.0 > v2.0
            for cvss_key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
                metric_list = metrics.get(cvss_key, [])
                if metric_list:
                    metric = metric_list[0]  # Pegar o primeiro
                    cvss_data = metric.get('cvssData', {})
                    cvss_score = cvss_data.get('baseScore')
                    
                    # Determinar versão CVSS
                    if cvss_key == 'cvssMetricV31':
                        cvss_version = '3.1'
                    elif cvss_key == 'cvssMetricV30':
                        cvss_version = '3.0'
                    else:
                        cvss_version = '2.0'
                    
                    # Extrair severidade com fallback
                    base_severity = cvss_data.get('baseSeverity', '').upper()
                    
                    # Se não tem baseSeverity (CVEs antigos), mapear do score
                    if not base_severity or base_severity in ['UNKNOWN', '', 'N/A']:
                        if cvss_score is not None:
                            base_severity = map_cvss_score_to_severity(cvss_score, cvss_version)
                    
                    # Validar severidade final
                    if base_severity not in ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                        base_severity = 'N/A'
                    
                    break
            
            # Extrair CWEs
            cwe_ids = []
            weaknesses = cve_data.get('weaknesses', [])
            for weakness in weaknesses:
                for desc in weakness.get('description', []):
                    if desc.get('lang') == 'en':
                        value = desc.get('value', '')
                        if value.startswith('CWE-'):
                            cwe_ids.append(value)
            
            # Extrair referências
            references = []
            for ref in cve_data.get('references', []):
                ref_url = ref.get('url')
                ref_tags = ref.get('tags', [])
                if ref_url:
                    references.append({
                        'url': ref_url,
                        'tags': ref_tags
                    })
            
            return {
                'cve_id': cve_id,
                'description': description,
                'published_date': published_date,
                'last_modified': last_modified,
                'cvss_score': cvss_score,
                'base_severity': base_severity,
                'cwe_ids': cwe_ids,
                'references': references,
                'raw_data': cve_data  # Manter dados brutos para análise posterior
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar CVE: {e}")
            return None
    
    async def bulk_save_to_database(self, processed_cves: List[Dict], 
                                  db_session: Session) -> int:
        """
        Salva CVEs processados no banco em lotes otimizados com gestão de memória.
        
        Args:
            processed_cves: Lista de CVEs processados
            db_session: Sessão do banco de dados
            
        Returns:
            Número de CVEs salvos
        """
        import gc
        saved_count = 0
        
        try:
            # OTIMIZAÇÃO: Processar em lotes menores para reduzir uso de memória
            optimized_batch_size = min(self.db_batch_size // 2, 250)  # Reduzir tamanho do lote
            
            for i in range(0, len(processed_cves), optimized_batch_size):
                batch = processed_cves[i:i + optimized_batch_size]
                
                # Preparar dados para bulk insert/update
                vulnerability_data = []
                
                for cve in batch:
                    # Verificar se CVE já existe
                    existing = db_session.query(Vulnerability).filter_by(
                        cve_id=cve['cve_id']
                    ).first()
                    
                    if existing:
                        # Atualizar se modificado
                        if (cve['last_modified'] and 
                            existing.last_modified and 
                            cve['last_modified'] > existing.last_modified):
                            
                            existing.description = cve['description']
                            existing.last_modified = cve['last_modified']
                            existing.cvss_score = cve['cvss_score']
                            existing.base_severity = cve['base_severity']
                            saved_count += 1
                    else:
                        # Criar novo
                        vulnerability_data.append({
                            'cve_id': cve['cve_id'],
                            'description': cve['description'],
                            'published_date': cve['published_date'],
                            'last_modified': cve['last_modified'],
                            'cvss_score': cve['cvss_score'],
                            'base_severity': cve['base_severity'],
                            'created_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow()
                        })
                
                # Bulk insert para novos registros
                if vulnerability_data:
                    db_session.execute(
                        text("""
                        INSERT INTO vulnerabilities 
                        (cve_id, description, published_date, last_modified, 
                         cvss_score, base_severity, created_at, updated_at)
                        VALUES 
                        (:cve_id, :description, :published_date, :last_modified,
                         :cvss_score, :base_severity, :created_at, :updated_at)
                        ON CONFLICT (cve_id) DO UPDATE SET
                        description = EXCLUDED.description,
                        last_modified = EXCLUDED.last_modified,
                        cvss_score = EXCLUDED.cvss_score,
                        base_severity = EXCLUDED.base_severity,
                        updated_at = EXCLUDED.updated_at
                        WHERE vulnerabilities.last_modified < EXCLUDED.last_modified
                        """)
                    )
                    
                    saved_count += len(vulnerability_data)
                
                # Commit em lotes
                db_session.commit()
                
                # OTIMIZAÇÃO: Limpar referências e executar garbage collection
                del vulnerability_data
                del batch
                
                # Garbage collection a cada 3 lotes
                if (i // optimized_batch_size) % 3 == 0:
                    gc.collect()
                
                logger.debug(f"Lote otimizado {i//optimized_batch_size + 1} processado. Total salvo: {saved_count}")
            
            self.metrics.total_cves_saved = saved_count
            return saved_count
            
        except Exception as e:
            logger.error(f"Erro ao salvar CVEs no banco: {e}")
            db_session.rollback()
            raise
    
    async def parallel_sync(self, full_sync: bool = False, 
                          vulnerability_service=None) -> ProcessingMetrics:
        """
        Executa sincronização paralela da API NVD.
        
        Args:
            full_sync: Se True, faz sincronização completa
            vulnerability_service: Serviço de vulnerabilidades
            
        Returns:
            Métricas de performance
        """
        self.metrics = ProcessingMetrics()
        self.metrics.start_time = time.time()
        
        # MONITORAMENTO DE MEMÓRIA: Inicializar monitoramento
        memory_monitor.log_memory_status("início da sincronização paralela")
        
        logger.info(f"Iniciando sincronização paralela (full={full_sync})")
        
        # Determinar última sincronização
        last_synced_time_str = None
        if not full_sync and vulnerability_service:
            last_synced_time = vulnerability_service.get_last_sync_time()
            if last_synced_time:
                last_synced_time_str = last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                logger.info(f"Última sincronização: {last_synced_time_str}")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Primeira requisição para determinar total de resultados
                initial_request = BatchRequest(
                    start_index=0,
                    page_size=self.page_size,
                    last_modified_start=last_synced_time_str
                )
                
                initial_data = await self.fetch_page_parallel(session, initial_request)
                if not initial_data:
                    logger.error("Falha na requisição inicial")
                    return self.metrics
                
                total_results = initial_data.get('totalResults', 0)
                logger.info(f"Total de resultados esperados: {total_results}")
                
                if total_results == 0:
                    logger.info("Nenhum resultado encontrado")
                    self.metrics.end_time = time.time()
                    return self.metrics
                
                # Criar requisições em lote
                batch_requests = []
                for start_idx in range(0, total_results, self.page_size):
                    batch_requests.append(BatchRequest(
                        start_index=start_idx,
                        page_size=self.page_size,
                        last_modified_start=last_synced_time_str
                    ))
                
                logger.info(f"Criadas {len(batch_requests)} requisições em lote")
                
                # Processar requisições em paralelo
                all_cves = []
                
                # Processar em chunks para evitar sobrecarga
                chunk_size = self.max_concurrent_requests * 2
                for i in range(0, len(batch_requests), chunk_size):
                    chunk = batch_requests[i:i + chunk_size]
                    
                    # Executar chunk em paralelo
                    tasks = [
                        self.fetch_page_parallel(session, req) 
                        for req in chunk
                    ]
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Processar resultados
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"Erro na requisição: {result}")
                            continue
                        
                        if result and 'vulnerabilities' in result:
                            vulnerabilities = result['vulnerabilities']
                            for vuln in vulnerabilities:
                                cve_data = vuln.get('cve')
                                if cve_data:
                                    all_cves.append(cve_data)
                    
                    logger.info(f"Processado chunk {i//chunk_size + 1}/{(len(batch_requests) + chunk_size - 1)//chunk_size}")
                
                logger.info(f"Total de CVEs coletados: {len(all_cves)}")
                
                # Processar CVEs em lotes
                all_processed_cves = []
                for i in range(0, len(all_cves), self.batch_size):
                    batch = all_cves[i:i + self.batch_size]
                    processed_batch = await self.process_cves_batch(batch)
                    all_processed_cves.extend(processed_batch)
                    
                    logger.debug(f"Processado lote {i//self.batch_size + 1}/{(len(all_cves) + self.batch_size - 1)//self.batch_size}")
                
                # Salvar no banco de dados
                if all_processed_cves and vulnerability_service:
                    with db.session.begin() as db_session:
                        saved_count = await self.bulk_save_to_database(
                            all_processed_cves, db_session
                        )
                        
                        # Atualizar última sincronização
                        vulnerability_service.update_last_sync_time(
                            datetime.utcnow(), db_session
                        )
                        
                        logger.info(f"Salvos {saved_count} CVEs no banco")
                
        except Exception as e:
            logger.error(f"Erro durante sincronização paralela: {e}")
            raise
        finally:
            self.metrics.end_time = time.time()
        
        logger.info(f"Sincronização paralela concluída em {self.metrics.duration:.2f}s")
        logger.info(f"Taxa de sucesso: {self.metrics.success_rate:.1f}%")
        logger.info(f"CVEs/segundo: {self.metrics.cves_per_second:.2f}")
        
        return self.metrics
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Gera relatório de performance detalhado.
        
        Returns:
            Dicionário com métricas de performance
        """
        return {
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'success_rate_percent': round(self.metrics.success_rate, 2),
            'total_cves_processed': self.metrics.total_cves_processed,
            'total_cves_saved': self.metrics.total_cves_saved,
            'duration_seconds': round(self.metrics.duration, 2),
            'requests_per_second': round(self.metrics.requests_per_second, 2),
            'cves_per_second': round(self.metrics.cves_per_second, 2),
            'max_concurrent_requests': self.max_concurrent_requests,
            'batch_size': self.batch_size,
            'db_batch_size': self.db_batch_size
        }

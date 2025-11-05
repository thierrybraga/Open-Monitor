
import sys
import os
import time
import pickle
import asyncio
import logging
import argparse
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional # Importar Optional explicitamente
from pathlib import Path # Importar Path explicitamente

import aiohttp
import tqdm
from flask import Flask # current_app não é necessário aqui, pois estamos em um contexto de job standalone
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Sistema de feedback aprimorado
from app.utils.terminal_feedback import terminal_feedback, timed_operation
from app.utils.visual_indicators import status_indicator
from app.utils.enhanced_logging import get_app_logger
from app.utils.memory_monitor import memory_monitor
from app.utils.nvd_statistics import nvd_stats

# Use importações relativas CORRETAS para módulos DENTRO do pacote project
# Assumindo que o pacote 'project' é o diretório pai de 'jobs'
from app.extensions import db # Importa db do pacote extensions (__init__.py)
# Importações CORRETAS dos modelos (Assumindo que estão em project/models)
from app.models.sync_metadata import SyncMetadata
from app.models.vulnerability import Vulnerability
from app.models.cvss_metric import CVSSMetric
# from models.api_call_log import ApiCallLog # Importar se o modelo for usado aqui
# from services.vulnerability_service import VulnerabilityService # Importar após criar o serviço
from app.jobs.nvd_enhancements import CWEAutoMapper, EnhancedReferenceProcessor
from app.utils.rate_limiter import NVDRateLimiter
from app.utils.severity_mapper import map_cvss_score_to_severity, get_primary_severity_from_metrics

logger = logging.getLogger(__name__)

# TODO: Garantir que estas configurações sejam carregadas da configuração da aplicação Flask (app.config)
# A classe NVDFetcher deve recebê-las via __init__.
# CACHE_DIR = Path('cache') # O caminho do cache deve ser configurável (obtido da config)
# API_BASE    = os.getenv("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0") # Obtido da config
# API_KEY     = os.getenv("NVD_API_KEY", None) # Obtido da config
# PAGE_SIZE   = 2000 # Obtido da config
# MAX_RETRIES = 5 # Obtido da config
# RATE_LIMIT  = (2, 1)  # 2 requests per 1 sec (para a API Key Gratuita) # Obtido da config


class EnhancedCPEParser:
    """Parser aprimorado para extrair vendor/product de múltiplas fontes"""
    
    def __init__(self):
        # Padrões conhecidos de vendors
        self.vendor_patterns = {
            r'\bmicrosoft\b': 'microsoft',
            r'\bapple\b': 'apple',
            r'\boracle\b': 'oracle',
            r'\bgoogle\b': 'google',
            r'\bdebian\b': 'debian',
            r'\bubuntu\b': 'canonical',
            r'\bredhat\b': 'redhat',
            r'\brhel\b': 'redhat',
            r'\bcentos\b': 'centos',
            r'\bfedora\b': 'fedoraproject',
            r'\bsuse\b': 'suse',
            r'\bopensuse\b': 'opensuse',
            r'\bcisco\b': 'cisco',
            r'\bibm\b': 'ibm',
            r'\bintel\b': 'intel',
            r'\bamd\b': 'amd',
            r'\bnvidia\b': 'nvidia',
            r'\badobe\b': 'adobe',
            r'\bmozilla\b': 'mozilla',
            r'\bfirefox\b': 'mozilla',
            r'\bchrome\b': 'google',
            r'\bchromium\b': 'google',
            r'\blinux\b': 'linux',
            r'\bwindows\b': 'microsoft',
            r'\bmacos\b': 'apple',
            r'\bios\b': 'apple',
            r'\bandroid\b': 'google',
            r'\bjava\b': 'oracle',
            r'\bopenjdk\b': 'openjdk',
            r'\bphp\b': 'php',
            r'\bpython\b': 'python',
            r'\bnodejs\b': 'nodejs',
            r'\bnode\.js\b': 'nodejs',
            r'\bnpm\b': 'npmjs',
            r'\byarn\b': 'yarnpkg',
            r'\bdocker\b': 'docker',
            r'\bkubernetes\b': 'kubernetes',
            r'\bjenkins\b': 'jenkins',
            r'\bgit\b': 'git-scm',
            r'\bapache\b': 'apache',
            r'\bnginx\b': 'nginx',
            r'\bmysql\b': 'mysql',
            r'\bpostgresql\b': 'postgresql',
            r'\bmongodb\b': 'mongodb',
            r'\bredis\b': 'redis',
            r'\belasticsearch\b': 'elastic',
            r'\bkibana\b': 'elastic',
            r'\blogstash\b': 'elastic',
            r'\bsplunk\b': 'splunk',
            r'\bvmware\b': 'vmware',
            r'\bcitrix\b': 'citrix',
            r'\baws\b': 'amazon',
            r'\bamazon\b': 'amazon',
            r'\bazure\b': 'microsoft',
            r'\bgcp\b': 'google',
            r'\bwordpress\b': 'wordpress',
            r'\bdrupal\b': 'drupal',
            r'\bjoomla\b': 'joomla',
            r'\bmagento\b': 'magento',
            r'\bshopify\b': 'shopify',
            r'\bsalesforce\b': 'salesforce',
            r'\bslack\b': 'slack',
            r'\bzoom\b': 'zoom',
            r'\bteams\b': 'microsoft',
            r'\bskype\b': 'microsoft',
            r'\bwhatsapp\b': 'whatsapp',
            r'\btelegram\b': 'telegram',
            r'\bdiscord\b': 'discord'
        }
        
        # Padrões conhecidos de products
        self.product_patterns = {
            r'\bwindows\s+\d+': 'windows',
            r'\bwindows\s+server': 'windows_server',
            r'\boffice\s+\d+': 'office',
            r'\bexchange\s+server': 'exchange_server',
            r'\bsql\s+server': 'sql_server',
            r'\bvisual\s+studio': 'visual_studio',
            r'\b\.net\s+framework': 'dotnet_framework',
            r'\biis': 'iis',
            r'\bmacos': 'macos',
            r'\bios': 'ios',
            r'\bsafari': 'safari',
            r'\bitunes': 'itunes',
            r'\bxcode': 'xcode',
            r'\bfirefox': 'firefox',
            r'\bthunderbird': 'thunderbird',
            r'\bchrome': 'chrome',
            r'\bchromium': 'chromium',
            r'\bandroid': 'android',
            r'\bgmail': 'gmail',
            r'\byoutube': 'youtube',
            r'\bmaps': 'maps',
            r'\bdrive': 'drive',
            r'\blinux\s+kernel': 'linux_kernel',
            r'\bdebian': 'debian',
            r'\bubuntu': 'ubuntu',
            r'\bcentos': 'centos',
            r'\bfedora': 'fedora',
            r'\brhel': 'rhel',
            r'\bsuse': 'suse',
            r'\bopensuse': 'opensuse',
            r'\bapache\s+http\s+server': 'apache_httpd',
            r'\bapache\s+tomcat': 'tomcat',
            r'\bnginx': 'nginx',
            r'\bmysql': 'mysql',
            r'\bpostgresql': 'postgresql',
            r'\bmongodb': 'mongodb',
            r'\bredis': 'redis',
            r'\belasticsearch': 'elasticsearch',
            r'\bkibana': 'kibana',
            r'\blogstash': 'logstash',
            r'\bjenkins': 'jenkins',
            r'\bdocker': 'docker',
            r'\bkubernetes': 'kubernetes',
            r'\bwordpress': 'wordpress',
            r'\bdrupal': 'drupal',
            r'\bjoomla': 'joomla',
            r'\bmagento': 'magento',
            r'\bphp': 'php',
            r'\bpython': 'python',
            r'\bnodejs': 'nodejs',
            r'\bnode\.js': 'nodejs',
            r'\bnpm': 'npm',
            r'\byarn': 'yarn',
            r'\bjava': 'java',
            r'\bopenjdk': 'openjdk'
        }
    
    def extract_from_cpe(self, configurations):
        """Extrai vendors, products e informações de versão de configurações CPE"""
        vendors = set()
        products = set()
        version_ranges = []
        
        for config in configurations:
            for node in config.get('nodes', []):
                for cpe_match in node.get('cpeMatch', []):
                    cpe_uri = cpe_match.get('criteria', '')
                    vulnerable = cpe_match.get('vulnerable', False)
                    
                    if cpe_uri.startswith('cpe:2.3:'):
                        parts = cpe_uri.split(':')
                        if len(parts) >= 5:
                            vendor = parts[3]
                            product = parts[4]
                            version = parts[5] if len(parts) > 5 else None
                            
                            if vendor and vendor != '*' and vendor != '-':
                                vendor = re.sub(r'[^a-zA-Z0-9_-]', '', vendor)
                                if vendor:
                                    vendors.add(vendor.lower())
                            
                            if product and product != '*' and product != '-':
                                product = re.sub(r'[^a-zA-Z0-9_-]', '', product)
                                if product:
                                    products.add(product.lower())
                            
                            # Extrair informações de versão
                            version_info = {
                                'cpe': cpe_uri,
                                'vendor': vendor,
                                'product': product,
                                'version': version if version and version != '*' and version != '-' else None,
                                'vulnerable': vulnerable,
                                'version_start_including': cpe_match.get('versionStartIncluding'),
                                'version_start_excluding': cpe_match.get('versionStartExcluding'),
                                'version_end_including': cpe_match.get('versionEndIncluding'),
                                'version_end_excluding': cpe_match.get('versionEndExcluding')
                            }
                            
                            # Adicionar apenas se tiver informações de versão relevantes
                            if (version_info['version'] or 
                                version_info['version_start_including'] or 
                                version_info['version_start_excluding'] or 
                                version_info['version_end_including'] or 
                                version_info['version_end_excluding']):
                                version_ranges.append(version_info)
        
        return list(vendors), list(products), version_ranges
    
    def extract_from_description(self, description):
        """Extrai vendors e products da descrição do CVE"""
        vendors = set()
        products = set()
        
        if not description:
            return [], []
        
        description_lower = description.lower()
        
        # Buscar vendors conhecidos
        for pattern, vendor in self.vendor_patterns.items():
            if re.search(pattern, description_lower, re.IGNORECASE):
                vendors.add(vendor)
        
        # Buscar products conhecidos
        for pattern, product in self.product_patterns.items():
            if re.search(pattern, description_lower, re.IGNORECASE):
                products.add(product)
        
        return list(vendors), list(products)
    
    def extract_from_references(self, references):
        """Extrai vendors e products das referências do CVE"""
        vendors = set()
        products = set()
        
        for ref in references:
            url = ref.get('url', '')
            if not url:
                continue
            
            url_lower = url.lower()
            
            # Extrair vendor do domínio
            domain_patterns = {
                r'microsoft\.com': 'microsoft',
                r'apple\.com': 'apple',
                r'oracle\.com': 'oracle',
                r'google\.com': 'google',
                r'debian\.org': 'debian',
                r'ubuntu\.com': 'canonical',
                r'redhat\.com': 'redhat',
                r'centos\.org': 'centos',
                r'fedoraproject\.org': 'fedoraproject',
                r'suse\.com': 'suse',
                r'opensuse\.org': 'opensuse',
                r'cisco\.com': 'cisco',
                r'ibm\.com': 'ibm',
                r'intel\.com': 'intel',
                r'amd\.com': 'amd',
                r'nvidia\.com': 'nvidia',
                r'adobe\.com': 'adobe',
                r'mozilla\.org': 'mozilla',
                r'php\.net': 'php',
                r'python\.org': 'python',
                r'nodejs\.org': 'nodejs',
                r'docker\.com': 'docker',
                r'kubernetes\.io': 'kubernetes',
                r'jenkins\.io': 'jenkins',
                r'apache\.org': 'apache',
                r'nginx\.org': 'nginx',
                r'mysql\.com': 'mysql',
                r'postgresql\.org': 'postgresql',
                r'mongodb\.com': 'mongodb',
                r'redis\.io': 'redis',
                r'elastic\.co': 'elastic',
                r'vmware\.com': 'vmware',
                r'citrix\.com': 'citrix',
                r'wordpress\.org': 'wordpress',
                r'drupal\.org': 'drupal',
                r'joomla\.org': 'joomla'
            }
            
            for pattern, vendor in domain_patterns.items():
                if re.search(pattern, url_lower):
                    vendors.add(vendor)
        
        return list(vendors), list(products)
    
    def extract_all(self, cve_data):
        """Extrai vendors, products e informações de versão de todas as fontes disponíveis"""
        all_vendors = set()
        all_products = set()
        all_version_ranges = []
        
        # 1. Extrair de configurações CPE
        configurations = cve_data.get('configurations', [])
        cpe_vendors, cpe_products, version_ranges = self.extract_from_cpe(configurations)
        all_vendors.update(cpe_vendors)
        all_products.update(cpe_products)
        all_version_ranges.extend(version_ranges)
        
        # 2. Extrair da descrição
        descriptions = cve_data.get('descriptions', [])
        if descriptions:
            description = descriptions[0].get('value', '')
            desc_vendors, desc_products = self.extract_from_description(description)
            all_vendors.update(desc_vendors)
            all_products.update(desc_products)
        
        # 3. Extrair das referências
        references = cve_data.get('references', [])
        ref_vendors, ref_products = self.extract_from_references(references)
        all_vendors.update(ref_vendors)
        all_products.update(ref_products)
        
        return list(all_vendors), list(all_products), all_version_ranges


class NVDFetcher:
    """
    Sincroniza CVEs da NVD API.

    Esta classe é responsável por buscar dados da API, gerenciar cache,
    rate limiting e retries. A lógica de persistência no banco de dados
    DEVE ser delegada a um serviço de persistência separado.
    """

    # Adicionado type hinting para config
    def __init__(self, session: aiohttp.ClientSession, config: Dict[str, Any]):
        """
        Inicializa o NVDFetcher.

        Args:
            session: aiohttp.ClientSession para requisições HTTP assíncronas.
            config: Dicionário com as configurações necessárias (API_BASE, API_KEY, PAGE_SIZE, etc.).
        """
        self.session = session
        # TODO: Remover self.db_session após mover a lógica de persistência para um serviço
        # self.db_session = db_session # Mover DB session para o serviço
        self.config = config
        # Obter configurações da API do dicionário config
        self.api_base = self.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0")
        self.api_key = self.config.get("NVD_API_KEY")
        self.page_size = self.config.get("NVD_PAGE_SIZE", 2000)
        self.max_retries = self.config.get("NVD_MAX_RETRIES", 5)
        self.cache_dir = Path(self.config.get("NVD_CACHE_DIR", "cache"))
        self.request_timeout = self.config.get("NVD_REQUEST_TIMEOUT", 30)
        self.user_agent = self.config.get("NVD_USER_AGENT", "Sec4all.co NVD Fetcher")
        # Janela máxima permitida pela NVD para consultas por lastModified (em dias)
        self.max_window_days = int(self.config.get("NVD_MAX_WINDOW_DAYS", 120))

        self.headers = {"User-Agent": self.user_agent}
        if self.api_key:
             self.headers["X-API-Key"] = self.api_key

        # Inicializar o rate limiter avançado
        self.rate_limiter = NVDRateLimiter.create_for_nvd(has_api_key=bool(self.api_key))
        
        # Manter compatibilidade com código legado (será removido)
        self.rate_limit_requests, self.rate_limit_window = self.config.get("NVD_RATE_LIMIT", (2, 1))
        self.request_times: List[float] = [] # Lista para controle de rate limit (legado)
        
        # Inicializar o parser aprimorado
        self.enhanced_parser = EnhancedCPEParser()
        
        # Inicializar melhorias para CWE e referências
        self.cwe_auto_mapper = CWEAutoMapper()
        self.enhanced_reference_processor = EnhancedReferenceProcessor()


    async def validate_key(self) -> bool:
        """
        Valida se a chave da API está funcionando (opcional)
        tentando buscar uma página mínima.
        """
        # TODO: Obter URL de validação da configuração
        url = f"{self.api_base}?resultsPerPage=1" # Usar self.api_base
        logger.debug(f"Validating API key using URL: {url}")
        try:
            # Usar timeout da configuração
            async with self.session.get(url, headers=self.headers, timeout=self.request_timeout) as resp: # Usar self.request_timeout
                # A validação da chave pode não dar 200 mesmo com chave válida,
                # mas 401 (Unauthorized) geralmente indica chave inválida.
                if resp.status == 401:
                     logger.error("API key invalid or missing (401 Unauthorized).")
                     return False
                resp.raise_for_status() # Lança exceção para outros 4xx/5xx respostas

                logger.info("API key validated successfully.")
                return True
        except aiohttp.ClientError as e:
            logger.error(f"Network or Client error during API key validation: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during API key validation: {e}", exc_info=True)
            return False


    async def fetch_page(self, start_index: int, last_modified_start: Optional[str], last_modified_end: Optional[str] = None) -> Optional[Dict]:
        """
        Busca uma página de vulnerabilidades da API NVD.

        Args:
            start_index: Índice inicial para a busca.
            last_modified_start: String ISO 8601 para buscar CVEs modificados
                                 DESDE esta data (usando lastModifiedStart).
                                 None para busca completa.

        Returns:
            Dicionário com os dados da página da API, ou None em caso de falha.
        """
        # --- Controle de rate limit avançado ---
        await self.rate_limiter.acquire()

        # --- Cacheamento básico em arquivo ---
        self.cache_dir.mkdir(exist_ok=True) # Usar self.cache_dir
        # Garante que o nome do cache é único para buscas full vs modificadas
        if last_modified_start:
            safe_start = last_modified_start.replace(":", "").replace("+", "_")
            safe_end = (last_modified_end or "now").replace(":", "").replace("+", "_") if last_modified_end else "now"
            cache_key_suffix = f"{safe_start}_{safe_end}"
        else:
            cache_key_suffix = "full"
        cache_file = self.cache_dir / f"page_{start_index}_{cache_key_suffix}.pkl" # Usar self.cache_dir

        if cache_file.exists():
            logger.debug(f"Loading page {start_index} (modified since {last_modified_start}) from cache: {cache_file}")
            try:
                data = pickle.loads(cache_file.read_bytes())
                # Opcional: adicionar validação básica dos dados cacheados
                if isinstance(data, dict) and 'vulnerabilities' in data and 'totalResults' in data:
                    # TODO: Adicionar validação mais robusta do formato dos dados cacheados
                    logger.debug(f"Cache file {cache_file} loaded successfully.")
                    return data
                else:
                     logger.warning(f"Cache file {cache_file} seems incomplete or corrupted. Deleting.")
                     cache_file.unlink()
            except (pickle.UnpicklingError, EOFError) as e:
                 logger.warning(f"Error loading cache file {cache_file}: {e}. Deleting and refetching.", exc_info=True)
                 cache_file.unlink(missing_ok=True)
            except Exception as e:
                 logger.error(f"Unexpected error processing cache file {cache_file}: {e}", exc_info=True)
                 cache_file.unlink(missing_ok=True)

        # --- Monta a URL da API ---
        url = f"{self.api_base}?startIndex={start_index}&resultsPerPage={self.page_size}" # Usar self.api_base, self.page_size

        # Lógica CORRETA para busca incremental (CVEs modificados DESDE a última sincronização)
        # A API NVD usa lastModifiedStart e lastModifiedEnd para intervalos.
        # Se last_modified_start é a data/hora da última sincronização, usá-lo com lastModifiedStart
        # busca CVEs modificados NESTE timestamp ou DEPOIS.
        if last_modified_start:
            # A API NVD requer AMBOS lastModStartDate E lastModEndDate
            # Formato correto: ISO com Z (Zulu time) - exemplo: 2025-09-20T14:35:44Z
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            # Converte last_modified_start para o formato correto se necessário
            if last_modified_start.endswith('+00:00'):
                last_modified_start = last_modified_start.replace('+00:00', 'Z')
            elif not last_modified_start.endswith('Z'):
                # Se não tem timezone, assume UTC e adiciona Z
                if 'T' in last_modified_start and '+' not in last_modified_start:
                    last_modified_start += 'Z'

            # Determinar o fim da janela
            end_param = last_modified_end or current_time
            if end_param.endswith('+00:00'):
                end_param = end_param.replace('+00:00', 'Z')
            elif not end_param.endswith('Z'):
                if 'T' in end_param and '+' not in end_param:
                    end_param += 'Z'

            url += f"&lastModStartDate={last_modified_start}&lastModEndDate={end_param}"

        if last_modified_start:
            logger.info(f"Fetching page {start_index} from NVD API (range {last_modified_start} to {last_modified_end or 'now'}). URL: {url}")
        else:
            logger.info(f"Fetching page {start_index} from NVD API (full sync). URL: {url}")

        # --- Tenta buscar a página com retries ---
        for attempt in range(self.max_retries): # Usar self.max_retries
            try:
                # Adiciona cabeçalho de API Key condicionalmente
                headers_with_key = {**self.headers} # Copia cabeçalhos base (inclui User-Agent)
                if self.api_key:
                     headers_with_key["X-API-Key"] = self.api_key # Adiciona API Key se presente

                async with self.session.get(url, headers=headers_with_key, timeout=self.request_timeout) as resp: # Usar headers_with_key, self.request_timeout
                    logger.debug(f"API Response Status for page {start_index}: {resp.status}")

                    if resp.status == 200:
                        data = await resp.json()
                        # Salvar cache somente se a requisição foi bem-sucedida
                        try:
                            cache_file.write_bytes(pickle.dumps(data))
                            logger.debug(f"Successfully fetched and cached page {start_index}.")
                        except Exception as cache_err:
                             logger.warning(f"Failed to write cache file {cache_file}: {cache_err}", exc_info=True)
                        # TODO: Log da chamada de API (ApiCallLog) aqui?
                        return data

                    elif resp.status == 400: # Bad Request - geralmente erro na requisição
                         logger.error(f"API returned 400 Bad Request for page {start_index}. Check URL/params. Response: {await resp.text()}")
                         return None # Erro fatal de requisição

                    elif resp.status == 401: # Unauthorized - API Key inválida
                         logger.error("API Key invalid or missing (401 Unauthorized). Cannot proceed.")
                         return None # Erro fatal

                    elif resp.status == 404: # Not Found
                         logger.warning(f"API returned 404 Not Found for page {start_index}. URL may be incorrect or no data.")
                         # Pode significar o fim dos resultados em alguns casos, mas a API geralmente retorna 200 com lista vazia.
                         # Tratar como um erro que interrompe o processo por segurança, a menos que se saiba o contrário.
                         return None

                    elif resp.status == 429: # Rate Limit Exceeded
                        # Usar o sistema avançado de rate limiting para tratar 429
                        should_retry = await self.rate_limiter.handle_http_error(
                            resp.status, dict(resp.headers)
                        )
                        if should_retry and attempt < self.max_retries - 1:
                            continue
                        else:
                            return None

                    elif resp.status >= 500: # Server Error
                        # Usar o sistema avançado de rate limiting para tratar erros de servidor
                        should_retry = await self.rate_limiter.handle_http_error(
                            resp.status, dict(resp.headers)
                        )
                        if should_retry and attempt < self.max_retries - 1:
                            continue
                        else:
                            return None

                    else: # Outro erro inesperado
                        logger.error(f"Unexpected API Error {resp.status} for page {start_index} (Attempt {attempt + 1}/{self.max_retries}). Response: {await resp.text()}") # Usar self.max_retries
                        if attempt == self.max_retries - 1: # Usar self.max_retries
                            return None # Não tenta novamente após o último retry
                        else:
                             wait_time = 2**(attempt + 1)
                             await asyncio.sleep(wait_time) # Espera antes de tentar novamente
                             continue

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Erros de conexão, timeout ou requisição com aiohttp
                logger.error(f"Network, Timeout, or Client Error fetching page {start_index} (Attempt {attempt + 1}/{self.max_retries}): {e}", exc_info=True) # Usar self.max_retries
                if attempt == self.max_retries - 1: # Usar self.max_retries
                    return None # Não tenta novamente após o último retry
                else:
                    # Backoff exponencial + um pouco mais para garantir tempo suficiente
                    wait_time = 2**(attempt + 1) + 1 # Adiciona 1 segundo extra
                    logger.warning(f"Retrying fetch for page {start_index} in {wait_time:.2f} seconds.")
                    await asyncio.sleep(wait_time) # Espera antes de tentar novamente
                    continue
            except Exception as e:
                # Outros erros inesperados durante o fetch
                 logger.error(f"An unexpected error occurred during fetch_page for page {start_index} (Attempt {attempt + 1}/{self.max_retries}): {e}", exc_info=True) # Usar self.max_retries
                 return None # Erro inesperado, parar

        logger.error(f"Failed to fetch page {start_index} after {self.max_retries} attempts.") # Usar self.max_retries
        # TODO: Log da falha no ApiCallLog?
        return None # Falhou após todas as tentativas


    # TODO: Esta lógica de processamento e mapeamento DEVE ser movida para o VulnerabilityService.
    # O fetcher deve retornar os dados brutos ou um dicionário leve.
    async def process_cve_data(self, cve_data: Dict[str, Any]) -> Optional[Dict[str, Any]]: # Alterar retorno para Dict ou DTO
        """
        Processa os dados brutos de um único CVE da API NVD e retorna um dicionário/DTO.
        Esta lógica deveria estar em um SERVIÇO ou REPOSITÓRIO de Vulnerabilidades.
        """
        # Exemplo de como extrair e mapear dados (ajuste conforme sua estrutura de modelo)
        cve_id = cve_data.get('id')
        if not cve_id:
            logger.warning("Skipping CVE item with no 'id'.")
            return None

        # Extrair descrição em inglês
        description = "No description available."
        for desc in cve_data.get('descriptions', []):
            if desc.get('lang') == 'en':
                 description = desc.get('value', description)
                 break

        # Extrair datas (lidar com formato ISO 8601, pode ter timezone)
        published_str = cve_data.get('published')
        last_modified_str = cve_data.get('lastModified')

        published_date = None
        if published_str:
            try:
                 # Ex: '2023-10-01T13:00:00.000-05:00' ou '2023-10-01T18:00:00Z'
                 published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except ValueError:
                 logger.warning(f"Could not parse published date '{published_str}' for CVE {cve_id}.")

        last_modified = None
        if last_modified_str:
            try:
                 last_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
            except ValueError:
                 logger.warning(f"Could not parse last modified date '{last_modified_str}' for CVE {cve_id}.")

        # Extrair campos adicionais da API NVD 2.0
        source_identifier = cve_data.get('sourceIdentifier')
        vuln_status = cve_data.get('vulnStatus')
        evaluator_comment = cve_data.get('evaluatorComment')
        evaluator_solution = cve_data.get('evaluatorSolution')
        evaluator_impact = cve_data.get('evaluatorImpact')
        
        # Extrair campos CISA KEV (Known Exploited Vulnerabilities)
        cisa_exploit_add = None
        cisa_action_due = None
        cisa_required_action = cve_data.get('cisaRequiredAction')
        cisa_vulnerability_name = cve_data.get('cisaVulnerabilityName')
        
        # Processar datas CISA se disponíveis
        cisa_exploit_add_str = cve_data.get('cisaExploitAdd')
        if cisa_exploit_add_str:
            try:
                cisa_exploit_add = datetime.fromisoformat(cisa_exploit_add_str.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Could not parse CISA exploit add date '{cisa_exploit_add_str}' for CVE {cve_id}.")
        
        cisa_action_due_str = cve_data.get('cisaActionDue')
        if cisa_action_due_str:
            try:
                cisa_action_due = datetime.fromisoformat(cisa_action_due_str.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Could not parse CISA action due date '{cisa_action_due_str}' for CVE {cve_id}.")

        # Extrair métricas CVSS de todas as versões disponíveis
        base_severity = 'N/A'
        cvss_score = None
        cvss_metrics = []

        metrics = cve_data.get('metrics', {})
        # Mapear chaves CVSS para versões
        cvss_version_map = {
            'cvssMetricV31': '3.1',
            'cvssMetricV30': '3.0', 
            'cvssMetricV2': '2.0'
        }
        
        # Ordem de prioridade para score principal
        priority_order = ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']
        
        # Extrair todas as métricas CVSS disponíveis
        for cvss_key, version in cvss_version_map.items():
            metric_list = metrics.get(cvss_key, [])
            if not isinstance(metric_list, list):
                continue
                
            for i, metric_item in enumerate(metric_list):
                cvss_data = metric_item.get('cvssData', {})
                if not cvss_data:
                    continue
                    
                try:
                    # Extrair score CVSS
                    base_score = float(cvss_data.get('baseScore', 0.0))
                    
                    # Extrair severidade - com fallback para CVEs antigos
                    severity_value = cvss_data.get('baseSeverity', '').upper()
                    
                    # Se não tem baseSeverity (CVEs antigos), mapear do score
                    if not severity_value or severity_value in ['UNKNOWN', '']:
                        severity_value = map_cvss_score_to_severity(base_score, version)
                    
                    # Validar severidade final
                    if severity_value not in ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                        severity_value = 'N/A'
                    
                    metric_info = {
                        'cvss_version': version,
                        'base_score': base_score,
                        'base_severity': severity_value,
                        'base_vector': cvss_data.get('vectorString', ''),
                        'is_primary': i == 0,  # Primeira métrica de cada versão é primária
                        'exploitability_score': cvss_data.get('exploitabilityScore'),
                        'impact_score': cvss_data.get('impactScore')
                    }
                    
                    # Extrair componentes específicos por versão
                    if version in ['3.0', '3.1']:
                        # CVSS v3.x componentes
                        metric_info.update({
                            'attack_vector': cvss_data.get('attackVector'),
                            'attack_complexity': cvss_data.get('attackComplexity'),
                            'privileges_required': cvss_data.get('privilegesRequired'),
                            'user_interaction': cvss_data.get('userInteraction'),
                            'scope': cvss_data.get('scope'),
                            'confidentiality_impact': cvss_data.get('confidentialityImpact'),
                            'integrity_impact': cvss_data.get('integrityImpact'),
                            'availability_impact': cvss_data.get('availabilityImpact')
                        })
                    elif version == '2.0':
                        # CVSS v2.x componentes
                        metric_info.update({
                            'access_vector': cvss_data.get('accessVector'),
                            'access_complexity': cvss_data.get('accessComplexity'),
                            'authentication': cvss_data.get('authentication'),
                            'confidentiality_impact': cvss_data.get('confidentialityImpact'),
                            'integrity_impact': cvss_data.get('integrityImpact'),
                            'availability_impact': cvss_data.get('availabilityImpact')
                        })
                    
                    # Converter scores para float quando disponíveis
                    for score_field in ['exploitability_score', 'impact_score']:
                        if metric_info[score_field] is not None:
                            try:
                                metric_info[score_field] = float(metric_info[score_field])
                            except (ValueError, TypeError):
                                metric_info[score_field] = None
                    
                    cvss_metrics.append(metric_info)
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing CVSS {version} data for CVE {cve_id}: {e}")
                    continue
        
        # Definir score e severidade principais usando a função utilitária
        base_severity, cvss_score = get_primary_severity_from_metrics(cvss_metrics)
        
        # Fallback para o método anterior se a função utilitária não encontrar nada
        if base_severity == 'N/A' and cvss_score is None:
            for priority_key in priority_order:
                if priority_key in cvss_version_map:
                    version = cvss_version_map[priority_key]
                    primary_metrics = [m for m in cvss_metrics if m['cvss_version'] == version and m['is_primary']]
                    if primary_metrics:
                        primary_metric = primary_metrics[0]
                        cvss_score = primary_metric['base_score']
                        base_severity = primary_metric['base_severity']
                        break

        # Extrair dados de vendors, products e informações de versão usando o parser aprimorado
        vendors_data, products_data, version_ranges_data = self.enhanced_parser.extract_all(cve_data)
        
        # Extrair CWEs usando o método original e adicionar mapeamento automático
        weaknesses_data = self._extract_weaknesses(cve_data.get('weaknesses', []))
        
        # Aplicar mapeamento automático de CWEs baseado na descrição
        auto_mapped_cwes = self.cwe_auto_mapper.map_cwe_from_description(description)
        
        # Combinar CWEs explícitos com os mapeados automaticamente
        all_cwes = set(weaknesses_data)  # CWEs explícitos
        all_cwes.update(auto_mapped_cwes)  # Adicionar CWEs mapeados automaticamente
        weaknesses_data = list(all_cwes)
        
        # Processar referências com melhorias
        references_data = []
        patch_available = False
        patch_references = []
        
        references = cve_data.get('references', [])
        for ref in references:
            url = ref.get('url')
            if url:
                ref_tags = ref.get('tags', [])
                
                # Validar referência usando o processador aprimorado
                if self.enhanced_reference_processor.validate_reference(url):
                    references_data.append({
                        'url': url,
                        'source': ref.get('source', ''),
                        'tags': ref_tags
                    })
                    
                    # Detectar patches usando o processador aprimorado
                    ref_dict = {'url': url, 'tags': ref_tags}
                    if self.enhanced_reference_processor.enhanced_patch_detection(ref_dict):
                        patch_available = True
                        patch_references.append({
                            'url': url,
                            'source': ref.get('source', ''),
                            'tags': ref_tags
                        })

        # Log informativo sobre patches e CWEs detectados
        if patch_available:
            logger.debug(f"CVE {cve_id}: Patch detected from {len(patch_references)} reference(s)")
        if auto_mapped_cwes:
            logger.debug(f"CVE {cve_id}: Auto-mapped CWEs: {auto_mapped_cwes}")
        
        # Em uma refatoração completa, isto retornaria um dicionário ou DTO
        # que representa os dados prontos para serem passados para o serviço de persistência.
        extracted_data = {
             "cve_id": cve_id,
             "description": description,
             "published_date": published_date,
             "last_update": last_modified,
             "base_severity": base_severity,
             "cvss_score": cvss_score if cvss_score is not None else 0.0,
             "patch_available": patch_available,  # Agora baseado em dados reais da API
             "cvss_metrics": cvss_metrics,  # Lista completa de métricas CVSS
             "vendors": vendors_data,
             "products": products_data,
             "weaknesses": weaknesses_data,
             "references": references_data,  # Adicionar referências
             "version_ranges": version_ranges_data,  # Informações de versão extraídas das configurações CPE
             "cpe_configurations": cve_data.get('configurations', []),  # Configurações CPE completas para referência
             
             # Campos adicionais da API NVD 2.0
             "source_identifier": source_identifier,
             "vuln_status": vuln_status,
             "evaluator_comment": evaluator_comment,
             "evaluator_solution": evaluator_solution,
             "evaluator_impact": evaluator_impact,
             
             # Campos CISA KEV (Known Exploited Vulnerabilities)
             "cisa_exploit_add": cisa_exploit_add,
             "cisa_action_due": cisa_action_due,
             "cisa_required_action": cisa_required_action,
             "cisa_vulnerability_name": cisa_vulnerability_name
        }
        # NOVO: Retornar o dicionário de dados extraídos/mapeados
        return extracted_data

    # Métodos de extração removidos - agora usando EnhancedCPEParser

    def _extract_weaknesses(self, weaknesses):
        """Extrai CWE IDs das weaknesses com melhor cobertura."""
        cwe_ids = set()
        
        # Prioridade de idiomas (inglês primeiro, depois outros)
        lang_priority = ['en', 'es', 'fr', 'de', 'pt', 'it']
        
        for weakness in weaknesses:
            descriptions = weakness.get('description', [])
            
            # Tentar extrair CWE em ordem de prioridade de idioma
            extracted = False
            for lang in lang_priority:
                if extracted:
                    break
                    
                for desc in descriptions:
                    if desc.get('lang') == lang:
                        value = desc.get('value', '').strip()
                        
                        # Formato padrão CWE-XXX
                        if value.startswith('CWE-') and len(value) > 4:
                            # Validar que após CWE- há números
                            cwe_number = value[4:]
                            if cwe_number.isdigit():
                                cwe_ids.add(value)
                                extracted = True
                                break
            
            # Se não encontrou CWE válido, tentar em qualquer idioma
            if not extracted:
                for desc in descriptions:
                    value = desc.get('value', '').strip()
                    if value.startswith('CWE-') and len(value) > 4:
                        cwe_number = value[4:]
                        if cwe_number.isdigit():
                            cwe_ids.add(value)
                            break
        
        return list(cwe_ids)
    
    def _validate_cve_data(self, cve_data: Dict[str, Any]) -> bool:
        """
        Valida os dados de uma CVE antes da gravação no banco.
        
        Args:
            cve_data: Dicionário com dados da CVE
            
        Returns:
            bool: True se os dados são válidos, False caso contrário
        """
        try:
            # Validações obrigatórias
            if not cve_data.get('cve_id'):
                terminal_feedback.error("❌ CVE ID é obrigatório")
                return False
            
            # Validar formato do CVE ID
            cve_id = cve_data['cve_id']
            if not cve_id.startswith('CVE-') or len(cve_id) < 8:
                terminal_feedback.error(f"❌ Formato inválido de CVE ID: {cve_id}")
                return False
            
            # Validar descrição
            description = cve_data.get('description', '')
            if not description or description == 'No description available.':
                terminal_feedback.warning(f"⚠️ CVE {cve_id} sem descrição válida")
            
            # Validar CVSS score
            cvss_score = cve_data.get('cvss_score')
            if cvss_score is not None and (cvss_score < 0 or cvss_score > 10):
                terminal_feedback.warning(f"⚠️ CVE {cve_id} com CVSS score inválido: {cvss_score}")
            
            # Validar datas
            published_date = cve_data.get('published_date')
            if published_date and not isinstance(published_date, datetime):
                terminal_feedback.warning(f"⚠️ CVE {cve_id} com data de publicação inválida")
            
            # Validar severidade
            base_severity = cve_data.get('base_severity', '')
            valid_severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'N/A']
            if base_severity not in valid_severities:
                terminal_feedback.warning(f"⚠️ CVE {cve_id} com severidade inválida: {base_severity}")
            
            # Validar estruturas de dados
            for field in ['cvss_metrics', 'vendors', 'products', 'weaknesses', 'references']:
                if field in cve_data and not isinstance(cve_data[field], list):
                    terminal_feedback.warning(f"⚠️ CVE {cve_id}: campo {field} deve ser uma lista")
            
            return True
            
        except Exception as e:
            terminal_feedback.error(f"❌ Erro na validação da CVE {cve_data.get('cve_id', 'unknown')}: {str(e)}")
            return False

    # TODO: Modificar o método update para receber uma instância do VulnerabilityService
    # e delegar a ele a lógica de persistência.
    async def update(self, vulnerability_service: 'VulnerabilityService', full: bool = False) -> int:
        """
        Atualiza o banco de dados com as últimas vulnerabilidades da NVD
        usando um serviço de persistência com feedback aprimorado.

        Args:
            vulnerability_service: Instância do serviço responsável pela persistência.
            full: Se True, ignora a última data de sincronização e busca todos os CVEs.

        Returns:
            O número total de vulnerabilidades processadas (salvas no DB).
        """
        # Usar sistema de feedback aprimorado
        sync_type = "completa" if full else "incremental"
        terminal_feedback.info(f"🔄 Iniciando sincronização NVD ({sync_type})", 
                             {"type": sync_type, "timestamp": datetime.now().isoformat()})

        # Exibir estatísticas iniciais
        nvd_stats.display_comprehensive_stats()
        
        # Obter logger aprimorado
        enhanced_logger = get_app_logger()
        
        # MONITORAMENTO DE MEMÓRIA: Inicializar monitoramento
        memory_monitor.log_memory_status("início da sincronização")
        system_memory = memory_monitor.get_system_memory_info()
        logger.info(f"Memória do sistema: {system_memory.get('available_gb', 0):.1f}GB disponível de {system_memory.get('total_gb', 0):.1f}GB total")
        
        # TODO: Mover a lógica de acesso a SyncMetadata para o VulnerabilityService.
        last_synced_time = None
        last_synced_time_str = None
        
        with enhanced_logger.operation_context("Verificação de sincronização anterior") as op_id:
            if not full:
                 # Buscar a última data de sincronização usando o serviço
                 last_synced_time = vulnerability_service.get_last_sync_time()
                 if last_synced_time:
                     # Converter datetime para string ISO 8601 no formato que a API espera (lastModifiedStart)
                     last_synced_time_str = last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                     terminal_feedback.success(f"Última sincronização encontrada: {last_synced_time_str}", 
                                             {"last_sync": last_synced_time_str})
                 else:
                     terminal_feedback.warning("Nenhuma sincronização anterior encontrada", 
                                             {"action": "Executando sincronização inicial"})
            else:
                 terminal_feedback.info("Sincronização completa solicitada", 
                                      {"ignore_last_sync": True})
            
            enhanced_logger.update_operation(op_id, progress=1.0, details="Verificação concluída")


        total_processed = 0 # Total de itens processados E SALVOS no DB
        start_index = 0
        total_results_expected = None # Para rastrear o total de resultados para a query


        # Usar um try/finally para garantir o rollback ou commit da sessão NO SERVIÇO
        # A sessão é gerenciada pelo serviço. O fetcher não faz commit/rollback direto.
        try:
            # Preparar janelas de tempo quando incremental excede o limite da NVD
            windows: List[Dict[str, str]] = []
            if not full and last_synced_time:
                # Converter para timezone UTC consciente
                last_dt = last_synced_time if last_synced_time.tzinfo else last_synced_time.replace(tzinfo=timezone.utc)
                last_dt = last_dt.astimezone(timezone.utc)
                now_dt = datetime.now(timezone.utc)
                # Construir janelas de até max_window_days
                if (now_dt - last_dt).days > self.max_window_days:
                    logger.warning(
                        f"Janela incremental de {(now_dt - last_dt).days} dias excede o limite de {self.max_window_days} dias. Aplicando chunking por janelas.")
                    cursor = last_dt
                    while cursor <= now_dt:
                        window_end = min(cursor + timedelta(days=self.max_window_days), now_dt)
                        windows.append({
                            'start': cursor.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                            'end': window_end.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                        })
                        # Avança 1 segundo para evitar reprocessar o mesmo registro no limite inclusivo
                        cursor = window_end + timedelta(seconds=1)
                else:
                    # Uma única janela dentro do limite
                    windows.append({
                        'start': last_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                        'end': now_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                    })

            # Indicador de sucesso global
            global_success = True

            # Se não é incremental (full) ou não há last_sync, executar loop único
            if full or not windows:
                windows = [{'start': None, 'end': None}]  # Sem filtros de data

            # Processar cada janela separadamente com paginação própria
            for idx, win in enumerate(windows):
                start_index = 0
                total_results_expected = None
                win_start = win['start']
                win_end = win['end']
                if win_start and win_end:
                    terminal_feedback.info(
                        f"🗓️ Processando janela {idx+1}/{len(windows)}: {win_start} → {win_end}",
                        {"window_index": idx+1, "windows_total": len(windows)}
                    )

                while True:
                    # Passar parâmetros de janela ao fetch_page
                    data = await self.fetch_page(start_index, win_start, win_end)

                    if data is None:
                        logger.error("Failed to fetch data from NVD API. Stopping update process.")
                        # Não atualiza a data de sincronização em caso de falha fatal no fetch
                        global_success = False
                        break  # Sair do loop da janela atual

                    vulnerabilities_data_raw = data.get('vulnerabilities', [])
                    total_results_on_api = data.get('totalResults', 0)

                    if total_results_expected is None:
                        total_results_expected = total_results_on_api
                        logger.info(f"Total results for this query range expected: {total_results_expected}")
                        # TODO: Opcional: Usar tqdm com o total esperado
                        # pbar = tqdm.tqdm(total=total_results_expected, desc='Processing CVEs')

                    if not vulnerabilities_data_raw:
                        # Se a página atual retornou vazio e não há mais resultados esperados (ou chegamos ao fim teórico)
                        # A API geralmente retorna totalResults > current_index mesmo na última página com dados,
                        # mas é mais seguro verificar se a lista está vazia E chegamos ou passamos o total esperado.
                        if start_index >= total_results_expected:  # Usar total_results_expected para controle
                            logger.info("Reached end of results for current window.")
                            break  # Sair do loop se não houver mais dados nesta página E for o fim esperado
                        else:
                            # Se a página atual retornou vazio, mas ainda há resultados esperados (API inconsistência?)
                            logger.warning(
                                f"Page {start_index} returned no vulnerabilities, but total results suggest more data ({total_results_expected}). API issue? Stopping for safety.")
                            break  # Parar por segurança

                    # OTIMIZAÇÃO DE MEMÓRIA: Processar dados em lotes menores para reduzir uso de memória
                    import gc  # Para garbage collection explícito

                    MEMORY_BATCH_SIZE = 50  # Processar em lotes menores para evitar estouro de memória

                    # Processar vulnerabilidades em mini-lotes para otimizar memória
                    for i in range(0, len(vulnerabilities_data_raw), MEMORY_BATCH_SIZE):
                        batch = vulnerabilities_data_raw[i:i + MEMORY_BATCH_SIZE]

                        # Processar lote atual
                        processed_data_list = []
                        for item in batch:
                            # process_cve_data AGORA retorna um dicionário/DTO, não um objeto ORM
                            extracted_data = await self.process_cve_data(item.get('cve'))
                            if extracted_data:  # Se a extração/mapeamento foi bem-sucedido
                                processed_data_list.append(extracted_data)

                        # Salvar mini-lote imediatamente para liberar memória
                        if processed_data_list:
                            try:
                                # Validar dados antes de salvar
                                valid_data = []
                                for data in processed_data_list:
                                    if self._validate_cve_data(data):
                                        valid_data.append(data)
                                    else:
                                        terminal_feedback.warning(
                                            f"⚠️ Dados inválidos para CVE {data.get('cve_id', 'unknown')}")

                                if valid_data:
                                    # O serviço lida com a criação/atualização dos objetos ORM e o commit em lote.
                                    processed_count_batch = vulnerability_service.save_vulnerabilities_batch(valid_data)
                                    total_processed += processed_count_batch  # Acumula o total processado PELO SERVIÇO

                                    # Feedback de progresso
                                    terminal_feedback.info(
                                        f"📦 Mini-lote {i//MEMORY_BATCH_SIZE + 1} processado",
                                        {
                                            "cves_processadas": processed_count_batch,
                                            "total_acumulado": total_processed,
                                            "memoria_mb": memory_monitor.get_memory_usage_mb()
                                        }
                                    )

                                    logger.debug(
                                        f"Processed mini-batch {i//MEMORY_BATCH_SIZE + 1} with {processed_count_batch} CVEs")
                                else:
                                    terminal_feedback.warning(
                                        f"⚠️ Nenhum dado válido no mini-lote {i//MEMORY_BATCH_SIZE + 1}")

                            except Exception as service_error:
                                # Captura erros que ocorreram no serviço de persistência
                                logger.error(f"Error saving vulnerability mini-batch: {service_error}", exc_info=True)
                                terminal_feedback.error(f"❌ Erro ao salvar mini-lote: {str(service_error)}")
                                logger.error("Stopping update due to service persistence error.")
                                raise  # Re-raise para parar o processamento

                        # Limpar referências para liberar memória
                        del processed_data_list
                        del batch

                        # Garbage collection periódico para mini-lotes
                        if i % (MEMORY_BATCH_SIZE * 2) == 0:
                            gc.collect()

                    # Limpar dados da página atual para liberar memória
                    del vulnerabilities_data_raw

                    logger.info(f"Completed page starting at index {start_index}. Total processed: {total_processed}")

                    # Verificar se há mais páginas a buscar com base no totalResults esperado
                    # Isso pode ser um pouco impreciso se o totalResults mudar durante a execução,
                    # mas é uma boa heurística. A condição principal de saída é quando fetch_page
                    # retorna uma lista vazia E index >= total_results_expected.
                    if start_index + self.page_size >= total_results_expected:  # Usar self.page_size
                        logger.info("Reached end of results for current window based on totalResults estimate.")
                        # Verifica se realmente não há mais dados na próxima chamada
                        # (já coberto pela lógica de 'not vulnerabilities_data' no início do loop)
                        pass  # Continua o loop para a próxima fetch_page, que deve retornar vazio

                    # Avançar para o próximo índice
                    start_index += self.page_size  # Usar self.page_size

                    # OTIMIZAÇÃO DE MEMÓRIA: Monitoramento e garbage collection periódico entre páginas
                    page_number = start_index // self.page_size
                    if page_number % 5 == 0:  # A cada 5 páginas
                        # Verificar status da memória e executar GC se necessário
                        gc_stats = memory_monitor.auto_manage_memory(f"após página {page_number}")
                        if gc_stats:
                            logger.info(
                                f"GC automático executado: {gc_stats['objects_collected']} objetos, {gc_stats['memory_freed_mb']:.1f}MB liberados")
                        else:
                            gc.collect()  # GC regular

                        memory_monitor.log_memory_status(f"página {page_number}")
                        logger.debug(f"Executed garbage collection after {page_number} pages")

                # Adicionar um pequeno delay entre as páginas, além do rate limit interno do fetch_page
                # Isso pode ser útil se a API tiver limites por minuto/hora além do por segundo.
                # await asyncio.sleep(1) # Exemplo: espera 1 segundo entre as páginas


            # TODO: pbar.close() # Fechar barra de progresso

            # --- Atualizar a data da última sincronização ---
            # Atualizar a data somente se a operação foi bem-sucedida (sem falhas fatais no fetch ou save)
            # Uma operação bem-sucedida significa que o loop principal não foi interrompido por um erro.
            # Podemos usar uma flag ou verificar se chegamos ao fim esperado (index >= total_results_expected ou total_results_expected == 0).
            # Sucesso se todas as janelas completaram sem falha
            sync_completed_successfully = global_success

            if sync_completed_successfully:
                 # Atualizar a data da última sincronização usando o serviço
                 vulnerability_service.update_last_sync_time(datetime.utcnow()) # Passar datetime.utcnow()

            else:
                logger.warning("Sync operation did not complete successfully. Last sync time not updated via service.")

        except Exception as e:
             # Capturar quaisquer erros inesperados durante a orquestração do update
             logger.error("An unexpected error occurred during the NVD update process.", exc_info=True)
             # TODO: A sessão do serviço já deve ter feito rollback em caso de erro
             # self.db_session.rollback() # Remover - sessão gerenciada pelo serviço


        # MONITORAMENTO DE MEMÓRIA: Log final de estatísticas
        memory_stats = memory_monitor.get_memory_stats()
        memory_monitor.log_memory_status("final da sincronização")
        logger.info(f"Estatísticas de memória - Pico: {memory_stats['peak_mb']:.1f}MB, "
                   f"Aumento: +{memory_stats['increase_mb']:.1f}MB, "
                   f"GCs executados: {memory_stats['gc_count']}")
        
        # Exibir estatísticas finais
        terminal_feedback.success(f"✅ Sincronização NVD concluída!", 
                                {"processed": total_processed, "type": sync_type})
        
        # Mostrar estatísticas atualizadas
        nvd_stats.display_comprehensive_stats()
        
        # Exibir progresso da sincronização
        progress_info = nvd_stats.get_sync_progress_info()
        if progress_info and progress_info.get('is_syncing'):
            terminal_feedback.info(f"📊 Progresso da sincronização:", progress_info)
        
        logger.info(f"NVD update job finished. Total vulnerabilities processed (and saved by service): {total_processed}.")
        return total_processed


# --- Lógica para execução como script standalone ---

# Mover a lógica de configuração básica para uma função de setup
def setup_standalone_script(env_name: str = None) -> Flask:
     """Cria e configura a aplicação Flask para execução standalone."""
     # Importar a fábrica de aplicação principal
     from app import create_app # Importação CORRETA da fábrica

     # TODO: Passar args.config para create_app se necessário para carregar ambiente específico
     #create_app já deve carregar a config com base no env_name
     app = create_app(env_name=env_name) # Usar a fábrica principal com ambiente opcional

     # O contexto da aplicação já é gerenciado por create_app e o with statement
     # As extensões já são inicializadas por create_app

     return app

# Adicionar parser de argumentos de linha de comando
parser = argparse.ArgumentParser(description="NVD Fetcher Job: Sync CVEs from NVD API.")
parser.add_argument(
    '--full',
    action='store_true',
    help='Perform a full synchronization instead of incremental.'
)
parser.add_argument(
    '--config',
    type=str,
    default=None,
    help='Flask environment configuration (e.g., development, production).'
)


if __name__ == '__main__':
    args = parser.parse_args()

    # Configurar e obter a aplicação Flask
    # Passar o nome do ambiente, se fornecido via argumento --config
    app = setup_standalone_script(env_name=args.config)

    # Rodar dentro do contexto da aplicação para ter acesso a app.config e db.session
    with app.app_context():
        # A instância db.session já está disponível aqui
        # TODO: Garantir que o logging é configurado corretamente no contexto do job standalone
        # (Pode ser feito no setup_standalone_script ou globalmente se não conflitar)

        # Obter configurações necessárias de app.config para passar para o fetcher
        # Acessar app.config APÓS criar o app e dentro do app_context
        nvd_config = {
            "NVD_API_BASE": getattr(app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
            "NVD_API_KEY": getattr(app.config, 'NVD_API_KEY', None),
            "NVD_PAGE_SIZE": getattr(app.config, 'NVD_PAGE_SIZE', 2000),
            "NVD_MAX_RETRIES": getattr(app.config, 'NVD_MAX_RETRIES', 5),
            "NVD_RATE_LIMIT": getattr(app.config, 'NVD_RATE_LIMIT', (2, 1)),
            "NVD_CACHE_DIR": getattr(app.config, 'NVD_CACHE_DIR', "cache"),
            "NVD_REQUEST_TIMEOUT": getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
            "NVD_USER_AGENT": getattr(app.config, 'NVD_USER_AGENT', "Sec4all.co NVD Fetcher"), # Exemplo de outra config
            "NVD_MAX_WINDOW_DAYS": getattr(app.config, 'NVD_MAX_WINDOW_DAYS', 120),
        }

        # Validar configurações essenciais (ex: API_BASE)
        if not nvd_config.get("NVD_API_BASE"):
             logger.error("NVD_API_BASE configuration is missing in app.config. Cannot run fetcher.")
             sys.exit(1) # Sair com código de erro
        
        # Usar aiohttp.ClientSession dentro de um bloco async with para garantir que seja fechada
        async def run_fetcher():
            async with aiohttp.ClientSession() as http_session:
                # Instanciar o fetcher, passando a sessão HTTP e as configurações
                fetcher = NVDFetcher(http_session, nvd_config)

                # Criar instância do VulnerabilityService (módulo dentro de app)
                from app.services.vulnerability_service import VulnerabilityService
                vulnerability_service = VulnerabilityService(db.session)

                # Rodar o update assíncrono, passando o serviço
                processed_count = await fetcher.update(vulnerability_service=vulnerability_service, full=args.full)

                logger.info(f"NVD Fetcher job finished. Processed {processed_count} CVEs.")

        # Rodar a função assíncrona principal
        try:
            asyncio.run(run_fetcher())
            sys.exit(0)
        except Exception as e:
            logger.error("An error occurred during the asyncio run.", exc_info=True)
            sys.exit(1) # Sair com código de erro em caso de falha

    # Execução finalizada
    logger.info("Standalone script execution finished.")

import sys
import os
import time
import pickle
import asyncio
import logging
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional # Importar Optional explicitamente
from pathlib import Path # Importar Path explicitamente

import aiohttp
import tqdm
from flask import Flask # current_app não é necessário aqui, pois estamos em um contexto de job standalone
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Use importações relativas CORRETAS para módulos DENTRO do pacote project
# Assumindo que o pacote 'project' é o diretório pai de 'jobs'
from ..extensions import db # Importa db do pacote extensions (__init__.py)
# Importações CORRETAS dos modelos (Assumindo que estão em project/models)
from ..models.sync_metadata import SyncMetadata
from ..models.vulnerability import Vulnerability
# from ..models.api_call_log import ApiCallLog # Importar se o modelo for usado aqui
# from ..services.vulnerability_service import VulnerabilityService # Importar após criar o serviço

logger = logging.getLogger(__name__)

# TODO: Garantir que estas configurações sejam carregadas da configuração da aplicação Flask (app.config)
# A classe NVDFetcher deve recebê-las via __init__.
# CACHE_DIR = Path('cache') # O caminho do cache deve ser configurável (obtido da config)
# API_BASE    = os.getenv("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0") # Obtido da config
# API_KEY     = os.getenv("NVD_API_KEY", None) # Obtido da config
# PAGE_SIZE   = 2000 # Obtido da config
# MAX_RETRIES = 5 # Obtido da config
# RATE_LIMIT  = (2, 1)  # 2 requests per 1 sec (para a API Key Gratuita) # Obtido da config


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
        self.rate_limit_requests, self.rate_limit_window = self.config.get("NVD_RATE_LIMIT", (2, 1))
        self.cache_dir = Path(self.config.get("NVD_CACHE_DIR", "cache"))
        self.request_timeout = self.config.get("NVD_REQUEST_TIMEOUT", 30)
        self.user_agent = self.config.get("NVD_USER_AGENT", "Sec4all.co NVD Fetcher")


        self.headers = {"User-Agent": self.user_agent}
        if self.api_key:
             self.headers["apiKey"] = self.api_key

        self.request_times: List[float] = [] # Lista para controle de rate limit


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


    async def fetch_page(self, start_index: int, last_modified_start: Optional[str]) -> Optional[Dict]:
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
        # --- Controle de rate limit ---
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_window] # Usar self.rate_limit_window
        if len(self.request_times) >= self.rate_limit_requests: # Usar self.rate_limit_requests
            wait_time = self.rate_limit_window - (now - self.request_times[0])
            logger.warning(f"Rate limit hit. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(max(wait_time, 0))
        self.request_times.append(time.time())

        # --- Cacheamento básico em arquivo ---
        self.cache_dir.mkdir(exist_ok=True) # Usar self.cache_dir
        # Garante que o nome do cache é único para buscas full vs modificadas
        cache_key_suffix = last_modified_start.replace(":", "").replace("+", "_") if last_modified_start else "full"
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
            url += f"&lastModifiedStart={last_modified_start}"
            # Opcional: adicionar lastModifiedEnd=datetime.utcnow().isoformat() para um intervalo fechado

        logger.info(f"Fetching page {start_index} from NVD API (modified since {last_modified_start or 'epoch'}). URL: {url}")

        # --- Tenta buscar a página com retries ---
        for attempt in range(self.max_retries): # Usar self.max_retries
            try:
                # Adiciona cabeçalho de API Key condicionalmente
                headers_with_key = {**self.headers} # Copia cabeçalhos base (inclui User-Agent)
                if self.api_key:
                     headers_with_key["apiKey"] = self.api_key # Adiciona API Key se presente

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
                        retry_after = int(resp.headers.get("Retry-After", 5)) # Default 5 seg
                        logger.warning(f"Rate limit exceeded for page {start_index}. Retrying in {retry_after} seconds (Attempt {attempt + 1}/{self.max_retries}).") # Usar self.max_retries
                        await asyncio.sleep(retry_after)
                        continue # Tentar novamente

                    elif resp.status >= 500: # Server Error
                         wait_time = 2**(attempt + 1) # Backoff exponencial
                         logger.error(f"API Server Error {resp.status} for page {start_index}. Retrying in {wait_time} seconds (Attempt {attempt + 1}/{self.max_retries}).") # Usar self.max_retries
                         await asyncio.sleep(wait_time)
                         continue # Tentar novamente

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
            if desc.get('lang') == 'en'):
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


        # Extrair métricas CVSS de todas as versões disponíveis
        base_severity = 'UNKNOWN'
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
                    # Extrair dados base comuns a todas as versões
                    metric_info = {
                        'cvss_version': version,
                        'base_score': float(cvss_data.get('baseScore', 0.0)),
                        'base_severity': cvss_data.get('baseSeverity', 'UNKNOWN').upper(),
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
        
        # Definir score e severidade principais baseados na prioridade
        for priority_key in priority_order:
            if priority_key in cvss_version_map:
                version = cvss_version_map[priority_key]
                primary_metrics = [m for m in cvss_metrics if m['cvss_version'] == version and m['is_primary']]
                if primary_metrics:
                    primary_metric = primary_metrics[0]
                    cvss_score = primary_metric['base_score']
                    base_severity = primary_metric['base_severity']
                    break

        # TODO: Extrair e mapear outros dados relevantes: references, configurations (CPEs), weakness (CWEs), etc.
        # Estes também devem ser mapeados para seus respectivos modelos e relacionados à Vulnerabilidade.


        # Em uma refatoração completa, isto retornaria um dicionário ou DTO
        # que representa os dados prontos para serem passados para o serviço de persistência.
        extracted_data = {
             "cve_id": cve_id,
             "description": description,
             "published_date": published_date,
             "last_modified": last_modified,
             "base_severity": base_severity,
             "cvss_score": cvss_score,
             "cvss_metrics": cvss_metrics,  # Lista completa de métricas CVSS
             # TODO: Incluir outros dados extraídos/mapeados (references, cpes, cwes, etc.)
             "raw_data": cve_data # Opcional: armazenar o JSON bruto para referência
        }
        # NOVO: Retornar o dicionário de dados extraídos/mapeados
        return extracted_data


    # TODO: Modificar o método update para receber uma instância do VulnerabilityService
    # e delegar a ele a lógica de persistência.
    async def update(self, vulnerability_service: 'VulnerabilityService', full: bool = False) -> int:
        """
        Atualiza o banco de dados com as últimas vulnerabilidades da NVD
        usando um serviço de persistência.

        Args:
            vulnerability_service: Instância do serviço responsável pela persistência.
            full: Se True, ignora a última data de sincronização e busca todos os CVEs.

        Returns:
            O número total de vulnerabilidades processadas (salvas no DB).
        """
        logger.info(f"Starting NVD update job (full={full}).")

        # TODO: Mover a lógica de acesso a SyncMetadata para o VulnerabilityService.
        last_synced_time = None
        if not full:
             # Buscar a última data de sincronização usando o serviço
             last_synced_time = vulnerability_service.get_last_sync_time()
             if last_synced_time:
                 # Converter datetime para string ISO 8601 no formato que a API espera (lastModifiedStart)
                 last_synced_time_str = last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                 logger.info(f"Last sync time found: {last_synced_time_str}")
             else:
                 logger.info("No last sync time found. Performing initial (potentially full) sync.")
                 last_synced_time_str = None # Garantir que é None se não encontrado e não for full


        total_processed = 0 # Total de itens processados E SALVOS no DB
        start_index = 0
        total_results_expected = None # Para rastrear o total de resultados para a query


        # Usar um try/finally para garantir o rollback ou commit da sessão NO SERVIÇO
        # A sessão é gerenciada pelo serviço. O fetcher não faz commit/rollback direto.
        try:
            while True:
                # Passar last_synced_time_str (ISO 8601) para fetch_page
                data = await self.fetch_page(start_index, last_synced_time_str)

                if data is None:
                    logger.error("Failed to fetch data from NVD API. Stopping update process.")
                    # Não atualiza a data de sincronização em caso de falha fatal no fetch
                    break # Sair do loop principal

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
                    if start_index >= total_results_expected: # Usar total_results_expected para controle
                         logger.info("Reached end of results.")
                         break # Sair do loop se não houver mais dados nesta página E for o fim esperado
                    else:
                        # Se a página atual retornou vazio, mas ainda há resultados esperados (API inconsistência?)
                        logger.warning(f"Page {start_index} returned no vulnerabilities, but total results suggest more data ({total_results_expected}). API issue? Stopping for safety.")
                        break # Parar por segurança


                # Processar dados brutos para extrair informações relevantes usando o método do fetcher
                processed_data_list = []
                for item in vulnerabilities_data_raw:
                    # process_cve_data AGORA retorna um dicionário/DTO, não um objeto ORM
                    extracted_data = await self.process_cve_data(item.get('cve'))

                    if extracted_data: # Se a extração/mapeamento foi bem-sucedido
                        processed_data_list.append(extracted_data)


                # Passar os dados extraídos para o serviço de persistência para salvar em lote
                if processed_data_list:
                    try:
                        # O serviço lida com a criação/atualização dos objetos ORM e o commit em lote.
                        # O serviço retorna o número de itens SALVOS/PROCESSADOS no lote.
                        processed_count_batch = vulnerability_service.save_vulnerabilities_batch(processed_data_list)
                        total_processed += processed_count_batch # Acumula o total processado PELO SERVIÇO
                        logger.info(f"Service processed and saved {processed_count_batch} vulnerabilities for page starting at index {start_index}.")
                    except Exception as service_error:
                         # Captura erros que ocorreram no serviço de persistência
                         logger.error(f"Error saving vulnerability batch for page {start_index}: {service_error}", exc_info=True)
                         # Decida se para o job ou tenta continuar (pode perder dados)
                         # Parar pode ser mais seguro em caso de erro de DB no serviço.
                         logger.error("Stopping update due to service persistence error.")
                         # TODO: A sessão do serviço já deve ter feito rollback em caso de erro
                         break # Sair do loop principal

                else:
                     logger.debug(f"No valid data to process for page starting at index {start_index}.")


                # Verificar se há mais páginas a buscar com base no totalResults esperado
                # Isso pode ser um pouco impreciso se o totalResults mudar durante a execução,
                # mas é uma boa heurística. A condição principal de saída é quando fetch_page
                # retorna uma lista vazia E index >= total_results_expected.
                if start_index + self.page_size >= total_results_expected: # Usar self.page_size
                    logger.info("Reached end of results based on totalResults estimate.")
                    # Verifica se realmente não há mais dados na próxima chamada
                    # (já coberto pela lógica de 'not vulnerabilities_data' no início do loop)
                    pass # Continua o loop para a próxima fetch_page, que deve retornar vazio

                # Avançar para o próximo índice
                start_index += self.page_size # Usar self.page_size

                # Adicionar um pequeno delay entre as páginas, além do rate limit interno do fetch_page
                # Isso pode ser útil se a API tiver limites por minuto/hora além do por segundo.
                # await asyncio.sleep(1) # Exemplo: espera 1 segundo entre as páginas


            # TODO: pbar.close() # Fechar barra de progresso

            # --- Atualizar a data da última sincronização ---
            # Atualizar a data somente se a operação foi bem-sucedida (sem falhas fatais no fetch ou save)
            # Uma operação bem-sucedida significa que o loop principal não foi interrompido por um erro.
            # Podemos usar uma flag ou verificar se chegamos ao fim esperado (index >= total_results_expected ou total_results_expected == 0).
            sync_completed_successfully = (data is not None) and (start_index >= total_results_expected or total_results_expected == 0) # Sucesso se buscou tudo ou não havia nada

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


        logger.info(f"NVD update job finished. Total vulnerabilities processed (and saved by service): {total_processed}.")
        return total_processed


# --- Lógica para execução como script standalone ---

# Mover a lógica de configuração básica para uma função de setup
def setup_standalone_script(env_name: str = None) -> Flask:
     """Cria e configura a aplicação Flask para execução standalone."""
     # Importar a fábrica de aplicação principal
     from project.app import create_app # Importação CORRETA da fábrica

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
            "NVD_API_BASE": app.config.get("NVD_API_BASE"),
            "NVD_API_KEY": app.config.get("NVD_API_KEY"),
            "NVD_PAGE_SIZE": app.config.get("NVD_PAGE_SIZE", 2000),
            "NVD_MAX_RETRIES": app.config.get("NVD_MAX_RETRIES", 5),
            "NVD_RATE_LIMIT": app.config.get("NVD_RATE_LIMIT", (2, 1)),
            "NVD_CACHE_DIR": app.config.get("NVD_CACHE_DIR", "cache"),
            "NVD_REQUEST_TIMEOUT": app.config.get("NVD_REQUEST_TIMEOUT", 30),
             "NVD_USER_AGENT": app.config.get("NVD_USER_AGENT", "Sec4all.co NVD Fetcher"), # Exemplo de outra config
        }

        # Validar configurações essenciais (ex: API_BASE)
        if not nvd_config.get("NVD_API_BASE"):
             logger.error("NVD_API_BASE configuration is missing in app.config. Cannot run fetcher.")
             sys.exit(1) # Sair com código de erro

        # TODO: Importar e instanciar o VulnerabilityService aqui, passando db.session para ele
        # from ..services.vulnerability_service import VulnerabilityService
        # vulnerability_service = VulnerabilityService(db.session)
        # REMOVER a linha abaixo após implementar o serviço
        logger.warning("VulnerabilityService not yet implemented. Persistence logic is still in NVDFetcher (TODO).") # Placeholder

        # Usar aiohttp.ClientSession dentro de um bloco async with para garantir que seja fechada
        async def run_fetcher():
             async with aiohttp.ClientSession() as http_session:
                # Instanciar o fetcher, passando a sessão HTTP e as configurações
                # TODO: Passar a instância do VulnerabilityService para o fetcher
                fetcher = NVDFetcher(http_session, nvd_config) # Remover db.session do init do fetcher

                # Rodar o update assíncrono, passando o serviço (após implementá-lo)
                # TODO: Chamar await fetcher.update(vulnerability_service=vulnerability_service, full=args.full)
                # REMOVER a linha abaixo após implementar o serviço e o update refatorado
                logger.warning("NVDFetcher.update is called with internal DB logic (TODO: use VulnerabilityService).") # Placeholder
                # Chamada temporária da versão antiga do update (que usa db.session direto)
                fetcher.db_session = db.session # ATENÇÃO: Isso quebra a separação. APENAS PARA TESTE TEMPORÁRIO.
                processed_count = await fetcher.update(full=args.full)


                logger.info(f"NVD Fetcher job finished. Processed {processed_count} CVEs.")

        # Rodar a função assíncrona principal
        try:
            asyncio.run(run_fetcher())
        except Exception as e:
            logger.error("An error occurred during the asyncio run.", exc_info=True)
            sys.exit(1) # Sair com código de erro em caso de falha

    # Considerar adicionar um sys.exit(0) para sucesso explícito se a lógica acima não levantar exceção
    logger.info("Standalone script execution finished.")
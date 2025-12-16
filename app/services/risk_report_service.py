import os
import re
import logging
import json
import hashlib
from typing import Dict, Any, Optional
from types import SimpleNamespace
import requests
from openai import OpenAI
from flask import current_app
from sqlalchemy import text, inspect
from app.extensions import db
from app.models.vulnerability import Vulnerability

logger = logging.getLogger(__name__)

class RiskReportService:
    """
    Serviço para geração de relatórios de risco de vulnerabilidades usando OpenAI.
    
    Baseado no código de exemplo fornecido, este serviço gera análises
    detalhadas de risco em formato Markdown para vulnerabilidades CVE.
    """
    
    def __init__(self):
        """
        Inicializa o serviço de relatórios de risco.
        """
        self.client = None
        self._initialized = False
        self.timeout = 30
        self.max_retries = 2
        self.backoff_base = 1.5
    
    def _initialize_client(self):
        """
        Inicializa o cliente OpenAI dentro do contexto da aplicação.
        """
        if self._initialized:
            return
            
        provider = (current_app.config.get('LLM_PROVIDER') or os.getenv('LLM_PROVIDER') or 'openai').lower()
        self.provider = provider
        self.api_key = (
            current_app.config.get('LLM_API_KEY')
            or current_app.config.get('OPENAI_API_KEY')
            or os.getenv('LLM_API_KEY')
            or os.getenv('OPENAI_API_KEY')
        )
        self.model = (
            current_app.config.get('LLM_MODEL')
            or current_app.config.get('OPENAI_MODEL')
            or os.getenv('LLM_MODEL')
            or os.getenv('OPENAI_MODEL')
            or 'gpt-3.5-turbo'
        )
        self.max_tokens = current_app.config.get('OPENAI_MAX_TOKENS', 800)
        self.temperature = current_app.config.get('OPENAI_TEMPERATURE', 0.5)
        self.timeout = current_app.config.get('OPENAI_TIMEOUT', 30)
        self.max_retries = current_app.config.get('OPENAI_MAX_RETRIES', 2)
        self.backoff_base = current_app.config.get('OPENAI_RETRY_BACKOFF', 1.5)
        self.base_url = current_app.config.get('LLM_BASE_URL') or os.getenv('LLM_BASE_URL') or None
        self.completion_param = (current_app.config.get('LLM_COMPLETION_TOKENS_PARAM') or os.getenv('LLM_COMPLETION_TOKENS_PARAM') or '').lower()
        self.top_p = current_app.config.get('OPENAI_TOP_P') or os.getenv('OPENAI_TOP_P')
        self.presence_penalty = current_app.config.get('OPENAI_PRESENCE_PENALTY') or os.getenv('OPENAI_PRESENCE_PENALTY')
        self.frequency_penalty = current_app.config.get('OPENAI_FREQUENCY_PENALTY') or os.getenv('OPENAI_FREQUENCY_PENALTY')
        self.stop_sequences = current_app.config.get('OPENAI_STOP') or os.getenv('OPENAI_STOP')
        self.system_prompt = (
            current_app.config.get('LLM_SYSTEM_PROMPT')
            or os.getenv('LLM_SYSTEM_PROMPT')
            or current_app.config.get('OPENAI_SYSTEM_PROMPT')
            or os.getenv('OPENAI_SYSTEM_PROMPT')
            or None
        )
        
        try:
            if self.provider in ('openai','openai_compatible','deepseek','lmstudio'):
                # Defaults for LM Studio when not provided
                if self.provider == 'lmstudio' and not self.base_url:
                    self.base_url = 'http://localhost:1234/v1'
                # LM Studio may not require an API key; use placeholder if missing
                if self.provider == 'lmstudio' and not self.api_key:
                    self.api_key = 'lm-studio'
                # For official OpenAI provider, ignore custom base_url to avoid misconfiguration
                if self.provider == 'openai' and self.base_url and not str(self.base_url).startswith('https://api.openai.com'):
                    logger.warning("LLM_BASE_URL detectado mas ignorado para provider=openai. Usando endpoint oficial.")
                    self.base_url = None
                if not self.api_key:
                    logger.warning("LLM_API_KEY/OPENAI_API_KEY não configurada - modo demo ativo")
                    self.client = None
                else:
                    if self.base_url:
                        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                    else:
                        self.client = OpenAI(api_key=self.api_key)
            elif self.provider in ('gemini','google'):
                self.client = None
            logger.info("Cliente LLM inicializado com sucesso (provider=%s)" % self.provider)
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente LLM: {e}")
            self.client = None
        
        self._initialized = True

    def _chat_completion_with_retries(self, messages):
        attempt = 0
        last_err = None
        while attempt < max(1, int(self.max_retries)):
            try:
                if self.provider in ('gemini','google'):
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                    content = "\n".join([m.get('content','') for m in messages])
                    payload = {"contents": [{"role": "user", "parts": [{"text": content}]}]}
                    r = requests.post(url, json=payload, timeout=self.timeout)
                    r.raise_for_status()
                    data = r.json()
                    text = ''
                    try:
                        text = (data.get('candidates') or [{}])[0].get('content', {}).get('parts', [{}])[0].get('text') or ''
                    except Exception:
                        text = ''
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))], usage=None)
                else:
                    # Escolha do endpoint conforme modelo
                    use_responses = (self.provider == 'openai' and str(self.model).lower().startswith('gpt-5'))
                    if use_responses:
                        # OpenAI Responses API requer 'max_output_tokens' e usa 'input'/'instructions'
                        content_join = "\n".join([m.get('content','') for m in messages if m.get('content')])
                        kwargs: Dict[str, Any] = {
                            "model": self.model,
                            "input": content_join,
                            "temperature": self.temperature,
                        }
                        try:
                            sys_msgs = [m.get('content','') for m in messages if m.get('role') == 'system']
                            if sys_msgs:
                                kwargs['instructions'] = sys_msgs[0]
                            elif getattr(self, 'system_prompt', None):
                                kwargs['instructions'] = self.system_prompt
                        except Exception:
                            pass
                        # tokens param para Responses API
                        kwargs['max_output_tokens'] = int(self.max_tokens)
                        if self.top_p is not None:
                            try:
                                kwargs['top_p'] = float(self.top_p)
                            except Exception:
                                pass
                        try:
                            logger.info(
                                f"LLM request (responses): provider={self.provider}, model={self.model}, max_output_tokens={self.max_tokens}"
                            )
                        except Exception:
                            pass
                        return self.client.responses.create(**kwargs)
                    else:
                        kwargs: Dict[str, Any] = {
                            "model": self.model,
                            "messages": messages,
                            "temperature": self.temperature,
                            "stream": False,
                        }
                        def _requires_max_completion_tokens(model: Optional[str]) -> bool:
                            m = (model or '').lower()
                            prefixes = (
                                'gpt-5',
                                'gpt-4.1',
                                'gpt-4o',
                                'o1',
                                'o3',
                                'o4',
                            )
                            return any(m.startswith(p) for p in prefixes)
                        requires_completion = _requires_max_completion_tokens(self.model)
                        p = (getattr(self, 'completion_param', '') or '').strip().lower()
                        if p == 'max_completion_tokens':
                            kwargs['max_completion_tokens'] = self.max_tokens
                        elif p == 'max_tokens':
                            if requires_completion:
                                kwargs['max_completion_tokens'] = self.max_tokens
                            else:
                                kwargs['max_tokens'] = self.max_tokens
                        else:
                            if requires_completion:
                                kwargs['max_completion_tokens'] = self.max_tokens
                            else:
                                kwargs['max_tokens'] = self.max_tokens
                        if self.top_p is not None:
                            try:
                                kwargs['top_p'] = float(self.top_p)
                            except Exception:
                                pass
                        if self.presence_penalty is not None:
                            try:
                                kwargs['presence_penalty'] = float(self.presence_penalty)
                            except Exception:
                                pass
                        if self.frequency_penalty is not None:
                            try:
                                kwargs['frequency_penalty'] = float(self.frequency_penalty)
                            except Exception:
                                pass
                        if self.stop_sequences:
                            try:
                                stops = [s for s in re.split(r"[|,]", str(self.stop_sequences)) if s.strip()]
                                if stops:
                                    kwargs['stop'] = stops
                            except Exception:
                                pass
                        try:
                            logger.info(
                                f"LLM request (chat): provider={self.provider}, model={self.model}, param={'max_completion_tokens' if 'max_completion_tokens' in kwargs else 'max_tokens'}, max={self.max_tokens}"
                            )
                        except Exception:
                            pass
                        return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                last_err = e
                attempt += 1
                if attempt >= int(self.max_retries):
                    break
                import time as _time
                sleep_secs = (self.backoff_base ** attempt)
                logger.warning(f"OpenAI falhou (tentativa {attempt}/{self.max_retries}): {e}. Retentando em {sleep_secs:.2f}s...")
                _time.sleep(sleep_secs)
        raise last_err if last_err else RuntimeError("Falha ao consultar OpenAI para análise de risco")

    def _compute_vuln_signature(self, vulnerability: Vulnerability) -> str:
        try:
            parts = [
                vulnerability.cve_id or '',
                vulnerability.description or '',
                str(vulnerability.base_severity or ''),
                str(vulnerability.cvss_score or ''),
                str(getattr(vulnerability, 'published_date', '') or ''),
                str(getattr(vulnerability, 'last_update', '') or ''),
                ','.join(sorted([getattr(w,'cwe_id', str(w)) or '' for w in getattr(vulnerability,'weaknesses',[]) or []])),
                ','.join(sorted([getattr(p.product,'name', '') or '' for p in getattr(vulnerability,'products',[]) or []])),
            ]
            s = '\n'.join(parts)
            return hashlib.sha1(s.encode('utf-8')).hexdigest()
        except Exception:
            return ''

    def _parse_cached_risks(self, value: Optional[str]) -> Optional[Dict[str, Any]]:
        if not value:
            return None
        try:
            obj = json.loads(value)
            if isinstance(obj, dict) and 'content_markdown' in obj:
                return obj
        except Exception:
            pass
        return None

    def _should_refresh_cache(self, cached: Optional[Dict[str, Any]], vulnerability: Vulnerability) -> bool:
        if not cached:
            return True
        try:
            sig_now = self._compute_vuln_signature(vulnerability)
            sig_old = str(cached.get('vuln_signature') or '')
            if not sig_old:
                return True
            return sig_now != sig_old
        except Exception:
            return True
    
    def build_markdown_prompt(self, vulnerability: Vulnerability) -> str:
        """
        Constrói um prompt rico em Markdown usando a nova estrutura de dados.
        Inclui descrição, CVSS, CWE, vendors/produtos, ranges de versão, CPEs, referências e CISA KEV.
        """
        try:
            desc = vulnerability.description or ""
            severity = vulnerability.base_severity or "MEDIUM"
            cvss = float(vulnerability.cvss_score or 0.0)
            patch_avail = bool(getattr(vulnerability, 'patch_available', False))
            assigner = getattr(vulnerability, 'assigner', None) or ""
            published = None
            last_update = None
            try:
                if getattr(vulnerability, 'published_date', None):
                    published = vulnerability.published_date.isoformat()
                if getattr(vulnerability, 'last_update', None):
                    last_update = vulnerability.last_update.isoformat()
            except Exception:
                published = None
                last_update = None
            source_identifier = getattr(vulnerability, 'source_identifier', None) or ""
            vuln_status = getattr(vulnerability, 'vuln_status', None) or ""
            evaluator_comment = getattr(vulnerability, 'evaluator_comment', None) or ""
            evaluator_solution = getattr(vulnerability, 'evaluator_solution', None) or ""
            evaluator_impact = getattr(vulnerability, 'evaluator_impact', None) or ""

            # Weaknesses (CWE)
            cwe_list = []
            try:
                for w in getattr(vulnerability, 'weaknesses', []) or []:
                    tag = getattr(w, 'cwe_id', None) or getattr(w, 'name', None) or str(w)
                    if tag:
                        cwe_list.append(str(tag))
            except Exception:
                cwe_list = []

            # Vendors/Products (normalizados e fallback via JSON)
            vendors = []
            products = []
            try:
                for vp in getattr(vulnerability, 'products', []) or []:
                    try:
                        prod = getattr(vp, 'product', None)
                        if prod:
                            pname = getattr(prod, 'name', None)
                            vname = getattr(prod, 'vendor', None).name if getattr(prod, 'vendor', None) else None
                            if vname:
                                vendors.append(vname)
                            if pname:
                                products.append(pname)
                    except Exception:
                        continue
                # Fallback pelos campos NVD JSON
                if not vendors:
                    try:
                        vendors = [str(x) for x in (vulnerability.nvd_vendors_data or []) if str(x).strip()]
                    except Exception:
                        vendors = []
                if not products:
                    try:
                        products = [str(x) for x in (vulnerability.nvd_products_data or []) if str(x).strip()]
                    except Exception:
                        products = []
            except Exception:
                vendors, products = [], []

            # Version references e produtos afetados
            affected_versions = []
            fixed_versions = []
            try:
                for vr in getattr(vulnerability, 'version_references', []) or []:
                    try:
                        if getattr(vr, 'affected_version', None):
                            affected_versions.append(f"{getattr(vr, 'product', None).name if getattr(vr, 'product', None) else 'produto'}: {vr.affected_version}")
                        if getattr(vr, 'fixed_version', None):
                            fixed_versions.append(f"{getattr(vr, 'product', None).name if getattr(vr, 'product', None) else 'produto'}: {vr.fixed_version}")
                    except Exception:
                        continue
                for ap in getattr(vulnerability, 'affected_products', []) or []:
                    try:
                        pname = getattr(ap, 'product', None).name if getattr(ap, 'product', None) else None
                        avers = getattr(ap, 'affected_versions', None)
                        if pname or avers:
                            affected_versions.append(f"{pname or 'produto'}: {avers or 'versões não especificadas'}")
                    except Exception:
                        continue
            except Exception:
                pass

            # Version ranges e CPE configs
            version_ranges = []
            try:
                if vulnerability.nvd_version_ranges:
                    for vr in vulnerability.nvd_version_ranges:
                        try:
                            version_ranges.append(str(vr))
                        except Exception:
                            continue
            except Exception:
                version_ranges = []
            cpe_configs = []
            try:
                if vulnerability.nvd_cpe_configurations:
                    for cfg in vulnerability.nvd_cpe_configurations[:10]:
                        try:
                            cpe_configs.append(str(cfg))
                        except Exception:
                            continue
            except Exception:
                cpe_configs = []

            # Referências públicas
            references = []
            references_tags = []
            try:
                for ref in getattr(vulnerability, 'references', []) or []:
                    url = getattr(ref, 'url', None)
                    tags = getattr(ref, 'tags', None)
                    if tags:
                        try:
                            references_tags.append(str(tags))
                        except Exception:
                            pass
                    if url:
                        references.append(url)
            except Exception:
                references = []

            # CISA KEV
            cisa_info = []
            try:
                if vulnerability.cisa_exploit_add:
                    cisa_info.append(f"Adicionada ao CISA KEV em {vulnerability.cisa_exploit_add.isoformat()}")
                if vulnerability.cisa_action_due:
                    cisa_info.append(f"Ação requerida até {vulnerability.cisa_action_due.isoformat()}")
                if vulnerability.cisa_required_action:
                    cisa_info.append(f"Ação requerida: {vulnerability.cisa_required_action}")
            except Exception:
                cisa_info = []

            vendors_md = "\n".join(f"- {v}" for v in sorted(set(vendors))) or "- Não disponível"
            products_md = "\n".join(f"- {p}" for p in sorted(set(products))) or "- Não disponível"
            cwe_md = "\n".join(f"- {c}" for c in sorted(set(cwe_list))) or "- Não mapeado"
            versions_md = "\n".join(f"- {vr}" for vr in version_ranges[:10]) or "- Não especificado"
            cpe_md = "\n".join(f"- {cpe}" for cpe in cpe_configs[:10]) or "- Não especificado"
            refs_md = "\n".join(f"- {u}" for u in references[:10]) or "- Nenhuma referência pública"
            cisa_md = "\n".join(f"- {ci}" for ci in cisa_info) or "- Não consta em CISA KEV"
            patch_md = "Sim" if patch_avail else "Não"

            affected_versions_md = "\n".join(f"- {av}" for av in affected_versions[:10]) or "- Não especificado"
            fixed_versions_md = "\n".join(f"- {fv}" for fv in fixed_versions[:10]) or "- Não especificado"
            refs_tags_md = "\n".join(f"- {t}" for t in references_tags[:10]) or "- N/A"

            attack_vector = None
            attack_complexity = None
            privileges_required = None
            user_interaction = None
            scope = None
            try:
                metrics_list = getattr(vulnerability, 'metrics', []) or []
                primary = None
                for m in metrics_list:
                    try:
                        if getattr(m, 'is_primary', False):
                            primary = m
                            break
                    except Exception:
                        continue
                metric = primary or (metrics_list[0] if metrics_list else None)
                if metric:
                    attack_vector = getattr(metric, 'attack_vector', None) or getattr(metric, 'access_vector', None)
                    attack_complexity = getattr(metric, 'attack_complexity', None) or getattr(metric, 'access_complexity', None)
                    privileges_required = getattr(metric, 'privileges_required', None) or getattr(metric, 'authentication', None)
                    user_interaction = getattr(metric, 'user_interaction', None)
                    scope = getattr(metric, 'scope', None)
                    base_vector = getattr(metric, 'base_vector', None)
                    confidentiality_impact = getattr(metric, 'confidentiality_impact', None)
                    integrity_impact = getattr(metric, 'integrity_impact', None)
                    availability_impact = getattr(metric, 'availability_impact', None)
                    exploitability_score = getattr(metric, 'exploitability_score', None)
                    impact_score = getattr(metric, 'impact_score', None)
                    temporal_score = getattr(metric, 'temporal_score', None)
                    environmental_score = getattr(metric, 'environmental_score', None)
            except Exception:
                pass

            from app.services.vulnerability_service import VulnerabilityService
            from app.extensions import db
            affected_assets = None
            calculated_risk = None
            try:
                vs_local = VulnerabilityService(db.session)
                analytics = vs_local.get_vulnerability_analytics(vulnerability.cve_id) or {}
                affected_assets = analytics.get('affected_assets_count')
                calculated_risk = analytics.get('calculated_risk_score')
            except Exception:
                affected_assets = None
                calculated_risk = None

            return f"""Você é um analista sênior de risco cibernético.
Gere um **relatório técnico profissional em formato Markdown**, claro e acionável, para a vulnerabilidade abaixo.

Quando a informação não estiver disponível, indique: **Não aplicável**.

---

## Descrição Técnica
{desc}

## Classificação CVSS
- Severidade Base: **{severity}**
- Pontuação CVSS: **{cvss:.1f}**
- Patch oficial disponível: **{patch_md}**
### Detalhes CVSS
- Vetor base: **{base_vector or 'Não disponível'}**
- Confidencialidade: **{confidentiality_impact or 'Não disponível'}**
- Integridade: **{integrity_impact or 'Não disponível'}**
- Disponibilidade: **{availability_impact or 'Não disponível'}**
- Exploitabilidade (score): **{(exploitability_score if exploitability_score is not None else 'N/A')}**
- Impacto (score): **{(impact_score if impact_score is not None else 'N/A')}**
- Temporal (score): **{(temporal_score if temporal_score is not None else 'N/A')}**
- Ambiental (score): **{(environmental_score if environmental_score is not None else 'N/A')}**

## Metadados
- CVE ID: **{vulnerability.cve_id}**
- Publicado em: **{published or 'Não disponível'}**
- Última atualização: **{last_update or 'Não disponível'}**
- Assigner: **{assigner or 'Não disponível'}**
- Fonte/NVD: **{source_identifier or 'Não disponível'}**
- Status NVD: **{vuln_status or 'Não disponível'}**

## Avaliação do Avaliador
- Impacto: {evaluator_impact or 'Não disponível'}
- Solução: {evaluator_solution or 'Não disponível'}
- Comentário: {evaluator_comment or 'Não disponível'}

## CWE (Fraquezas)
{cwe_md}

## Vendors Afetados
{vendors_md}

## Produtos Afetados
{products_md}

## Faixas de Versão (se conhecidas)
{versions_md}

## Versões Afetadas e Corrigidas
- Afetadas:
{affected_versions_md}
- Corrigidas:
{fixed_versions_md}

## Configurações CPE (resumo)
{cpe_md}

## Referências Públicas
{refs_md}
**Tags**
{refs_tags_md}

## CISA KEV
{cisa_md}

## Contexto Operacional
- Ativos afetados: **{affected_assets if affected_assets is not None else 'N/A'}**
- Score de risco calculado: **{calculated_risk if calculated_risk is not None else 'N/A'}**

## 3. Vetor de Exploração e Requisitos
### 3.1 Método provável de exploração
- Descreva como um atacante poderia explorar a vulnerabilidade com base nos dados técnicos.

### 3.2 Pré-requisitos Técnicos e de Acesso
- Vetor de ataque: **{attack_vector or 'Não disponível'}**
- Complexidade do ataque: **{attack_complexity or 'Não disponível'}**
- Privilégios necessários: **{privileges_required or 'Não disponível'}**
- Interação do usuário: **{user_interaction or 'Não disponível'}**
- Escopo: **{scope or 'Não disponível'}**

## Exploits Conhecidos
- Exploit público / PoC, quando aplicável

## Impacto Potencial
**Impacto Técnico Direto**
- Confidencialidade, Integridade e Disponibilidade afetadas

**Impacto Organizacional e de Negócio**
- Interrupção de serviços, exposição de dados, compliance

## Mitigações e Correções
- Patches oficiais e hotfixes
- Medidas compensatórias
- Monitoramento recomendado

## Recomendação de Ação
- Ações imediatas e procedimentos internos

## Avaliação de Risco Interno
- Exposição técnica: Baixa/Média/Alta
- Risco: **Baixo/Médio/Alto** (com justificativa)

        **Importante:** Mantenha o conteúdo em formato Markdown, técnico e objetivo.
        """
        except Exception as e:
            logger.warning(f"Falha ao construir prompt estruturado: {e}")
            return (vulnerability.description or "")

    def _append_missing_sections(self, vulnerability: Vulnerability, content: str) -> str:
        try:
            text = str(content or "")
            need_prereqs = "## 3.2 Pré-requisitos Técnicos e de Acesso" not in text
            need_context = "## Contexto Operacional" not in text
            need_cvss_details = "### Detalhes CVSS" not in text

            extras = []
            if need_context:
                from app.services.vulnerability_service import VulnerabilityService
                from app.extensions import db
                affected_assets = None
                calculated_risk = None
                try:
                    vs_local = VulnerabilityService(db.session)
                    analytics = vs_local.get_vulnerability_analytics(vulnerability.cve_id) or {}
                    affected_assets = analytics.get('affected_assets_count')
                    calculated_risk = analytics.get('calculated_risk_score')
                except Exception:
                    pass
                extras.append("\n\n## Contexto Operacional\n- Ativos afetados: **{aa}**\n- Score de risco calculado: **{rs}**".format(
                    aa=(affected_assets if affected_assets is not None else 'N/A'),
                    rs=(calculated_risk if calculated_risk is not None else 'N/A')
                ))

            if need_prereqs or need_cvss_details:
                attack_vector = None
                attack_complexity = None
                privileges_required = None
                user_interaction = None
                scope = None
                base_vector = None
                confidentiality_impact = None
                integrity_impact = None
                availability_impact = None
                try:
                    metrics_list = getattr(vulnerability, 'metrics', []) or []
                    metric = None
                    for m in metrics_list:
                        try:
                            if getattr(m, 'is_primary', False):
                                metric = m
                                break
                        except Exception:
                            continue
                    metric = metric or (metrics_list[0] if metrics_list else None)
                    if metric:
                        attack_vector = getattr(metric, 'attack_vector', None) or getattr(metric, 'access_vector', None)
                        attack_complexity = getattr(metric, 'attack_complexity', None) or getattr(metric, 'access_complexity', None)
                        privileges_required = getattr(metric, 'privileges_required', None) or getattr(metric, 'authentication', None)
                        user_interaction = getattr(metric, 'user_interaction', None)
                        scope = getattr(metric, 'scope', None)
                        base_vector = getattr(metric, 'base_vector', None)
                        confidentiality_impact = getattr(metric, 'confidentiality_impact', None)
                        integrity_impact = getattr(metric, 'integrity_impact', None)
                        availability_impact = getattr(metric, 'availability_impact', None)
                except Exception:
                    pass

                if need_cvss_details:
                    extras.append("\n\n### Detalhes CVSS\n- Vetor base: **{bv}**\n- Confidencialidade: **{ci}**\n- Integridade: **{ii}**\n- Disponibilidade: **{ai}**".format(
                        bv=(base_vector or 'Não disponível'),
                        ci=(confidentiality_impact or 'Não disponível'),
                        ii=(integrity_impact or 'Não disponível'),
                        ai=(availability_impact or 'Não disponível')
                    ))

                if need_prereqs:
                    extras.append("\n\n### 3.2 Pré-requisitos Técnicos e de Acesso\n- Vetor de ataque: **{av}**\n- Complexidade do ataque: **{ac}**\n- Privilégios necessários: **{pr}**\n- Interação do usuário: **{ui}**\n- Escopo: **{sc}**".format(
                        av=(attack_vector or 'Não disponível'),
                        ac=(attack_complexity or 'Não disponível'),
                        pr=(privileges_required or 'Não disponível'),
                        ui=(user_interaction or 'Não disponível'),
                        sc=(scope or 'Não disponível')
                    ))

            if extras:
                return text + "".join(extras)
            return text
        except Exception:
            return str(content or "")

    def _extract_text_from_response(self, response: Any) -> str:
        try:
            # OpenAI Responses API convenience
            if hasattr(response, 'output_text') and response.output_text:
                return str(response.output_text)
            # Fallback to chat completions
            if hasattr(response, 'choices'):
                try:
                    return str(response.choices[0].message.content)
                except Exception:
                    pass
            # Generic fallback
            return str(response)
        except Exception:
            return ""
    
    def sanitize_markdown_output(self, text: str) -> str:
        """
        Remove blocos de código Markdown (```markdown ... ```) do texto, para evitar exibição literal.
        
        Args:
            text: Texto a ser sanitizado
            
        Returns:
            Texto sanitizado
        """
        return re.sub(r"```(?:markdown)?\s*([\s\S]*?)\s*```", r"\1", text)
    
    def get_risk_analysis(self, cve_id: str) -> str:
        """
        Retorna a análise de risco para a CVE fornecida.
        Caso não exista no banco, retorna um aviso.
        Se a análise ainda não foi gerada, consulta a OpenAI.
        
        Args:
            cve_id: ID da CVE para análise
            
        Returns:
            Análise de risco em formato Markdown
        """
        # Inicializa o cliente dentro do contexto da aplicação
        self._initialize_client()

        try:
            # Buscar vulnerabilidade com detalhes usando o serviço dedicado
            from app.services.vulnerability_service import VulnerabilityService
            vs = VulnerabilityService(db.session)
            vulnerability = vs.get_vulnerability_with_details(cve_id)
            if not vulnerability:
                logger.warning(f"CVE {cve_id} não encontrada no banco de dados")
                return "CVE id não encontrada."

            description = vulnerability.description or ""
            base_severity = vulnerability.base_severity or "MEDIUM"
            cvss_score = float(vulnerability.cvss_score or 0.0)

            # Verificar se a coluna 'risks' existe na tabela
            has_risks_col = False
            try:
                inspector = inspect(db.engine)
                column_names = [col['name'] for col in inspector.get_columns('vulnerabilities')]
                has_risks_col = 'risks' in column_names
            except Exception as e:
                logger.debug(f"Não foi possível inspecionar colunas: {e}")
                has_risks_col = False

            # Se não existir, tentar adicionar coluna 'risks' (compatível com SQLite/PostgreSQL)
            if not has_risks_col:
                try:
                    db.session.execute(text("ALTER TABLE vulnerabilities ADD COLUMN risks TEXT"))
                    db.session.commit()
                    logger.info("Coluna 'risks' adicionada à tabela vulnerabilities")
                    has_risks_col = True
                except Exception as e:
                    logger.warning(f"Não foi possível adicionar coluna 'risks': {e}")
                    has_risks_col = False

            # Buscar análise existente se coluna 'risks' estiver disponível
            existing_risks = None
            if has_risks_col:
                try:
                    row = db.session.execute(
                        text("SELECT risks FROM vulnerabilities WHERE cve_id = :cve"),
                        {"cve": cve_id}
                    ).fetchone()
                    if row:
                        existing_risks = row[0]
                        try:
                            demo_markers = [
                                'análise de demonstração',
                                'Nenhuma informação conhecida',
                                'Relatório de Análise de Risco -',
                            ]
                            low = (existing_risks or '').lower()
                            if any(m.lower() in low for m in demo_markers):
                                existing_risks = None
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Falha ao consultar coluna 'risks': {e}")

            cached_obj = self._parse_cached_risks(existing_risks)
            # Se não houver análise ou a assinatura mudou, gerar nova
            if (not existing_risks or not str(existing_risks).strip()) or self._should_refresh_cache(cached_obj, vulnerability):
                logger.info(f"Gerando nova análise de risco para CVE {cve_id}")
                prompt = self.build_markdown_prompt(vulnerability)
                
                if self.client:
                    try:
                        sys_msg = self.system_prompt or "Você é um analista de risco especializado em vulnerabilidades."
                        response = self._chat_completion_with_retries([
                            {"role": "system", "content": sys_msg},
                            {"role": "user", "content": prompt}
                        ])
                        resp_text = self._extract_text_from_response(response)
                        risks_md = self.sanitize_markdown_output(resp_text.strip())
                        try:
                            low = (risks_md or "").lower()
                            if not low.startswith("você é um analista sênior de risco cibernético"):
                                risks_md = self._append_missing_sections(vulnerability, risks_md)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.error(f"Erro ao consultar OpenAI: {e}")
                        # Fallback: exibir o prompt gerado em vez de mock de demonstração
                        risks_md = prompt
                else:
                    # Sem cliente LLM: exibir o prompt gerado
                    risks_md = prompt

                # Persistir análise se coluna existir
                if has_risks_col:
                    try:
                        envelope = json.dumps({
                            "content_markdown": risks_md,
                            "provider": self.provider,
                            "model": self.model,
                            "max_tokens": self.max_tokens,
                            "temperature": self.temperature,
                            "generated_at": __import__('datetime').datetime.now().isoformat(),
                            "vuln_signature": self._compute_vuln_signature(vulnerability),
                        }, ensure_ascii=False)
                        db.session.execute(
                            text("UPDATE vulnerabilities SET risks = :risks WHERE cve_id = :cve"),
                            {"risks": envelope, "cve": cve_id}
                        )
                        db.session.commit()
                        logger.info(f"Análise de risco salva para CVE {cve_id}")
                    except Exception as e:
                        logger.warning(f"Falha ao salvar análise de risco: {e}")

                return risks_md

            # Retornar análise existente
            if cached_obj:
                return str(cached_obj.get('content_markdown') or '')
            return existing_risks

        except Exception as e:
            logger.error(f"Erro ao acessar banco de dados ou gerar análise: {e}")
            return f"Erro ao acessar banco de dados: {e}"
    
    def _generate_demo_risk_analysis(self, cve_id: str, description: str, base_severity: str, cvss_score: float) -> str:
        """
        Deprecated: substituído por exibição do prompt quando LLM indisponível.
        Mantido apenas por compatibilidade de importação.
        """
        return f"# Prompt de Análise de Risco para {cve_id}\n\n{description}"
    
    def generate_risk_report_html(self, cve_id: str) -> str:
        """
        Gera um relatório de risco em formato HTML para exibição na web.
        
        Args:
            cve_id: ID da CVE para análise
            
        Returns:
            Relatório de risco em formato HTML
        """
        try:
            # Inicializa o cliente dentro do contexto da aplicação
            self._initialize_client()
            
            import markdown
            
            # Gera a análise em Markdown
            markdown_content = self.get_risk_analysis(cve_id)
            
            # Converte para HTML
            html_content = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
            
            return html_content
            
        except ImportError:
            logger.warning("Biblioteca markdown não encontrada, retornando conteúdo em texto")
            return f"<pre>{self.get_risk_analysis(cve_id)}</pre>"
        except Exception as e:
            logger.error(f"Erro ao gerar HTML: {e}")
            return f"<p>Erro ao gerar relatório: {e}</p>"

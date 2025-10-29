# services/report_ai_service.py

"""
Service para geração de conteúdo inteligente para relatórios usando OpenAI.
Responsável por gerar resumos executivos, análises de impacto de negócio (BIA) e planos de remediação.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from flask import current_app
from openai import OpenAI

logger = logging.getLogger(__name__)


class ReportAIService:
    """Service para geração de conteúdo inteligente para relatórios."""
    
    def __init__(self):
        self.client = None
        self.api_key = None
        self.model = None
        self.max_tokens = None
        self.temperature = None
        self.demo_mode = False
        self._initialized = False
    
    def _initialize_openai(self):
        """Inicializa o cliente OpenAI dentro do contexto da aplicação."""
        if self._initialized:
            return
            
        try:
            self.api_key = current_app.config.get('OPENAI_API_KEY')
            self.model = current_app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')
            self.max_tokens = current_app.config.get('OPENAI_MAX_TOKENS', 2000)
            self.temperature = current_app.config.get('OPENAI_TEMPERATURE', 0.3)
            
            if not self.api_key:
                logger.warning("OPENAI_API_KEY não configurada - modo demo ativo")
                self.demo_mode = True
                self._initialized = True
                return
                
            self.client = OpenAI(api_key=self.api_key)
            logger.info("Cliente OpenAI inicializado com sucesso para relatórios")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente OpenAI: {e}")
            self.demo_mode = True
            self._initialized = True
    
    def generate_executive_summary(self, 
                                 report_data: Dict[str, Any],
                                 report_type: str,
                                 organization_context: Optional[str] = None) -> str:
        """
        Gera um resumo executivo baseado nos dados do relatório.
        
        Args:
            report_data: Dados compilados do relatório
            report_type: Tipo do relatório (executive, technical, etc.)
            organization_context: Contexto organizacional opcional
            
        Returns:
            Resumo executivo em formato markdown
        """
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_executive_summary(report_data, report_type)
            
            # Preparar dados para o prompt
            asset_count = report_data.get('assets', {}).get('total_assets', 0)
            vuln_count = report_data.get('vulnerabilities', {}).get('total_vulnerabilities', 0)
            vuln_by_severity = report_data.get('vulnerabilities', {}).get('by_severity', {})
            risk_stats = report_data.get('risks', {}).get('risk_statistics', {})
            
            # Dados enriquecidos
            cisa_kev_data = report_data.get('vulnerabilities', {}).get('cisa_kev_data', {})
            epss_stats = report_data.get('vulnerabilities', {}).get('epss_stats', {})
            vendor_product_data = report_data.get('vulnerabilities', {}).get('vendor_product_data', {})
            
            # Construir prompt
            prompt = self._build_executive_summary_prompt(
                asset_count, vuln_count, vuln_by_severity, risk_stats, 
                report_type, organization_context, cisa_kev_data, epss_stats, vendor_product_data
            )
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_executive_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo executivo: {e}")
            return self._generate_demo_executive_summary(report_data, report_type)
    
    def generate_business_impact_analysis(self,
                                        report_data: Dict[str, Any],
                                        asset_attributes: List[Dict[str, Any]],
                                        cve_mappings: List[Dict[str, Any]]) -> str:
        """
        Gera análise de impacto de negócio (BIA) usando atributos de ativos e mapeamento CVE.
        
        Args:
            report_data: Dados compilados do relatório
            asset_attributes: Lista de atributos dos ativos
            cve_mappings: Mapeamentos CVE para análise
            
        Returns:
            Análise BIA em formato markdown
        """
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_bia(report_data, asset_attributes)
            
            # Preparar dados para análise
            critical_assets = [asset for asset in asset_attributes if asset.get('criticality') == 'HIGH']
            high_severity_vulns = report_data.get('vulnerabilities', {}).get('vulnerabilities_by_severity', {}).get('HIGH', 0)
            critical_vulns = report_data.get('vulnerabilities', {}).get('vulnerabilities_by_severity', {}).get('CRITICAL', 0)
            
            # Construir prompt
            prompt = self._build_bia_prompt(
                critical_assets, high_severity_vulns, critical_vulns, 
                asset_attributes, cve_mappings, cisa_kev_data=cisa_kev_data, epss_stats=epss_stats, vendor_product_data=vendor_product_data)
            
            # Dados enriquecidos para BIA
            threat_intelligence_info = ""
            if cisa_kev_data or epss_stats:
                threat_intelligence_info = f"""
**DADOS DE THREAT INTELLIGENCE:**
"""
                if cisa_kev_data:
                    kev_count = cisa_kev_data.get('total_kev_vulnerabilities', 0)
                    threat_intelligence_info += f"""
- Vulnerabilidades CISA KEV: {kev_count} (exploração ativa confirmada)
- Prioridade máxima para remediação devido ao risco de exploração imediata
"""
                    
                    if epss_stats:
                        high_epss = epss_stats.get('high_probability_count', 0)
                        avg_epss = epss_stats.get('average_score', 0)
                        threat_intelligence_info += f"""
- Vulnerabilidades com alta probabilidade de exploração (EPSS): {high_epss}
- Score médio EPSS: {avg_epss:.3f} (predição de exploração em 30 dias)
"""
                
                vendor_risk_info = ""
                if vendor_product_data:
                    top_vendors = vendor_product_data.get('top_affected_vendors', [])[:5]
                    vendor_risk_info = f"""
**ANÁLISE DE RISCO POR VENDOR:**
- Principais vendors afetados: {', '.join([f"{v['vendor']} ({v['count']})" for v in top_vendors])}
- Concentração de risco por fornecedor pode amplificar impacto de negócio
- Necessidade de avaliação de fornecedores alternativos
"""
                
                return f"""Realize uma Business Impact Analysis (BIA) baseada nos seguintes dados:

**Ativos Críticos Identificados:**
{len(critical_assets)} ativos classificados como críticos

**Vulnerabilidades de Alto Impacto:**
- Críticas: {critical_vulns}
- Altas: {high_severity_vulns}

{threat_intelligence_info}
{vendor_risk_info}

**Atributos dos Ativos:**
{self._format_asset_attributes(asset_attributes[:10])}  # Limitar para não sobrecarregar

**ANÁLISE BIA REQUERIDA:**

1. **Impacto Financeiro Potencial**
   - Perda de receita por hora/dia de interrupção
   - Custos de recuperação e resposta a incidentes
   - Multas regulatórias e penalidades
   - Considere dados CISA KEV e EPSS para priorização de risco

2. **Impacto Operacional nos Processos**
   - Interrupção de processos críticos de negócio
   - Degradação de serviços e SLAs
   - Impacto na produtividade e operações
   - Efeito cascata em sistemas dependentes

3. **Riscos Reputacionais**
   - Danos à marca e confiança do cliente
   - Impacto no valor de mercado
   - Relacionamento com stakeholders
   - Exposição midiática negativa

4. **Tempo de Recuperação Estimado (RTO/RPO)**
   - Recovery Time Objective por categoria de ativo
   - Recovery Point Objective para dados críticos
   - Mean Time To Recovery (MTTR)
   - Janelas de manutenção disponíveis

5. **Interdependências Críticas**
   - Mapeamento de dependências entre sistemas
   - Fornecedores e parceiros críticos
   - Infraestrutura compartilhada
   - Pontos únicos de falha

6. **Classificação de Prioridade para Remediação**
   - Matriz de risco (probabilidade x impacto)
   - Priorização baseada em criticidade de negócio
   - Consideração de dados CISA KEV (prioridade máxima)
   - Integração de scores EPSS para probabilidade de exploração

**CONSIDERAÇÕES ESPECIAIS:**
- Vulnerabilidades CISA KEV devem ser tratadas como CRÍTICAS para BIA
- Scores EPSS altos indicam maior probabilidade de materialização do risco
- Concentração de vulnerabilidades por vendor pode amplificar impacto
- Considere cenários de exploração simultânea de múltiplas vulnerabilidades

Forneça uma análise BIA estruturada em markdown com foco em impactos quantificáveis de negócio."""
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_bia_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise BIA: {e}")
            return self._generate_demo_bia(report_data, asset_attributes)
    
    def generate_remediation_plan(self,
                                report_data: Dict[str, Any],
                                priority_vulnerabilities: List[Dict[str, Any]],
                                available_resources: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera plano de remediação baseado nas vulnerabilidades prioritárias.
        
        Args:
            report_data: Dados compilados do relatório
            priority_vulnerabilities: Lista de vulnerabilidades prioritárias
            available_resources: Recursos disponíveis para remediação
            
        Returns:
            Plano de remediação em formato markdown
        """
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_remediation_plan(priority_vulnerabilities)
            
            # Preparar dados para o plano
            total_vulns = len(priority_vulnerabilities)
            critical_count = len([v for v in priority_vulnerabilities if v.get('severity') == 'CRITICAL'])
            high_count = len([v for v in priority_vulnerabilities if v.get('severity') == 'HIGH'])
            
            # Construir prompt
            prompt = self._build_remediation_prompt(
                priority_vulnerabilities, total_vulns, critical_count, 
                high_count, available_resources
            )
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_remediation_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar plano de remediação: {e}")
            return self._generate_demo_remediation_plan(priority_vulnerabilities)
    
    def generate_technical_study(self,
                               report_data: Dict[str, Any],
                               asset_configurations: List[Dict[str, Any]],
                               security_architecture: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera análise técnica aprofundada para Estudo Técnico.
        
        Args:
            report_data: Dados compilados do relatório
            asset_configurations: Configurações detalhadas dos ativos
            security_architecture: Informações sobre arquitetura de segurança
            
        Returns:
            Análise técnica em formato markdown
        """
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_technical_study(report_data, asset_configurations)
            
            # Preparar dados para análise
            asset_count = len(asset_configurations)
            vuln_data = report_data.get('vulnerabilities', {})
            technical_details = report_data.get('technical_analysis', {})
            
            # Construir prompt
            prompt = self._build_technical_study_prompt(
                asset_configurations, vuln_data, technical_details, security_architecture
            )
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_technical_study_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar estudo técnico: {e}")
            return self._generate_demo_technical_study(report_data, asset_configurations)
    
    def generate_cisa_kev_analysis(self,
                                 cisa_kev_data: Dict[str, Any],
                                 vulnerability_data: Dict[str, Any]) -> str:
        """Gera análise específica de vulnerabilidades CISA KEV."""
        try:
            if not self.openai_client:
                return self._generate_demo_cisa_kev_analysis(cisa_kev_data, vulnerability_data)
            
            # Construir prompt específico para CISA KEV
            prompt = self._build_cisa_kev_prompt(cisa_kev_data, vulnerability_data)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self._get_cisa_kev_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise CISA KEV: {str(e)}")
            return self._generate_demo_cisa_kev_analysis(cisa_kev_data, vulnerability_data)

    def generate_epss_analysis(self,
                              epss_data: Dict[str, Any],
                              vulnerability_data: Dict[str, Any]) -> str:
        """Gera análise específica de dados EPSS."""
        try:
            if not self.openai_client:
                return self._generate_demo_epss_analysis(epss_data, vulnerability_data)
            
            # Construir prompt específico para EPSS
            prompt = self._build_epss_prompt(epss_data, vulnerability_data)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self._get_epss_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise EPSS: {str(e)}")
            return self._generate_demo_epss_analysis(epss_data, vulnerability_data)

    def generate_vendor_product_analysis(self,
                                       vendor_product_data: Dict[str, Any],
                                       vulnerability_data: Dict[str, Any]) -> str:
        """Gera análise específica de vendors e produtos."""
        try:
            if not self.openai_client:
                return self._generate_demo_vendor_product_analysis(vendor_product_data, vulnerability_data)
            
            # Construir prompt específico para vendor/product
            prompt = self._build_vendor_product_prompt(vendor_product_data, vulnerability_data)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self._get_vendor_product_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise vendor/product: {str(e)}")
            return self._generate_demo_vendor_product_analysis(vendor_product_data, vulnerability_data)

    def generate_technical_analysis(self,
                                  vulnerability_data: Dict[str, Any],
                                  cve_details: List[Dict[str, Any]]) -> str:
        """
        Gera análise técnica detalhada das vulnerabilidades.
        
        Args:
            vulnerability_data: Dados de vulnerabilidades
            cve_details: Detalhes específicos das CVEs
            
        Returns:
            Análise técnica em formato markdown
        """
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_technical_analysis(vulnerability_data)
            
            # Preparar dados técnicos
            cvss_stats = vulnerability_data.get('cvss_statistics', {})
            cwe_distribution = vulnerability_data.get('cwe_distribution', {})
            
            # Construir prompt
            prompt = self._build_technical_analysis_prompt(
                vulnerability_data, cve_details, cvss_stats, cwe_distribution
            )
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_technical_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise técnica: {e}")
            return self._generate_demo_technical_analysis(vulnerability_data)
    
    # Métodos para construção de prompts
    
    def _get_executive_system_prompt(self) -> str:
        """Retorna o prompt do sistema para resumos executivos."""
        return """Você é um CISO (Chief Information Security Officer) experiente com mais de 15 anos 
        de experiência em cybersegurança corporativa. Sua especialidade é traduzir riscos técnicos 
        complexos em insights estratégicos para liderança executiva e conselhos de administração.
        
        DIRETRIZES OBRIGATÓRIAS:
        
        **Linguagem e Tom:**
        - Use linguagem executiva clara, evitando jargões técnicos desnecessários
        - Mantenha tom assertivo, mas não alarmista
        - Foque em impactos de negócio quantificáveis sempre que possível
        - Use analogias de negócio quando apropriado
        
        **Estrutura Obrigatória:**
        1. **Situação Atual** (2-3 frases): Estado geral da postura de segurança
        2. **Riscos Críticos** (bullet points): Top 3-5 riscos com impacto de negócio
        3. **Impacto Financeiro** (quando aplicável): Estimativas de exposição/custo
        4. **Ações Imediatas** (numeradas): 3-5 ações prioritárias com prazos
        5. **Investimentos Recomendados** (opcional): Recursos necessários
        
        **Métricas Essenciais:**
        - Percentual de redução de risco esperado
        - Tempo estimado para implementação
        - ROI de segurança quando relevante
        - Comparação com benchmarks da indústria
        
        **Formato:** Markdown com seções claras, máximo 400 palavras, foco em decisões executivas."""
    
    def _get_bia_system_prompt(self) -> str:
        """Retorna o prompt do sistema para análise BIA."""
        return """Você é um analista sênior de continuidade de negócios certificado (CBCP/MBCI) 
        com especialização em Business Impact Analysis (BIA) para riscos de cybersegurança. 
        Sua experiência inclui análises para organizações Fortune 500 e frameworks regulatórios.
        
        METODOLOGIA OBRIGATÓRIA:
        
        **Framework de Análise:**
        - Use metodologia NIST SP 800-34 para BIA
        - Aplique matriz de risco ISO 27005
        - Considere frameworks setoriais relevantes (SOX, HIPAA, PCI-DSS)
        
        **Categorias de Impacto (Analise TODAS):**
        1. **Financeiro Direto:** Perda de receita, multas, custos de recuperação
        2. **Operacional:** Interrupção de processos, produtividade, SLA
        3. **Reputacional:** Danos à marca, confiança do cliente, valor de mercado
        4. **Regulatório:** Não conformidade, sanções, licenças
        5. **Estratégico:** Vantagem competitiva, oportunidades perdidas
        
        **Métricas Obrigatórias:**
        - **RTO (Recovery Time Objective):** Tempo máximo aceitável de interrupção
        - **RPO (Recovery Point Objective):** Perda máxima aceitável de dados
        - **MTTR (Mean Time To Recovery):** Tempo médio de recuperação
        - **Impacto Financeiro:** Valores em USD por hora/dia de interrupção
        
        **Estrutura de Saída:**
        1. **Resumo Executivo** (3-4 linhas)
        2. **Análise de Impacto por Categoria** (detalhada)
        3. **Interdependências Críticas** (mapeamento)
        4. **Cenários de Risco** (melhor/pior caso)
        5. **Recomendações de Mitigação** (priorizadas)
        6. **Métricas de Recuperação** (RTO/RPO/MTTR)
        
        **Formato:** Markdown estruturado, máximo 600 palavras, foco em impactos quantificáveis."""
    
    def _get_remediation_system_prompt(self) -> str:
        """Retorna o prompt do sistema para planos de remediação."""
        return """Você é um especialista sênior em gestão de vulnerabilidades e resposta a incidentes 
        certificado (CISSP, GCIH, GCFA) com mais de 10 anos de experiência em implementação de 
        programas de remediação em ambientes corporativos complexos.
        
        METODOLOGIA OBRIGATÓRIA:
        
        **Framework de Priorização:**
        - Use matriz CVSS + Exploitabilidade + Impacto de Negócio
        - Aplique metodologia NIST SP 800-40 para patch management
        - Considere OWASP Risk Rating Methodology
        - Integre threat intelligence e contexto de ameaças ativas
        
        **Categorização de Ações:**
        1. **CRÍTICAS (0-24h):** Vulnerabilidades com exploits ativos
        2. **ALTAS (1-7 dias):** Alto risco com impacto significativo
        3. **MÉDIAS (8-30 dias):** Risco moderado, implementação planejada
        4. **BAIXAS (31-90 dias):** Baixo risco, manutenção preventiva
        
        **Tipos de Remediação (Especifique SEMPRE):**
        - **Patch/Update:** Aplicação de correções oficiais
        - **Configuração:** Mudanças em configurações de segurança
        - **Mitigação:** Controles compensatórios temporários
        - **Isolamento:** Segregação de sistemas vulneráveis
        - **Substituição:** Troca de componentes/sistemas
        
        **Estrutura Obrigatória:**
        1. **Resumo Executivo** (2-3 linhas)
        2. **Cronograma de Implementação** (tabela com prazos)
        3. **Ações por Prioridade** (detalhadas com responsáveis)
        4. **Medidas Temporárias** (controles imediatos)
        5. **Recursos Necessários** (pessoas, ferramentas, orçamento)
        6. **Critérios de Validação** (testes e verificações)
        7. **Plano de Rollback** (procedimentos de reversão)
        8. **Marcos e Métricas** (KPIs de progresso)
        
        **Formato:** Markdown com tabelas, máximo 700 palavras, foco em execução prática."""
    
    def _get_technical_system_prompt(self) -> str:
        """Retorna o prompt do sistema para análises técnicas."""
        return """Você é um pesquisador sênior de segurança e analista de vulnerabilidades certificado 
        (OSCP, GPEN, CEH) com especialização em análise de exploits, engenharia reversa e threat hunting. 
        Sua experiência inclui descoberta de 0-days e análise forense digital.
        
        METODOLOGIA TÉCNICA OBRIGATÓRIA:
        
        **Framework de Análise:**
        - Use MITRE ATT&CK para mapeamento de TTPs
        - Aplique OWASP Testing Guide para web applications
        - Considere NIST SP 800-115 para technical testing
        - Integre CVSS 3.1 com contexto de exploitabilidade
        
        **Análise de Vulnerabilidades (OBRIGATÓRIO):**
        1. **Vetor de Ataque:** Como a vulnerabilidade é explorada
        2. **Complexidade:** Dificuldade técnica de exploração
        3. **Pré-requisitos:** Condições necessárias para exploração
        4. **Impacto Técnico:** CIA (Confidencialidade, Integridade, Disponibilidade)
        5. **Proof of Concept:** Evidências ou exemplos de exploração
        6. **Detecção:** Métodos para identificar tentativas de exploração
        
        **Categorização por CWE:**
        - Mapeie vulnerabilidades para CWE Top 25
        - Explique a classe de fraqueza e suas variações
        - Forneça contexto sobre prevalência e tendências
        
        **Análise de Exploitabilidade:**
        - **Exploits Públicos:** Disponibilidade de PoCs/exploits
        - **Facilidade de Exploração:** Skill level necessário
        - **Reliability:** Consistência do exploit
        - **Detectabilidade:** Facilidade de detecção pelo SOC
        
        **Estrutura Técnica Obrigatória:**
        1. **Resumo Técnico** (2-3 linhas)
        2. **Análise de Vetores de Ataque** (detalhada por categoria)
        3. **Mapeamento MITRE ATT&CK** (táticas e técnicas)
        4. **Análise de Exploitabilidade** (com evidências)
        5. **Indicadores Técnicos** (IoCs, assinaturas)
        6. **Contramedidas Técnicas** (controles específicos)
        7. **Referências Técnicas** (CVEs, advisories, papers)
        
        **Formato:** Markdown técnico com código, máximo 800 palavras, precisão absoluta."""
    
    def _get_technical_study_system_prompt(self) -> str:
        """Retorna o prompt do sistema para estudos técnicos."""
        return """Você é um arquiteto de segurança sênior especializado em análises técnicas aprofundadas.
        Sua tarefa é criar estudos técnicos abrangentes que combinem análise de vulnerabilidades,
        arquitetura de segurança e recomendações técnicas específicas.
        
        Diretrizes:
        - Realize análise técnica aprofundada de configurações e arquitetura
        - Avalie configurações de segurança em detalhes
        - Analise a arquitetura de segurança existente
        - Forneça recomendações técnicas específicas e implementáveis
        - Inclua procedimentos detalhados de implementação
        - Considere impactos técnicos e operacionais
        - Use diagramas e exemplos de código quando apropriado
        - Mantenha foco em aspectos técnicos profundos
        - Estruture em seções claras usando markdown
        - Inclua referências técnicas e melhores práticas"""

    def _get_cisa_kev_system_prompt(self) -> str:
        """Retorna prompt do sistema para análise CISA KEV."""
        return """Você é um especialista em threat intelligence e análise de vulnerabilidades CISA KEV.
        
Sua tarefa é analisar vulnerabilidades que estão no CISA Known Exploited Vulnerabilities (KEV) catalog,
focando no risco de exploração ativa e priorização de remediação.

Foque em:
- Análise de vulnerabilidades com exploração ativa confirmada
- Priorização baseada em threat intelligence
- Impacto de ataques em andamento
- Recomendações urgentes de mitigação
- Contexto de ameaças atuais

Use linguagem clara e enfatize a urgência das vulnerabilidades KEV."""

    def _get_epss_system_prompt(self) -> str:
        """Retorna prompt do sistema para análise EPSS."""
        return """Você é um especialista em análise de probabilidade de exploração usando dados EPSS.
        
Sua tarefa é analisar a probabilidade de exploração de vulnerabilidades baseada em dados
do Exploit Prediction Scoring System (EPSS).

Foque em:
- Interpretação de scores EPSS e probabilidades
- Correlação entre EPSS e risco real
- Priorização baseada em likelihood de exploração
- Tendências de exploração ao longo do tempo
- Recomendações de priorização inteligente

Use dados quantitativos e forneça insights acionáveis sobre priorização."""

    def _get_vendor_product_system_prompt(self) -> str:
        """Retorna prompt do sistema para análise vendor/product."""
        return """Você é um especialista em análise de vulnerabilidades por vendor e produto.
        
Sua tarefa é analisar a distribuição de vulnerabilidades por fabricantes e produtos,
identificando padrões e riscos específicos.

Foque em:
- Análise de vendors com maior exposição
- Produtos mais vulneráveis no ambiente
- Padrões de vulnerabilidades por fabricante
- Recomendações de diversificação de vendors
- Estratégias de patch management por produto

Use análise estatística e forneça insights estratégicos sobre gestão de vendors."""
    
    def _build_executive_summary_prompt(self, asset_count, vuln_count, vuln_by_severity, 
                                      risk_stats, report_type, organization_context, 
                                      cisa_kev_data=None, epss_stats=None, vendor_product_data=None):
        """Constrói prompt para resumo executivo."""
        context = f"**Contexto Organizacional:** {organization_context}" if organization_context else ""
        
        # Calcular métricas de risco
        critical_ratio = (vuln_by_severity.get('Critical', 0) / vuln_count * 100) if vuln_count > 0 else 0
        high_ratio = (vuln_by_severity.get('High', 0) / vuln_count * 100) if vuln_count > 0 else 0
        
        # Dados enriquecidos
        cisa_kev_info = ""
        if cisa_kev_data:
            kev_count = cisa_kev_data.get('total_kev_vulnerabilities', 0)
            kev_percentage = (kev_count / vuln_count * 100) if vuln_count > 0 else 0
            cisa_kev_info = f"""
**DADOS CISA KEV (Known Exploited Vulnerabilities):**
- Vulnerabilidades CISA KEV: {kev_count} ({kev_percentage:.1f}% do total)
- Status de exploração ativa confirmada pelo governo americano
- Prioridade máxima para remediação imediata
"""
        
        epss_info = ""
        if epss_stats:
            high_epss = epss_stats.get('high_probability_count', 0)
            avg_epss = epss_stats.get('average_score', 0)
            epss_info = f"""
**DADOS EPSS (Exploit Prediction Scoring System):**
- Vulnerabilidades com alta probabilidade de exploração: {high_epss}
- Score médio EPSS: {avg_epss:.3f}
- Predição baseada em machine learning de exploração em 30 dias
"""
        
        vendor_product_info = ""
        if vendor_product_data:
            top_vendors = vendor_product_data.get('top_affected_vendors', [])[:5]
            vendor_info = ", ".join([f"{v['vendor']} ({v['count']})" for v in top_vendors])
            vendor_product_info = f"""
**ANÁLISE DE VENDORS/PRODUTOS:**
- Principais vendors afetados: {vendor_info}
- Concentração de risco por fornecedor identificada
- Necessidade de diversificação de fornecedores avaliada
"""
        
        return f"""MISSÃO EXECUTIVA: Crie um resumo executivo que permita ao CEO/Board tomar decisões 
        informadas sobre investimentos em cybersegurança e priorização de recursos.

**DADOS DA AVALIAÇÃO DE SEGURANÇA:**

**Escopo e Cobertura:**
- Tipo de Avaliação: {report_type.replace('_', ' ').title()}
- Ativos Analisados: {asset_count:,} sistemas/aplicações
- Vulnerabilidades Identificadas: {vuln_count:,} issues
- Período de Análise: Últimos 30 dias

**PERFIL DE RISCO ATUAL:**
{self._format_severity_distribution(vuln_by_severity)}

**MÉTRICAS CRÍTICAS:**
- Exposição Crítica: {critical_ratio:.1f}% das vulnerabilidades
- Risco Alto/Crítico: {critical_ratio + high_ratio:.1f}% do total
{self._format_risk_stats(risk_stats)}

{cisa_kev_info}
{epss_info}
{vendor_product_info}

{context}

**DELIVERABLES OBRIGATÓRIOS:**

1. **SITUAÇÃO ATUAL** (2-3 frases):
   - Estado geral da postura de segurança
   - Comparação com benchmarks da indústria
   - Tendência (melhorando/piorando/estável)

2. **RISCOS CRÍTICOS** (Top 3-5 bullet points):
   - Impacto de negócio específico para cada risco
   - Probabilidade de exploração (considere dados EPSS e CISA KEV)
   - Exposição financeira estimada

3. **IMPACTO FINANCEIRO** (quando aplicável):
   - Custo estimado de um incidente
   - ROI de investimentos em segurança
   - Comparação custo/benefício

4. **AÇÕES IMEDIATAS** (3-5 ações numeradas):
   - Prazo específico para cada ação
   - Responsável sugerido
   - Investimento necessário
   - Priorize vulnerabilidades CISA KEV e alto EPSS

5. **RECOMENDAÇÃO ESTRATÉGICA** (1-2 frases):
   - Direção estratégica recomendada
   - Próximos marcos importantes

**RESTRIÇÕES:**
- Máximo 400 palavras
- Linguagem executiva (não técnica)
- Foco em decisões e investimentos
- Tom assertivo mas não alarmista
- Considere dados de threat intelligence (CISA KEV, EPSS) para priorização"""
    
    def _build_bia_prompt(self, critical_assets, high_severity_vulns, critical_vulns, 
                         asset_attributes, cve_mappings, cisa_kev_data=None, epss_stats=None, vendor_product_data=None):
        """Constrói prompt para análise BIA."""
        
        # Dados enriquecidos para BIA
        threat_intelligence_info = ""
        if cisa_kev_data or epss_stats:
            threat_intelligence_info = f"""
**DADOS DE THREAT INTELLIGENCE:**
"""
            if cisa_kev_data:
                kev_count = cisa_kev_data.get('total_kev_vulnerabilities', 0)
                threat_intelligence_info += f"""
- Vulnerabilidades CISA KEV: {kev_count} (exploração ativa confirmada)
- Prioridade máxima para remediação devido ao risco de exploração imediata
"""
            
            if epss_stats:
                high_epss = epss_stats.get('high_probability_count', 0)
                avg_epss = epss_stats.get('average_score', 0)
                threat_intelligence_info += f"""
- Vulnerabilidades com alta probabilidade de exploração (EPSS): {high_epss}
- Score médio EPSS: {avg_epss:.3f} (predição de exploração em 30 dias)
"""
        
        vendor_risk_info = ""
        if vendor_product_data:
            top_vendors = vendor_product_data.get('top_affected_vendors', [])[:5]
            vendor_risk_info = f"""
**ANÁLISE DE RISCO POR VENDOR:**
- Principais vendors afetados: {', '.join([f"{v['vendor']} ({v['count']})" for v in top_vendors])}
- Concentração de risco por fornecedor pode amplificar impacto de negócio
- Necessidade de avaliação de fornecedores alternativos
"""
        
        return f"""Realize uma Business Impact Analysis (BIA) baseada nos seguintes dados:

**Ativos Críticos Identificados:**
{len(critical_assets)} ativos classificados como críticos

**Vulnerabilidades de Alto Impacto:**
- Críticas: {critical_vulns}
- Altas: {high_severity_vulns}

{threat_intelligence_info}
{vendor_risk_info}

**Atributos dos Ativos:**
{self._format_asset_attributes(asset_attributes[:10])}  # Limitar para não sobrecarregar

**ANÁLISE BIA REQUERIDA:**

1. **Impacto Financeiro Potencial**
   - Perda de receita por hora/dia de interrupção
   - Custos de recuperação e resposta a incidentes
   - Multas regulatórias e penalidades
   - Considere dados CISA KEV e EPSS para priorização de risco

2. **Impacto Operacional nos Processos**
   - Interrupção de processos críticos de negócio
   - Degradação de serviços e SLAs
   - Impacto na produtividade e operações
   - Efeito cascata em sistemas dependentes

3. **Riscos Reputacionais**
   - Danos à marca e confiança do cliente
   - Impacto no valor de mercado
   - Relacionamento com stakeholders
   - Exposição midiática negativa

4. **Tempo de Recuperação Estimado (RTO/RPO)**
   - Recovery Time Objective por categoria de ativo
   - Recovery Point Objective para dados críticos
   - Mean Time To Recovery (MTTR)
   - Janelas de manutenção disponíveis

5. **Interdependências Críticas**
   - Mapeamento de dependências entre sistemas
   - Fornecedores e parceiros críticos
   - Infraestrutura compartilhada
   - Pontos únicos de falha

6. **Classificação de Prioridade para Remediação**
   - Matriz de risco (probabilidade x impacto)
   - Priorização baseada em criticidade de negócio
   - Consideração de dados CISA KEV (prioridade máxima)
   - Integração de scores EPSS para probabilidade de exploração

**CONSIDERAÇÕES ESPECIAIS:**
- Vulnerabilidades CISA KEV devem ser tratadas como CRÍTICAS para BIA
- Scores EPSS altos indicam maior probabilidade de materialização do risco
- Concentração de vulnerabilidades por vendor pode amplificar impacto
- Considere cenários de exploração simultânea de múltiplas vulnerabilidades

Forneça uma análise BIA estruturada em markdown com foco em impactos quantificáveis de negócio."""
    
    def _build_remediation_prompt(self, priority_vulnerabilities, total_vulns, 
                                critical_count, high_count, available_resources):
        """Constrói prompt para plano de remediação."""
        resources_info = ""
        if available_resources:
            resources_info = f"**Recursos Disponíveis:** {available_resources}"
        
        return f"""Crie um plano de remediação para as seguintes vulnerabilidades:

**Resumo das Vulnerabilidades:**
- Total: {total_vulns}
- Críticas: {critical_count}
- Altas: {high_count}

**Vulnerabilidades Prioritárias:**
{self._format_priority_vulnerabilities(priority_vulnerabilities[:15])}

{resources_info}

**Plano Deve Incluir:**
1. Cronograma de remediação (30/60/90 dias)
2. Priorização baseada em risco
3. Medidas temporárias de mitigação
4. Recursos necessários
5. Responsabilidades e marcos
6. Critérios de validação
7. Plano de contingência

Formate como um plano executável em markdown."""
    
    def _build_technical_analysis_prompt(self, vulnerability_data, cve_details, 
                                       cvss_stats, cwe_distribution):
        """Constrói prompt para análise técnica."""
        return f"""Realize uma análise técnica detalhada baseada nos seguintes dados:

**Estatísticas CVSS:**
{self._format_cvss_stats(cvss_stats)}

**Distribuição de CWE (Top 10):**
{self._format_cwe_distribution(cwe_distribution)}

**Detalhes das CVEs:**
{self._format_cve_details(cve_details[:10])}

**Análise Técnica Requerida:**
1. Análise de vetores de ataque predominantes
2. Avaliação de exploitabilidade
3. Tendências de vulnerabilidades
4. Análise de superfície de ataque
5. Recomendações técnicas específicas
6. Indicadores de comprometimento (IoCs)

Forneça uma análise técnica abrangente em markdown."""
    
    def _build_technical_study_prompt(self, asset_configurations, vuln_data, 
                                    technical_details, security_architecture):
        """Constrói prompt para estudo técnico."""
        arch_info = ""
        if security_architecture:
            arch_info = f"""
**Arquitetura de Segurança:**
{self._format_security_architecture(security_architecture)}
"""
        
        return f"""Realize um estudo técnico aprofundado baseado nos seguintes dados:

**Configurações dos Ativos ({len(asset_configurations)} ativos):**
{self._format_asset_configurations(asset_configurations[:10])}

**Dados de Vulnerabilidades:**
{self._format_vulnerability_summary(vuln_data)}

**Detalhes Técnicos:**
{self._format_technical_details(technical_details)}
{arch_info}

**Estudo Técnico Deve Incluir:**
1. **Análise Técnica Aprofundada**
   - Avaliação detalhada das configurações atuais
   - Identificação de gaps de segurança
   - Análise de conformidade com padrões

2. **Configurações de Segurança**
   - Revisão de hardening aplicado
   - Configurações recomendadas
   - Políticas de segurança sugeridas

3. **Avaliação de Arquitetura**
   - Análise da arquitetura de segurança
   - Pontos de falha identificados
   - Melhorias arquiteturais

4. **Recomendações Técnicas Específicas**
   - Implementações técnicas detalhadas
   - Configurações específicas por tecnologia
   - Ferramentas e soluções recomendadas

5. **Procedimentos de Implementação**
   - Passos detalhados de implementação
   - Scripts e comandos específicos
   - Cronograma técnico de implementação

Forneça um estudo técnico abrangente e detalhado em markdown."""

    def _build_cisa_kev_prompt(self, cisa_kev_data, vulnerability_data):
        """Constrói prompt para análise CISA KEV."""
        kev_vulns = cisa_kev_data.get('kev_vulnerabilities', [])
        kev_count = len(kev_vulns)
        
        return f"""**Análise de Vulnerabilidades CISA KEV**

**Vulnerabilidades KEV Identificadas:** {kev_count}

**Vulnerabilidades KEV Críticas:**
{self._format_kev_vulnerabilities(kev_vulns[:10])}

**Dados de Vulnerabilidades Gerais:**
{self._format_vulnerability_summary(vulnerability_data)}

**Análise Requerida:**
1. **Priorização Urgente** - Vulnerabilidades com exploração ativa confirmada
2. **Contexto de Ameaças** - Análise do cenário atual de ameaças
3. **Impacto de Exploração** - Consequências de ataques em andamento
4. **Recomendações de Mitigação** - Ações imediatas e de longo prazo
5. **Timeline de Remediação** - Cronograma acelerado para KEV

Forneça análise focada na urgência e criticidade das vulnerabilidades KEV."""

    def _build_epss_prompt(self, epss_data, vulnerability_data):
        """Constrói prompt para análise EPSS."""
        epss_stats = epss_data.get('epss_statistics', {})
        high_probability_vulns = epss_data.get('high_probability_vulnerabilities', [])
        
        return f"""**Análise de Probabilidade de Exploração (EPSS)**

**Estatísticas EPSS:**
{self._format_epss_statistics(epss_stats)}

**Vulnerabilidades com Alta Probabilidade de Exploração:**
{self._format_epss_vulnerabilities(high_probability_vulns[:10])}

**Dados de Vulnerabilidades Gerais:**
{self._format_vulnerability_summary(vulnerability_data)}

**Análise Requerida:**
1. **Interpretação de Scores EPSS** - Significado dos percentis de probabilidade
2. **Priorização Inteligente** - Combinação de EPSS com CVSS e contexto
3. **Tendências de Exploração** - Análise temporal de probabilidades
4. **Recomendações de Priorização** - Estratégia baseada em dados quantitativos
5. **Correlação de Riscos** - Relação entre probabilidade e impacto

Forneça análise quantitativa focada em priorização baseada em dados."""

    def _build_vendor_product_prompt(self, vendor_product_data, vulnerability_data):
        """Constrói prompt para análise vendor/product."""
        vendor_stats = vendor_product_data.get('vendor_statistics', {})
        product_stats = vendor_product_data.get('product_statistics', {})
        
        return f"""**Análise de Vulnerabilidades por Vendor e Produto**

**Estatísticas por Vendor:**
{self._format_vendor_statistics(vendor_stats)}

**Estatísticas por Produto:**
{self._format_product_statistics(product_stats)}

**Dados de Vulnerabilidades Gerais:**
{self._format_vulnerability_summary(vulnerability_data)}

**Análise Requerida:**
1. **Análise de Vendors** - Fabricantes com maior exposição a vulnerabilidades
2. **Produtos Críticos** - Produtos mais vulneráveis no ambiente
3. **Padrões de Vulnerabilidades** - Tendências por fabricante e categoria
4. **Estratégia de Diversificação** - Recomendações para redução de risco
5. **Gestão de Patch Management** - Estratégias específicas por vendor/produto

Forneça análise estratégica focada em gestão de vendors e produtos."""
    
    # Métodos de formatação de dados
    
    def _format_severity_distribution(self, vuln_by_severity):
        """Formata distribuição de severidade para o prompt."""
        if not vuln_by_severity:
            return "Nenhuma vulnerabilidade identificada"
        
        formatted = []
        for severity, count in vuln_by_severity.items():
            formatted.append(f"- {severity}: {count}")
        return "\n".join(formatted)
    
    def _format_risk_stats(self, risk_stats):
        """Formata estatísticas de risco para o prompt."""
        if not risk_stats:
            return "Estatísticas de risco não disponíveis"
        
        return f"""- Score médio de risco: {risk_stats.get('mean', 'N/A'):.2f}
- Score máximo: {risk_stats.get('max', 'N/A')}
- Score mínimo: {risk_stats.get('min', 'N/A')}
- Total de avaliações: {risk_stats.get('count', 0)}"""
    
    def _format_asset_attributes(self, asset_attributes):
        """Formata atributos de ativos para o prompt."""
        if not asset_attributes:
            return "Nenhum atributo de ativo disponível"
        
        formatted = []
        for asset in asset_attributes:
            name = asset.get('name', 'N/A')
            criticality = asset.get('criticality', 'N/A')
            type_info = asset.get('type', 'N/A')
            formatted.append(f"- {name} (Criticidade: {criticality}, Tipo: {type_info})")
        
        return "\n".join(formatted)
    
    def _format_priority_vulnerabilities(self, vulnerabilities):
        """Formata vulnerabilidades prioritárias para o prompt."""
        if not vulnerabilities:
            return "Nenhuma vulnerabilidade prioritária"
        
        formatted = []
        for vuln in vulnerabilities:
            cve_id = vuln.get('cve_id', 'N/A')
            severity = vuln.get('severity', 'N/A')
            cvss = vuln.get('cvss_score', 'N/A')
            formatted.append(f"- {cve_id} (Severidade: {severity}, CVSS: {cvss})")
        
        return "\n".join(formatted)
    
    def _format_cvss_stats(self, cvss_stats):
        """Formata estatísticas CVSS para o prompt."""
        if not cvss_stats:
            return "Estatísticas CVSS não disponíveis"
        
        return f"""- Score médio: {cvss_stats.get('mean', 'N/A'):.2f}
- Score máximo: {cvss_stats.get('max', 'N/A')}
- Score mínimo: {cvss_stats.get('min', 'N/A')}
- Total analisado: {cvss_stats.get('count', 0)}"""
    
    def _format_cwe_distribution(self, cwe_distribution):
        """Formata distribuição CWE para o prompt."""
        if not cwe_distribution:
            return "Distribuição CWE não disponível"
        
        # Ordenar por frequência e pegar top 10
        sorted_cwes = sorted(cwe_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
        
        formatted = []
        for cwe_id, count in sorted_cwes:
            formatted.append(f"- {cwe_id}: {count} ocorrências")
        
        return "\n".join(formatted)
    
    def _format_cve_details(self, cve_details):
        """Formata detalhes das CVEs para o prompt."""
        if not cve_details:
            return "Detalhes de CVE não disponíveis"
        
        formatted = []
        for cve in cve_details:
            cve_id = cve.get('cve_id', 'N/A')
            description = cve.get('description', 'N/A')[:100] + "..."
            formatted.append(f"- {cve_id}: {description}")
        
        return "\n".join(formatted)
    
    def _format_asset_configurations(self, asset_configurations):
        """Formata configurações de ativos para o prompt."""
        if not asset_configurations:
            return "Nenhuma configuração de ativo disponível"
        
        formatted = []
        for asset in asset_configurations:
            name = asset.get('name', 'N/A')
            os_info = asset.get('operating_system', 'N/A')
            services = asset.get('services', [])
            service_count = len(services) if services else 0
            formatted.append(f"- {name} (OS: {os_info}, Serviços: {service_count})")
        
        return "\n".join(formatted)
    
    def _format_vulnerability_summary(self, vuln_data):
        """Formata resumo de vulnerabilidades para o prompt."""
        if not vuln_data:
            return "Dados de vulnerabilidades não disponíveis"
        
        total = vuln_data.get('total_vulnerabilities', 0)
        by_severity = vuln_data.get('by_severity', {})
        
        summary = [f"Total de vulnerabilidades: {total}"]
        for severity, count in by_severity.items():
            summary.append(f"- {severity}: {count}")
        
        return "\n".join(summary)
    
    def _format_technical_details(self, technical_details):
        """Formata detalhes técnicos para o prompt."""
        if not technical_details:
            return "Detalhes técnicos não disponíveis"
        
        formatted = []
        for key, value in technical_details.items():
            formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)
    
    def _format_security_architecture(self, security_architecture):
        """Formata informações de arquitetura de segurança para o prompt."""
        if not security_architecture:
            return "Informações de arquitetura não disponíveis"
        
        formatted = []
        for component, details in security_architecture.items():
            formatted.append(f"- {component}: {details}")
        
        return "\n".join(formatted)

    def _format_kev_vulnerabilities(self, kev_vulns):
        """Formata vulnerabilidades KEV para o prompt."""
        if not kev_vulns:
            return "Nenhuma vulnerabilidade KEV identificada"
        
        formatted = []
        for vuln in kev_vulns:
            cve_id = vuln.get('cve_id', 'N/A')
            vendor = vuln.get('vendor_project', 'N/A')
            product = vuln.get('product', 'N/A')
            date_added = vuln.get('date_added', 'N/A')
            due_date = vuln.get('due_date', 'N/A')
            formatted.append(f"- {cve_id} ({vendor} {product}) - Adicionado: {date_added}, Prazo: {due_date}")
        
        return "\n".join(formatted)

    def _format_epss_statistics(self, epss_stats):
        """Formata estatísticas EPSS para o prompt."""
        if not epss_stats:
            return "Estatísticas EPSS não disponíveis"
        
        formatted = []
        avg_score = epss_stats.get('average_score', 0)
        high_prob_count = epss_stats.get('high_probability_count', 0)
        total_with_epss = epss_stats.get('total_with_epss', 0)
        
        formatted.append(f"- Score EPSS médio: {avg_score:.3f}")
        formatted.append(f"- Vulnerabilidades com alta probabilidade (>0.7): {high_prob_count}")
        formatted.append(f"- Total com dados EPSS: {total_with_epss}")
        
        return "\n".join(formatted)

    def _format_epss_vulnerabilities(self, epss_vulns):
        """Formata vulnerabilidades EPSS para o prompt."""
        if not epss_vulns:
            return "Nenhuma vulnerabilidade com dados EPSS"
        
        formatted = []
        for vuln in epss_vulns:
            cve_id = vuln.get('cve_id', 'N/A')
            epss_score = vuln.get('epss_score', 0)
            percentile = vuln.get('epss_percentile', 0)
            formatted.append(f"- {cve_id}: Score {epss_score:.3f} (Percentil {percentile:.1f}%)")
        
        return "\n".join(formatted)

    def _format_vendor_statistics(self, vendor_stats):
        """Formata estatísticas de vendors para o prompt."""
        if not vendor_stats:
            return "Estatísticas de vendors não disponíveis"
        
        formatted = []
        for vendor, stats in vendor_stats.items():
            vuln_count = stats.get('vulnerability_count', 0)
            critical_count = stats.get('critical_count', 0)
            formatted.append(f"- {vendor}: {vuln_count} vulnerabilidades ({critical_count} críticas)")
        
        return "\n".join(formatted)

    def _format_product_statistics(self, product_stats):
        """Formata estatísticas de produtos para o prompt."""
        if not product_stats:
            return "Estatísticas de produtos não disponíveis"
        
        formatted = []
        for product, stats in product_stats.items():
            vuln_count = stats.get('vulnerability_count', 0)
            critical_count = stats.get('critical_count', 0)
            formatted.append(f"- {product}: {vuln_count} vulnerabilidades ({critical_count} críticas)")
        
        return "\n".join(formatted)
    
    # Métodos de demonstração (modo demo)
    
    def _generate_demo_executive_summary(self, report_data, report_type):
        """Gera resumo executivo de demonstração."""
        asset_count = report_data.get('assets', {}).get('total_assets', 0)
        vuln_count = report_data.get('vulnerabilities', {}).get('total_vulnerabilities', 0)
        
        return f"""# Resumo Executivo - Relatório de Cybersegurança

## Situação Atual
Nossa análise de segurança abrangeu **{asset_count} ativos** e identificou **{vuln_count} vulnerabilidades** que requerem atenção imediata.

## Principais Riscos Identificados
- **Exposição crítica**: Vulnerabilidades de alta severidade em sistemas essenciais
- **Superfície de ataque ampliada**: Múltiplos vetores de entrada identificados
- **Patches pendentes**: Correções de segurança não aplicadas em tempo hábil

## Impacto no Negócio
- **Risco operacional**: Potencial interrupção de serviços críticos
- **Exposição de dados**: Possibilidade de vazamento de informações sensíveis
- **Conformidade**: Riscos regulatórios e de compliance

## Recomendações Prioritárias
1. **Implementação imediata** de patches críticos
2. **Fortalecimento** dos controles de acesso
3. **Monitoramento contínuo** de ameaças
4. **Treinamento** da equipe de segurança

## Próximos Passos
- Execução do plano de remediação em 30 dias
- Implementação de monitoramento 24/7
- Revisão trimestral da postura de segurança

---
*Relatório gerado em modo demonstração. Configure a API OpenAI para análises personalizadas.*"""
    
    def _generate_demo_bia(self, report_data, asset_attributes):
        """Gera análise BIA de demonstração."""
        return f"""# Business Impact Analysis (BIA)

## Resumo Executivo
Análise de impacto de negócio identificou **riscos significativos** aos processos críticos organizacionais.

## Impacto Financeiro
- **Perda estimada por hora de inatividade**: $50,000 - $200,000
- **Custo de recuperação**: $100,000 - $500,000
- **Multas regulatórias potenciais**: $250,000 - $1,000,000

## Impacto Operacional
### Processos Críticos Afetados
- **Sistemas de produção**: Interrupção total (RTO: 4 horas)
- **Processamento de transações**: Degradação severa (RTO: 2 horas)
- **Comunicações internas**: Impacto moderado (RTO: 1 hora)

### Tempo de Recuperação
- **RTO (Recovery Time Objective)**: 4 horas máximo
- **RPO (Recovery Point Objective)**: 1 hora máximo

## Riscos Reputacionais
- **Confiança do cliente**: Alto risco de perda
- **Imagem da marca**: Impacto negativo significativo
- **Relacionamento com parceiros**: Deterioração potencial

## Interdependências Críticas
- Sistemas de backup e recuperação
- Fornecedores de serviços essenciais
- Infraestrutura de rede e comunicações

## Classificação de Prioridade
1. **Crítico**: Remediação em 24-48 horas
2. **Alto**: Remediação em 1 semana
3. **Médio**: Remediação em 1 mês

---
*Análise gerada em modo demonstração. Configure a API OpenAI para análises personalizadas.*"""

    def _generate_demo_cisa_kev_analysis(self, cisa_kev_data, vulnerability_data):
        """Gera análise CISA KEV de demonstração."""
        return """# Análise CISA KEV - Vulnerabilidades Conhecidas Exploradas

## Resumo Executivo
Análise das vulnerabilidades presentes no catálogo CISA KEV (Known Exploited Vulnerabilities) identificadas no ambiente.

## Vulnerabilidades CISA KEV Identificadas

### Vulnerabilidades Críticas
- **CVE-2023-4966**: Citrix NetScaler - Exploração ativa detectada
- **CVE-2023-3519**: Citrix NetScaler ADC - RCE crítico
- **CVE-2023-20198**: Cisco IOS XE - Implante web malicioso

### Status de Remediação
- **Pendentes**: 3 vulnerabilidades críticas
- **Em andamento**: 2 vulnerabilidades
- **Corrigidas**: 1 vulnerabilidade

## Impacto de Negócio
- **Risco Imediato**: CRÍTICO
- **Probabilidade de Exploração**: ALTA (confirmada pelo CISA)
- **Impacto Financeiro Estimado**: R$ 2.5M - R$ 5M

## Recomendações Prioritárias
1. **Ação Imediata**: Aplicar patches para CVE-2023-4966
2. **Monitoramento**: Implementar detecção de IoCs conhecidos
3. **Isolamento**: Segmentar sistemas afetados
4. **Comunicação**: Notificar stakeholders sobre riscos

---
*Análise CISA KEV gerada em modo demonstração.*"""

    def _generate_demo_epss_analysis(self, epss_data, vulnerability_data):
        """Gera análise EPSS de demonstração."""
        return """# Análise EPSS - Exploit Prediction Scoring System

## Resumo Executivo
Análise preditiva de exploração baseada em scores EPSS para priorização de remediação.

## Distribuição de Scores EPSS

### Vulnerabilidades de Alto Risco (EPSS > 0.7)
- **CVE-2023-4966**: EPSS 0.97 (97% probabilidade)
- **CVE-2023-3519**: EPSS 0.89 (89% probabilidade)
- **CVE-2023-20198**: EPSS 0.85 (85% probabilidade)

### Vulnerabilidades de Médio Risco (EPSS 0.3-0.7)
- **CVE-2023-1234**: EPSS 0.65 (65% probabilidade)
- **CVE-2023-5678**: EPSS 0.45 (45% probabilidade)

### Estatísticas Gerais
- **Score EPSS Médio**: 0.68
- **Vulnerabilidades > 0.7**: 15 (30%)
- **Vulnerabilidades > 0.5**: 25 (50%)

## Correlação com Atividade de Exploração
- **Exploits Públicos**: 8 vulnerabilidades
- **PoCs Disponíveis**: 12 vulnerabilidades
- **Atividade em Wild**: 5 vulnerabilidades confirmadas

## Priorização Baseada em EPSS
1. **Prioridade 1** (EPSS > 0.8): 3 vulnerabilidades
2. **Prioridade 2** (EPSS 0.5-0.8): 12 vulnerabilidades
3. **Prioridade 3** (EPSS < 0.5): 35 vulnerabilidades

## Recomendações
- Focar recursos nas vulnerabilidades com EPSS > 0.7
- Monitorar tendências de scores EPSS
- Integrar EPSS no processo de patch management

---
*Análise EPSS gerada em modo demonstração.*"""

    def _generate_demo_vendor_product_analysis(self, vendor_product_data, vulnerability_data):
        """Gera análise de vendor/produto de demonstração."""
        return """# Análise por Vendor e Produto

## Resumo Executivo
Análise da distribuição de vulnerabilidades por fornecedor e produto para identificar riscos concentrados.

## Distribuição por Vendor

### Top 5 Vendors com Mais Vulnerabilidades
1. **Microsoft**: 45 vulnerabilidades (32%)
   - Windows: 25 vulnerabilidades
   - Office: 12 vulnerabilidades
   - Exchange: 8 vulnerabilidades

2. **Adobe**: 28 vulnerabilidades (20%)
   - Acrobat Reader: 15 vulnerabilidades
   - Flash Player: 8 vulnerabilidades
   - Creative Suite: 5 vulnerabilidades

3. **Oracle**: 22 vulnerabilidades (16%)
   - Java: 12 vulnerabilidades
   - Database: 6 vulnerabilidades
   - WebLogic: 4 vulnerabilidades

4. **Cisco**: 18 vulnerabilidades (13%)
   - IOS: 10 vulnerabilidades
   - ASA: 5 vulnerabilidades
   - Webex: 3 vulnerabilidades

5. **VMware**: 15 vulnerabilidades (11%)
   - vSphere: 8 vulnerabilidades
   - Workstation: 4 vulnerabilidades
   - Horizon: 3 vulnerabilidades

## Análise de Criticidade por Vendor

### Vulnerabilidades Críticas (CVSS > 9.0)
- **Microsoft**: 8 vulnerabilidades críticas
- **Adobe**: 6 vulnerabilidades críticas
- **Oracle**: 4 vulnerabilidades críticas

### Produtos Mais Afetados
1. **Windows Server 2019**: 15 vulnerabilidades
2. **Adobe Acrobat Reader**: 12 vulnerabilidades
3. **Oracle Java SE**: 10 vulnerabilidades

## Concentração de Risco
- **Monocultura Microsoft**: 65% dos ativos
- **Dependência Java**: 80% das aplicações
- **Infraestrutura Cisco**: 90% da rede

## Recomendações Estratégicas
1. **Diversificação**: Reduzir dependência de vendors únicos
2. **Patch Management**: Priorizar vendors com mais vulnerabilidades
3. **Monitoramento**: Acompanhar advisories de vendors críticos
4. **Contratos**: Incluir SLAs de segurança com fornecedores

---
*Análise de vendor/produto gerada em modo demonstração.*"""
    
    def _generate_demo_technical_study(self, report_data, asset_configurations):
        """Gera estudo técnico de demonstração."""
        asset_count = len(asset_configurations)
        
        return f"""# Estudo Técnico - Análise Aprofundada de Segurança

## Resumo Executivo
Estudo técnico abrangente de **{asset_count} ativos** identificou gaps críticos de segurança e oportunidades de melhoria arquitetural.

## 1. Análise Técnica Aprofundada

### Configurações Atuais Avaliadas
- **Sistemas operacionais**: Windows Server, Linux (Ubuntu/CentOS)
- **Serviços de rede**: HTTP/HTTPS, SSH, RDP, DNS
- **Aplicações**: Web servers, databases, APIs
- **Infraestrutura**: Firewalls, load balancers, proxies

### Gaps de Segurança Identificados
#### Configurações Críticas
- **Hardening insuficiente**: 75% dos sistemas não seguem baselines de segurança
- **Patches pendentes**: 40+ vulnerabilidades críticas não corrigidas
- **Configurações padrão**: Credenciais e configurações inseguras mantidas

#### Conformidade com Padrões
- **CIS Benchmarks**: Conformidade de apenas 60%
- **NIST Framework**: Gaps em controles de acesso e monitoramento
- **ISO 27001**: Deficiências em gestão de ativos e classificação

## 2. Configurações de Segurança

### Hardening Aplicado (Status Atual)
```bash
# Exemplo de configurações encontradas
- Password policies: Parcialmente implementadas
- Account lockout: Configurado (5 tentativas)
- Audit logging: Habilitado em 70% dos sistemas
- Service accounts: Privilégios excessivos identificados
```

### Configurações Recomendadas
#### Sistemas Windows
```powershell
# Políticas de senha recomendadas
net accounts /minpwlen:12 /maxpwage:90 /minpwage:1
# Desabilitar protocolos inseguros
Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol
# Configurar auditoria avançada
auditpol /set /category:"Logon/Logoff" /success:enable /failure:enable
```

#### Sistemas Linux
```bash
# Configurações SSH seguras
echo "Protocol 2" >> /etc/ssh/sshd_config
echo "PermitRootLogin no" >> /etc/ssh/sshd_config
echo "MaxAuthTries 3" >> /etc/ssh/sshd_config

# Configurar firewall
ufw enable
ufw default deny incoming
ufw default allow outgoing
```

### Políticas de Segurança Sugeridas
1. **Gestão de Identidade**: Implementar MFA obrigatório
2. **Controle de Acesso**: Princípio do menor privilégio
3. **Monitoramento**: Logging centralizado e SIEM
4. **Backup**: Estratégia 3-2-1 com testes regulares

## 3. Avaliação de Arquitetura

### Arquitetura de Segurança Atual
```
[Internet] → [Firewall] → [DMZ] → [Internal Network]
                ↓
        [Web Servers] → [App Servers] → [Database]
```

### Pontos de Falha Identificados
- **Single point of failure**: Firewall único sem redundância
- **Segmentação insuficiente**: Rede plana com acesso lateral
- **Monitoramento limitado**: Visibilidade reduzida do tráfego interno
- **Backup centralizado**: Risco de comprometimento simultâneo

### Melhorias Arquiteturais
#### Arquitetura Proposta
```
[Internet] → [WAF] → [Load Balancer] → [Firewall Cluster]
                                           ↓
[DMZ Segmentada] → [App Network] → [Database Network]
        ↓                ↓              ↓
   [Web Tier]    [Application Tier] [Data Tier]
```

#### Componentes Recomendados
- **Zero Trust Architecture**: Verificação contínua de identidade
- **Micro-segmentação**: Isolamento granular de workloads
- **SASE (Secure Access Service Edge)**: Convergência de rede e segurança
- **Cloud Security Posture Management**: Monitoramento contínuo

## 4. Recomendações Técnicas Específicas

### Implementações por Tecnologia
#### Web Applications
```
# Configuração Nginx segura
server {{
    listen 443 ssl http2;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
}}
```

#### Database Security
```sql
-- Configurações MySQL/PostgreSQL
-- Criar usuários com privilégios mínimos
CREATE USER 'app_user'@'localhost' IDENTIFIED BY 'complex_password';
GRANT SELECT, INSERT, UPDATE ON app_db.* TO 'app_user'@'localhost';

-- Habilitar SSL
SET GLOBAL ssl_ca = '/path/to/ca-cert.pem';
SET GLOBAL ssl_cert = '/path/to/server-cert.pem';
SET GLOBAL ssl_key = '/path/to/server-key.pem';
```

### Ferramentas e Soluções Recomendadas
#### Monitoramento e SIEM
- **Splunk/ELK Stack**: Centralização de logs
- **Wazuh**: HIDS/SIEM open source
- **OSSEC**: Monitoramento de integridade

#### Vulnerability Management
- **OpenVAS**: Scanner de vulnerabilidades
- **Nessus**: Avaliação comercial
- **Qualys VMDR**: Solução cloud

#### Network Security
- **pfSense**: Firewall open source
- **Suricata**: IDS/IPS
- **Zeek**: Análise de tráfego de rede

## 5. Procedimentos de Implementação

### Fase 1: Preparação (Semanas 1-2)
```bash
# 1. Backup completo dos sistemas
rsync -avz /etc/ /backup/config-backup-$(date +%Y%m%d)/

# 2. Documentação da configuração atual
nmap -sS -O target_network/24 > current_network_scan.txt
systemctl list-units --type=service > current_services.txt

# 3. Criação de ambiente de teste
vagrant up test-environment
```

### Fase 2: Hardening Básico (Semanas 3-4)
```bash
# 1. Aplicação de patches críticos
apt update && apt upgrade -y  # Ubuntu/Debian
yum update -y                 # CentOS/RHEL

# 2. Configuração de firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw enable

# 3. Configuração de auditoria
echo "audit=1" >> /etc/default/grub
update-grub
```

### Fase 3: Implementação Avançada (Semanas 5-8)
```bash
# 1. Deploy de SIEM
docker-compose up -d elk-stack
# 2. Configuração de monitoramento
ansible-playbook -i inventory monitoring-setup.yml
# 3. Implementação de backup
./setup-backup-strategy.sh
```

### Cronograma Técnico de Implementação
| Semana | Atividade | Responsável | Status |
|--------|-----------|-------------|---------|
| 1-2 | Preparação e backup | Equipe Infra | Planejado |
| 3-4 | Hardening básico | Equipe Segurança | Planejado |
| 5-6 | Implementação SIEM | Equipe SOC | Planejado |
| 7-8 | Testes e validação | Equipe QA | Planejado |

### Scripts de Automação
```bash
#!/bin/bash
# security-hardening.sh
# Script de hardening automatizado

echo "Iniciando processo de hardening..."

# Atualizar sistema
apt update && apt upgrade -y

# Configurar SSH
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# Configurar firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw enable

echo "Hardening básico concluído!"
```

## Conclusões e Próximos Passos

### Prioridades Imediatas
1. **Aplicação de patches críticos** (24-48 horas)
2. **Implementação de hardening básico** (1 semana)
3. **Deploy de monitoramento** (2 semanas)

### Investimentos Recomendados
- **SIEM/SOC**: $50,000 - $100,000 anuais
- **Ferramentas de segurança**: $25,000 - $50,000
- **Treinamento da equipe**: $15,000 - $30,000

### Métricas de Sucesso
- **Redução de 80%** em vulnerabilidades críticas
- **Tempo de detecção** < 15 minutos
- **Tempo de resposta** < 1 hora
- **Conformidade** > 95% com frameworks

---
*Estudo técnico gerado em modo demonstração. Configure a API OpenAI para análises personalizadas.*"""
    
    def _generate_demo_remediation_plan(self, priority_vulnerabilities):
        """Gera plano de remediação de demonstração."""
        vuln_count = len(priority_vulnerabilities)
        
        return f"""# Plano de Remediação de Vulnerabilidades

## Resumo
Plano estruturado para correção de **{vuln_count} vulnerabilidades prioritárias** identificadas.

## Cronograma de Execução

### Fase 1 - Ações Imediatas (0-30 dias)
- **Patches críticos**: Aplicação em sistemas de produção
- **Medidas temporárias**: Implementação de controles compensatórios
- **Monitoramento intensivo**: Vigilância 24/7 dos sistemas afetados

### Fase 2 - Correções Estruturais (30-60 dias)
- **Atualizações de sistema**: Upgrade de componentes vulneráveis
- **Configurações de segurança**: Hardening dos sistemas
- **Testes de penetração**: Validação das correções

### Fase 3 - Melhorias Contínuas (60-90 dias)
- **Automação**: Implementação de patches automáticos
- **Treinamento**: Capacitação da equipe técnica
- **Documentação**: Atualização de procedimentos

## Recursos Necessários
- **Equipe técnica**: 3-5 especialistas
- **Janelas de manutenção**: 4-6 horas por sistema
- **Orçamento estimado**: $50,000 - $150,000

## Responsabilidades
- **Gerente de TI**: Coordenação geral
- **Equipe de Segurança**: Implementação técnica
- **Administradores de Sistema**: Aplicação de patches

## Marcos e Validação
- **Semana 1**: 50% dos patches críticos aplicados
- **Semana 2**: 100% dos patches críticos aplicados
- **Semana 4**: Validação completa das correções

## Plano de Contingência
- **Rollback procedures**: Procedimentos de reversão
- **Sistemas de backup**: Ativação em caso de falha
- **Comunicação de crise**: Plano de comunicação interna/externa

---
*Plano gerado em modo demonstração. Configure a API OpenAI para planos personalizados.*"""
    
    def _generate_demo_technical_analysis(self, vulnerability_data):
        """Gera análise técnica de demonstração."""
        total_vulns = vulnerability_data.get('total_vulnerabilities', 0)
        
        return f"""# Análise Técnica de Vulnerabilidades

## Resumo Técnico
Análise detalhada de **{total_vulns} vulnerabilidades** identificadas no ambiente.

### Distribuição por Severidade
- **Críticas**: 15% das vulnerabilidades
- **Altas**: 25% das vulnerabilidades  
- **Médias**: 40% das vulnerabilidades
- **Baixas**: 20% das vulnerabilidades

### Principais Vetores de Ataque
1. **Aplicações Web**: Injeção SQL, XSS, CSRF
2. **Serviços de Rede**: Protocolos inseguros, configurações padrão
3. **Sistema Operacional**: Patches pendentes, configurações fracas

### Recomendações Técnicas
- Implementar programa de patch management
- Configurar hardening de sistemas
- Estabelecer monitoramento contínuo
- Realizar testes de penetração regulares

---
*Análise gerada em modo demonstração. Configure a API OpenAI para análises personalizadas.*"""
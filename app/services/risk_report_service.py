import os
import re
import logging
from typing import Dict, Any, Optional
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
    
    def _initialize_client(self):
        """
        Inicializa o cliente OpenAI dentro do contexto da aplicação.
        """
        if self._initialized:
            return
            
        self.api_key = current_app.config.get('OPENAI_API_KEY')
        self.model = current_app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = current_app.config.get('OPENAI_MAX_TOKENS', 800)
        self.temperature = current_app.config.get('OPENAI_TEMPERATURE', 0.5)
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY não configurada - modo demo ativo")
            self.client = None
        else:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("Cliente OpenAI inicializado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao inicializar cliente OpenAI: {e}")
                self.client = None
        
        self._initialized = True
    
    def build_markdown_prompt(self, description: str) -> str:
        """
        Constrói o prompt em Markdown para análise de risco.
        
        Args:
            description: Descrição da vulnerabilidade
            
        Returns:
            Prompt formatado para análise de risco
        """
        return f"""Você é um analista de risco cibernético especializado em segurança da informação.
Gere um **relatório técnico profissional em formato Markdown**, com linguagem clara, objetiva e com foco em ações práticas para mitigação da vulnerabilidade descrita a seguir.

Sempre que uma informação não estiver disponível ou aplicável, indique explicitamente com: **Não aplicável** ou **Nenhuma informação conhecida**.

---

## Descrição Técnica
{description}

## Impacto Potencial
**Impacto Técnico Direto**
<Descreva aqui o impacto técnico direto.>

**Impacto Organizacional e de Negócio**
<Descreva aqui o impacto organizacional e comercial.>

## Vetor de Ataque
<Descreva o método mais provável de exploração.>

## Tecnologias Afetadas
- Sistemas, serviços ou softwares vulneráveis.
- Versões afetadas, se aplicável.

## Exploits Conhecidos
- Exploits públicos disponíveis?
- Há registros de ataques em larga escala?

## Mitigações e Correções
- Patches oficiais ou hotfixes disponíveis?
- Medidas temporárias recomendadas.

## Recomendação de Ação
- Ações imediatas e procedimentos internos recomendados.

## Avaliação de Risco Interno
Classifique o risco considerando que a organização **utiliza a tecnologia afetada**:
- Exposição técnica
- Risco: **Baixo**, **Médio** ou **Alto** (com justificativa)

---

**Importante:** Mantenha o conteúdo em formato Markdown, com tom técnico, objetivo e direto ao ponto.
"""
    
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
            # Buscar vulnerabilidade usando SQLAlchemy (banco configurado pela aplicação)
            vulnerability = db.session.query(Vulnerability).filter_by(cve_id=cve_id).first()
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
                except Exception as e:
                    logger.warning(f"Falha ao consultar coluna 'risks': {e}")

            # Se não houver análise, gerar nova
            if not existing_risks or not str(existing_risks).strip():
                logger.info(f"Gerando nova análise de risco para CVE {cve_id}")
                
                if not self.client:
                    risks_md = self._generate_demo_risk_analysis(cve_id, description, base_severity, cvss_score)
                else:
                    try:
                        prompt = self.build_markdown_prompt(description)
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "Você é um analista de risco especializado em vulnerabilidades."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=self.max_tokens,
                            temperature=self.temperature
                        )
                        risks_md = self.sanitize_markdown_output(response.choices[0].message.content.strip())
                    except Exception as e:
                        logger.error(f"Erro ao consultar OpenAI: {e}")
                        risks_md = self._generate_demo_risk_analysis(cve_id, description, base_severity, cvss_score)

                # Persistir análise se coluna existir
                if has_risks_col:
                    try:
                        db.session.execute(
                            text("UPDATE vulnerabilities SET risks = :risks WHERE cve_id = :cve"),
                            {"risks": risks_md, "cve": cve_id}
                        )
                        db.session.commit()
                        logger.info(f"Análise de risco salva para CVE {cve_id}")
                    except Exception as e:
                        logger.warning(f"Falha ao salvar análise de risco: {e}")

                return risks_md

            # Retornar análise existente
            return existing_risks

        except Exception as e:
            logger.error(f"Erro ao acessar banco de dados ou gerar análise: {e}")
            return f"Erro ao acessar banco de dados: {e}"
    
    def _generate_demo_risk_analysis(self, cve_id: str, description: str, base_severity: str, cvss_score: float) -> str:
        """
        Gera uma análise de risco de demonstração quando a API da OpenAI não está disponível.
        
        Args:
            cve_id: ID da CVE
            description: Descrição da vulnerabilidade
            base_severity: Severidade base
            cvss_score: Score CVSS
            
        Returns:
            Análise de risco simulada em formato Markdown
        """
        severity_map = {
            'LOW': 'Baixo',
            'MEDIUM': 'Médio', 
            'HIGH': 'Alto',
            'CRITICAL': 'Crítico'
        }
        
        severity_pt = severity_map.get(base_severity, 'Não definido')
        
        return f"""# Relatório de Análise de Risco - {cve_id}

## Descrição Técnica
{description}

## Impacto Potencial
**Impacto Técnico Direto**
Baseado na severidade {severity_pt} (CVSS: {cvss_score}), esta vulnerabilidade pode comprometer a segurança do sistema afetado.

**Impacto Organizacional e de Negócio**
Potencial interrupção de serviços e exposição de dados sensíveis, dependendo do contexto de implementação.

## Vetor de Ataque
**Nenhuma informação conhecida** - Análise detalhada requer acesso à API da OpenAI.

## Tecnologias Afetadas
- Sistemas e softwares relacionados à vulnerabilidade {cve_id}
- **Nenhuma informação conhecida** sobre versões específicas

## Exploits Conhecidos
- **Nenhuma informação conhecida** - Verificação em bases de dados de exploits recomendada

## Mitigações e Correções
- Verificar disponibilidade de patches oficiais
- Implementar medidas de segurança compensatórias
- Monitorar sistemas afetados

## Recomendação de Ação
- Avaliar exposição dos sistemas organizacionais
- Priorizar correção baseada na severidade {severity_pt}
- Implementar monitoramento adicional

## Avaliação de Risco Interno
**Exposição técnica:** Dependente da implementação organizacional
**Risco:** {severity_pt} - Baseado na classificação CVSS {cvss_score}

---

*Nota: Esta é uma análise de demonstração. Para análise completa e detalhada, configure a chave da API OpenAI.*
"""
    
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

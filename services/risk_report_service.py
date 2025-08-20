import os
import re
import sqlite3
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from flask import current_app

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
        
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'vulnerabilities.db')
        
        # Conecta ao banco de dados e manipula as vulnerabilidades
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Garante que a coluna 'risks' exista
                cursor.execute("PRAGMA table_info(vulnerabilities)")
                colunas_nomes = [col[1] for col in cursor.fetchall()]
                if 'risks' not in colunas_nomes:
                    cursor.execute("ALTER TABLE vulnerabilities ADD COLUMN risks TEXT")
                    conn.commit()
                    logger.info("Coluna 'risks' adicionada à tabela vulnerabilities")
                
                # Busca os dados da CVE
                cursor.execute("""
                    SELECT vendor, description, baseSeverity, cvssScore, risks
                    FROM vulnerabilities
                    WHERE cve_id = ?
                """, (cve_id,))
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"CVE {cve_id} não encontrada no banco de dados")
                    return "CVE id não encontrada."
                
                vendor, description, base_severity, cvss_score, risks = row
                
                # Gera novo relatório se não existir
                if not risks or not risks.strip():
                    logger.info(f"Gerando nova análise de risco para CVE {cve_id}")
                    
                    if not self.client:
                        # Modo demo - retorna análise simulada
                        risks = self._generate_demo_risk_analysis(cve_id, description, base_severity, cvss_score)
                    else:
                        try:
                            prompt = self.build_markdown_prompt(description)
                            
                            # Prepara a requisição para a OpenAI
                            response = self.client.chat.completions.create(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": "Você é um analista de risco especializado em vulnerabilidades."},
                                    {"role": "user", "content": prompt}
                                ],
                                max_tokens=self.max_tokens,
                                temperature=self.temperature
                            )
                            
                            risks = response.choices[0].message.content.strip()
                            risks = self.sanitize_markdown_output(risks)
                            
                        except Exception as e:
                            logger.error(f"Erro ao consultar OpenAI: {e}")
                            risks = self._generate_demo_risk_analysis(cve_id, description, base_severity, cvss_score)
                    
                    # Atualiza a coluna 'risks' com a análise gerada
                    cursor.execute("UPDATE vulnerabilities SET risks = ? WHERE cve_id = ?", (risks, cve_id))
                    conn.commit()
                    logger.info(f"Análise de risco salva para CVE {cve_id}")
                
                return risks
                
        except sqlite3.Error as e:
            logger.error(f"Erro no banco de dados: {e}")
            return f"Erro ao acessar banco de dados: {e}"
        except Exception as e:
            logger.error(f"Erro desconhecido: {e}")
            return f"Erro desconhecido: {e}"
    
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
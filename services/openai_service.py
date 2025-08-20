import os
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)

class OpenAIService:
    """
    Serviço para integração com a API da OpenAI.
    
    Fornece métodos para gerar respostas de chat usando modelos GPT,
    com configurações flexíveis e tratamento de erros.
    """
    
    def __init__(self):
        """
        Inicializa o serviço OpenAI com configurações da aplicação.
        """
        self.api_key = current_app.config.get('OPENAI_API_KEY')
        self.model = current_app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = current_app.config.get('OPENAI_MAX_TOKENS', 1000)
        self.temperature = current_app.config.get('OPENAI_TEMPERATURE', 0.7)
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY não configurada - modo demo ativo")
            self.client = None
        else:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI Service inicializado com modelo: {self.model}")
            except Exception as e:
                logger.warning(f"Erro ao inicializar OpenAI client: {e} - modo demo ativo")
                self.client = None
    
    def generate_chat_response(
        self, 
        user_message: str, 
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Gera uma resposta de chat usando a API da OpenAI.
        
        Args:
            user_message: Mensagem do usuário
            context: Contexto adicional (dados CVE, etc.)
            conversation_history: Histórico da conversa
            
        Returns:
            Resposta gerada pelo modelo
            
        Raises:
            Exception: Se houver erro na API da OpenAI
        """
        # Verificar se o client está disponível
        if not self.client:
            logger.info("Modo demo ativo - retornando resposta simulada")
            return self._generate_demo_response(user_message, context)
        
        try:
            # Construir mensagens para o chat
            messages = self._build_messages(
                user_message, 
                context, 
                conversation_history
            )
            
            # Fazer chamada para a API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Extrair resposta
            assistant_message = response.choices[0].message.content
            
            logger.info(f"Resposta gerada com sucesso. Tokens usados: {response.usage.total_tokens}")
            return assistant_message
            
        except Exception as e:
            logger.error(f"Erro ao gerar resposta OpenAI: {str(e)} - usando modo demo")
            return self._generate_demo_response(user_message, context)
    
    def _build_messages(
        self, 
        user_message: str, 
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """
        Constrói a lista de mensagens para enviar à API.
        
        Args:
            user_message: Mensagem atual do usuário
            context: Contexto adicional
            conversation_history: Histórico da conversa
            
        Returns:
            Lista de mensagens formatadas
        """
        messages = []
        
        # Sistema prompt
        system_prompt = self._get_system_prompt(context)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Adicionar histórico da conversa (limitado)
        if conversation_history:
            # Limitar histórico para evitar excesso de tokens
            recent_history = conversation_history[-10:]  # Últimas 10 mensagens
            for msg in recent_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Adicionar mensagem atual do usuário
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _get_system_prompt(self, context: Optional[str] = None) -> str:
        """
        Gera o prompt do sistema para o chatbot de segurança.
        
        Args:
            context: Contexto adicional para incluir no prompt
            
        Returns:
            Prompt do sistema
        """
        base_prompt = """
Você é o SecuriBot, um assistente especializado em segurança cibernética e vulnerabilidades CVE.

Suas responsabilidades:
1. Fornecer informações precisas sobre vulnerabilidades CVE
2. Explicar conceitos de segurança de forma clara
3. Sugerir medidas de mitigação e correção
4. Analisar riscos e impactos de vulnerabilidades
5. Responder em português brasileiro

Diretrizes:
- Seja preciso e técnico, mas acessível
- Sempre cite fontes quando possível
- Priorize a segurança nas recomendações
- Se não souber algo, admita e sugira onde buscar informações
- Mantenha um tom profissional e útil
"""
        
        if context:
            base_prompt += f"\n\nContexto adicional:\n{context}"
        
        return base_prompt
    
    def generate_cve_summary(self, cve_data: Dict[str, Any]) -> str:
        """
        Gera um resumo detalhado de uma CVE usando IA.
        
        Args:
            cve_data: Dados da CVE do banco de dados
            
        Returns:
            Resumo gerado pela IA
        """
        try:
            # Formatar dados da CVE para o prompt
            cve_context = self._format_cve_data(cve_data)
            
            prompt = f"""
Analise a seguinte vulnerabilidade CVE e forneça um resumo detalhado:

{cve_context}

Por favor, forneça:
1. Resumo da vulnerabilidade
2. Impacto potencial
3. Sistemas/produtos afetados
4. Recomendações de mitigação
5. Prioridade de correção
"""
            
            return self.generate_chat_response(prompt)
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo CVE: {str(e)}")
            return "Erro ao gerar resumo da vulnerabilidade."
    
    def _format_cve_data(self, cve_data: Dict[str, Any]) -> str:
        """
        Formata dados da CVE para uso em prompts.
        
        Args:
            cve_data: Dados da CVE
            
        Returns:
            String formatada com os dados
        """
        formatted = f"""
CVE ID: {cve_data.get('cve_id', 'N/A')}
Descrição: {cve_data.get('description', 'N/A')}
Severidade: {cve_data.get('base_severity', 'N/A')}
CVSS Score: {cve_data.get('cvss_score', 'N/A')}
Data de Publicação: {cve_data.get('published_date', 'N/A')}
Patch Disponível: {'Sim' if cve_data.get('patch_available') else 'Não'}
"""
        
        return formatted
    
    def _generate_demo_response(self, user_message: str, context: Optional[str] = None) -> str:
        """
        Gera uma resposta de demonstração quando a API da OpenAI não está disponível.
        
        Args:
            user_message: Mensagem do usuário
            context: Contexto adicional (dados CVE, etc.)
            
        Returns:
            Resposta simulada baseada na mensagem do usuário
        """
        # Respostas baseadas em palavras-chave
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ['cve', 'vulnerabilidade', 'vulnerability', 'segurança', 'security']):
            if context:
                return f"Com base nos dados de vulnerabilidades disponíveis, posso ajudar com informações sobre segurança. Contexto encontrado: {context[:200]}..."
            else:
                return "Sou um assistente especializado em vulnerabilidades de segurança. Posso ajudar com informações sobre CVEs, análise de riscos e recomendações de segurança. Como posso ajudar?"
        
        elif any(word in user_lower for word in ['olá', 'oi', 'hello', 'hi']):
            return "Olá! Sou o assistente de segurança do Open Monitor. Posso ajudar com informações sobre vulnerabilidades, CVEs e análise de riscos. O que você gostaria de saber?"
        
        elif any(word in user_lower for word in ['ajuda', 'help']):
            return "Posso ajudar com:\n- Informações sobre vulnerabilidades (CVEs)\n- Análise de riscos de segurança\n- Recomendações de patches\n- Consultas sobre produtos e fornecedores\n\nO que você gostaria de saber?"
        
        else:
            return f"Entendi sua pergunta sobre '{user_message}'. Como assistente de segurança, posso fornecer informações sobre vulnerabilidades e riscos. Para uma resposta mais precisa, uma chave válida da API OpenAI seria necessária. Como posso ajudar com questões de segurança?"
    
    def check_api_health(self) -> bool:
        """
        Verifica se a API da OpenAI está acessível.
        
        Returns:
            True se a API estiver funcionando, False caso contrário
        """
        if not self.client:
            logger.warning("OpenAI client não inicializado")
            return False
            
        try:
            # Fazer uma chamada simples para testar a API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"API OpenAI não está acessível: {str(e)}")
            return False
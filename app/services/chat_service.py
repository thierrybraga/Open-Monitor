# services/chat_service.py

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from flask import current_app
from openai import OpenAI

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage, MessageType
from app.extensions import db

logger = logging.getLogger(__name__)


class ChatService:
    """
    Serviço para gerenciar conversas de chat com integração OpenAI.
    """
    
    def __init__(self):
        """Inicializa o serviço de chat."""
        self.client = None
        self.api_key = None
        self.model = None
        self.max_tokens = None
        self.temperature = None
        self.demo_mode = False
        
    def _initialize_openai(self):
        """Inicializa o cliente OpenAI dentro do contexto da aplicação."""
        if self.client is not None:
            return
            
        try:
            self.api_key = current_app.config.get('OPENAI_API_KEY')
            self.model = current_app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')
            self.max_tokens = current_app.config.get('OPENAI_MAX_TOKENS', 1000)
            self.temperature = current_app.config.get('OPENAI_TEMPERATURE', 0.7)
            
            if not self.api_key:
                logger.warning("OPENAI_API_KEY não configurada - modo demo ativo")
                self.demo_mode = True
                return
                
            self.client = OpenAI(api_key=self.api_key)
            logger.info("Cliente OpenAI inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente OpenAI: {e}")
            self.demo_mode = True
    
    def get_system_prompt(self) -> str:
        """Retorna o prompt do sistema para o assistente."""
        return """Você é um assistente de IA especializado em monitoramento de segurança e vulnerabilidades para o sistema Open Monitor.

Suas responsabilidades incluem:
- Ajudar usuários com questões sobre monitoramento de segurança
- Explicar vulnerabilidades e suas implicações
- Fornecer orientações sobre melhores práticas de segurança
- Auxiliar na interpretação de relatórios e alertas
- Responder perguntas sobre o sistema Open Monitor

Mantenha suas respostas:
- Claras e objetivas
- Tecnicamente precisas
- Focadas em segurança
- Úteis e práticas
- Em português brasileiro

Se não souber algo específico, seja honesto e sugira onde o usuário pode encontrar mais informações."""

    def build_conversation_history(self, session_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """
        Constrói o histórico da conversa para enviar à OpenAI.
        
        Args:
            session_id: ID da sessão de chat
            limit: Número máximo de mensagens a incluir
            
        Returns:
            Lista de mensagens formatadas para a OpenAI
        """
        try:
            # Buscar mensagens recentes da sessão
            messages = ChatMessage.query.filter_by(
                session_id=session_id,
                is_deleted=False
            ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
            
            # Reverter para ordem cronológica
            messages.reverse()
            
            # Construir histórico
            conversation = [{"role": "system", "content": self.get_system_prompt()}]
            
            for message in messages:
                if message.message_type == MessageType.USER:
                    conversation.append({"role": "user", "content": message.content})
                elif message.message_type == MessageType.ASSISTANT:
                    conversation.append({"role": "assistant", "content": message.content})
            
            return conversation
            
        except Exception as e:
            logger.error(f"Erro ao construir histórico da conversa: {e}")
            return [{"role": "system", "content": self.get_system_prompt()}]
    
    def generate_response(self, user_message: str, session_id: int) -> Dict[str, Any]:
        """
        Gera uma resposta usando a OpenAI.
        
        Args:
            user_message: Mensagem do usuário
            session_id: ID da sessão de chat
            
        Returns:
            Dicionário com a resposta e metadados
        """
        start_time = time.time()
        
        try:
            self._initialize_openai()
            
            if self.demo_mode:
                return self._generate_demo_response(user_message)
            
            # Construir histórico da conversa
            conversation = self.build_conversation_history(session_id)
            
            # Adicionar mensagem atual do usuário
            conversation.append({"role": "user", "content": user_message})
            
            # Fazer requisição à OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=conversation,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False
            )
            
            # Extrair resposta
            assistant_message = response.choices[0].message.content
            processing_time = time.time() - start_time
            
            # Calcular tokens (aproximação)
            total_tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
            
            logger.info(f"Resposta gerada com sucesso em {processing_time:.2f}s usando {total_tokens} tokens")
            
            return {
                'success': True,
                'content': assistant_message,
                'processing_time': processing_time,
                'token_count': len(assistant_message.split()),
                'total_tokens_used': total_tokens,
                'model_used': self.model
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Erro ao gerar resposta: {e}")
            
            return {
                'success': False,
                'content': self._get_error_response(str(e)),
                'processing_time': processing_time,
                'token_count': 0,
                'error': str(e)
            }
    
    def _generate_demo_response(self, user_message: str) -> Dict[str, Any]:
        """Gera uma resposta de demonstração quando a API não está disponível."""
        demo_responses = [
            "Obrigado pela sua mensagem! Este é o assistente de IA do Open Monitor. Como posso ajudá-lo com questões de segurança e monitoramento?",
            "Entendo sua pergunta sobre segurança. O Open Monitor oferece várias funcionalidades para monitoramento de vulnerabilidades. Você gostaria de saber mais sobre alguma específica?",
            "Essa é uma excelente pergunta sobre monitoramento. Para fornecer uma resposta mais detalhada, recomendo configurar a integração com a OpenAI nas configurações do sistema.",
            "Como assistente do Open Monitor, posso ajudá-lo com questões sobre vulnerabilidades, relatórios de segurança e melhores práticas. O que você gostaria de saber?",
            "Sua pergunta é muito relevante para segurança de sistemas. O Open Monitor pode ajudar a identificar e monitorar vulnerabilidades. Precisa de orientação sobre algum aspecto específico?"
        ]
        
        # Selecionar resposta baseada no hash da mensagem para consistência
        response_index = hash(user_message.lower()) % len(demo_responses)
        demo_content = demo_responses[response_index]
        
        return {
            'success': True,
            'content': demo_content,
            'processing_time': 0.5,
            'token_count': len(demo_content.split()),
            'demo_mode': True
        }
    
    def _get_error_response(self, error_message: str) -> str:
        """Retorna uma resposta amigável para erros."""
        return f"""Desculpe, ocorreu um erro ao processar sua mensagem. 

**Erro técnico:** {error_message}

**Sugestões:**
- Verifique se a chave da API OpenAI está configurada corretamente
- Tente novamente em alguns instantes
- Entre em contato com o administrador do sistema se o problema persistir

Enquanto isso, posso ajudá-lo com informações gerais sobre o Open Monitor."""

    def save_user_message(self, content: str, session_id: int, user_id: int, metadata: Optional[Any] = None) -> ChatMessage:
        """
        Salva a mensagem do usuário no banco de dados.
        
        Args:
            content: Conteúdo da mensagem
            session_id: ID da sessão
            user_id: ID do usuário
            metadata: Metadados adicionais da mensagem (ex: anexos)
            
        Returns:
            Objeto ChatMessage criado
        """
        try:
            # Serializar metadados de forma segura
            metadata_str = None
            if metadata is not None:
                try:
                    # Se for dict/list, converter para string
                    if isinstance(metadata, (dict, list)):
                        metadata_str = str(metadata)
                    elif isinstance(metadata, str):
                        metadata_str = metadata
                    else:
                        metadata_str = str(metadata)
                except Exception:
                    metadata_str = None

            user_message = ChatMessage(
                content=content,
                message_type=MessageType.USER,
                session_id=session_id,
                user_id=user_id,
                token_count=len(content.split()),
                processing_time=0.0,
                message_metadata=metadata_str
            )
            
            db.session.add(user_message)
            db.session.flush()  # Para obter o ID
            
            return user_message
            
        except Exception as e:
            logger.error(f"Erro ao salvar mensagem do usuário: {e}")
            raise
    
    def save_assistant_message(self, response_data: Dict[str, Any], session_id: int, user_id: int) -> ChatMessage:
        """
        Salva a resposta do assistente no banco de dados.
        
        Args:
            response_data: Dados da resposta gerada
            session_id: ID da sessão
            user_id: ID do usuário
            
        Returns:
            Objeto ChatMessage criado
        """
        try:
            assistant_message = ChatMessage(
                content=response_data['content'],
                message_type=MessageType.ASSISTANT,
                session_id=session_id,
                user_id=user_id,
                token_count=response_data.get('token_count', 0),
                processing_time=response_data.get('processing_time', 0.0)
            )
            
            db.session.add(assistant_message)
            db.session.flush()  # Para obter o ID
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Erro ao salvar mensagem do assistente: {e}")
            raise
    
    def update_session_activity(self, session_id: int):
        """
        Atualiza a última atividade da sessão.
        
        Args:
            session_id: ID da sessão
        """
        try:
            session = ChatSession.query.get(session_id)
            if session:
                session.last_activity = datetime.utcnow()
                session.updated_at = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Erro ao atualizar atividade da sessão: {e}")
    
    def process_message(self, content: str, session_id: int, user_id: int, metadata: Optional[Any] = None) -> Dict[str, Any]:
        """
        Processa uma mensagem completa: salva mensagem do usuário com metadados, gera resposta e salva resposta.
        
        Args:
            content: Conteúdo da mensagem do usuário
            session_id: ID da sessão
            user_id: ID do usuário
            metadata: Metadados adicionais da mensagem (ex: anexos)
            
        Returns:
            Dicionário com as mensagens criadas e metadados
        """
        try:
            # Salvar mensagem do usuário (com metadados)
            user_message = self.save_user_message(content, session_id, user_id, metadata)
            
            # Gerar resposta do assistente
            response_data = self.generate_response(content, session_id)
            
            # Salvar resposta do assistente
            assistant_message = self.save_assistant_message(response_data, session_id, user_id)
            
            # Atualizar atividade da sessão
            self.update_session_activity(session_id)
            
            # Commit das alterações
            db.session.commit()
            
            return {
                'success': True,
                'user_message': user_message.to_dict(),
                'assistant_message': assistant_message.to_dict(),
                'processing_time': response_data.get('processing_time', 0.0),
                'demo_mode': response_data.get('demo_mode', False)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao processar mensagem: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'message': 'Erro ao processar mensagem'
            }
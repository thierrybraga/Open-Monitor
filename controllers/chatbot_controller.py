import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, session, render_template
from extensions.db import db
from models.chat import ChatSession, ChatMessage, ChatMessageSchema, ChatSessionSchema
from services.rag_service import RAGService
from services.openai_service import OpenAIService
from sqlalchemy.exc import SQLAlchemyError
import time

logger = logging.getLogger(__name__)

# Blueprint para rotas do chatbot
chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

class ChatbotController:
    """
    Controlador para funcionalidades do chatbot.
    
    Gerencia sessões de chat, processamento de mensagens e
    integração com serviços de IA e RAG.
    """
    
    def __init__(self):
        self.rag_service = RAGService()
        self.openai_service = None
        
    def _get_openai_service(self):
        """Obtém instância do serviço OpenAI (lazy loading)."""
        if self.openai_service is None:
            try:
                self.openai_service = OpenAIService()
            except Exception as e:
                logger.error(f"Erro ao inicializar OpenAI Service: {str(e)}")
                raise
        return self.openai_service
    
    def _get_or_create_session(self, session_id=None):
        """
        Obtém sessão existente ou cria uma nova.
        
        Args:
            session_id: ID da sessão (opcional)
            
        Returns:
            Objeto ChatSession
        """
        try:
            if session_id:
                chat_session = ChatSession.query.filter_by(
                    session_id=session_id, 
                    is_active=True
                ).first()
                
                if chat_session:
                    return chat_session
            
            # Criar nova sessão
            chat_session = ChatSession(
                user_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            
            db.session.add(chat_session)
            db.session.commit()
            
            logger.info(f"Nova sessão de chat criada: {chat_session.session_id}")
            return chat_session
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro ao criar/obter sessão: {str(e)}")
            raise
    
    def _save_message(self, chat_session, message_type, content, **kwargs):
        """
        Salva uma mensagem no banco de dados.
        
        Args:
            chat_session: Sessão do chat
            message_type: Tipo da mensagem ('user' ou 'assistant')
            content: Conteúdo da mensagem
            **kwargs: Metadados adicionais
            
        Returns:
            Objeto ChatMessage criado
        """
        try:
            if message_type == 'user':
                message = ChatMessage.create_user_message(
                    session_id=chat_session.id,
                    content=content
                )
            else:
                message = ChatMessage.create_assistant_message(
                    session_id=chat_session.id,
                    content=content,
                    **kwargs
                )
            
            db.session.add(message)
            db.session.commit()
            
            return message
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro ao salvar mensagem: {str(e)}")
            raise
    
    def _get_conversation_history(self, chat_session, limit=10):
        """
        Obtém histórico da conversa.
        
        Args:
            chat_session: Sessão do chat
            limit: Número máximo de mensagens
            
        Returns:
            Lista de mensagens formatadas
        """
        try:
            messages = ChatMessage.query.filter_by(
                session_id=chat_session.id
            ).order_by(
                ChatMessage.created_at.desc()
            ).limit(limit).all()
            
            # Reverter ordem para cronológica
            messages.reverse()
            
            # Formatar para OpenAI
            formatted_messages = []
            for msg in messages:
                role = "user" if msg.message_type == "user" else "assistant"
                formatted_messages.append({
                    "role": role,
                    "content": msg.content
                })
            
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Erro ao obter histórico: {str(e)}")
            return []

# Instância global do controlador
chatbot_controller = ChatbotController()

@chatbot_bp.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint principal para chat com o bot.
    
    Recebe mensagem do usuário e retorna resposta do chatbot.
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Mensagem é obrigatória',
                'success': False
            }), 400
        
        user_message = data['message'].strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({
                'error': 'Mensagem não pode estar vazia',
                'success': False
            }), 400
        
        # Obter ou criar sessão
        chat_session = chatbot_controller._get_or_create_session(session_id)
        
        # Salvar mensagem do usuário
        chatbot_controller._save_message(
            chat_session, 
            'user', 
            user_message
        )
        
        # Obter histórico da conversa
        conversation_history = chatbot_controller._get_conversation_history(
            chat_session
        )
        
        # Processar mensagem com RAG
        start_time = time.time()
        
        rag_response = chatbot_controller.rag_service.search_and_generate_response(
            user_message,
            conversation_history
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Preparar resposta
        bot_response = rag_response['response']
        relevant_cves = rag_response.get('relevant_cves', [])
        context_used = rag_response.get('context_used', False)
        
        # Salvar resposta do bot
        cve_references = None
        if relevant_cves:
            cve_references = json.dumps([
                cve['cve_id'] for cve in relevant_cves[:5]
            ])
        
        chatbot_controller._save_message(
            chat_session,
            'assistant',
            bot_response,
            processing_time=processing_time,
            context_used=context_used,
            cve_references=cve_references
        )
        
        return jsonify({
            'success': True,
            'response': bot_response,
            'session_id': chat_session.session_id,
            'relevant_cves': relevant_cves[:3],  # Limitar CVEs na resposta
            'context_used': context_used,
            'processing_time': processing_time
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint de chat: {str(e)}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@chatbot_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """
    Obtém informações de uma sessão específica.
    """
    try:
        chat_session = ChatSession.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not chat_session:
            return jsonify({
                'error': 'Sessão não encontrada',
                'success': False
            }), 404
        
        # Obter mensagens da sessão
        messages = ChatMessage.query.filter_by(
            session_id=chat_session.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        session_schema = ChatSessionSchema()
        message_schema = ChatMessageSchema(many=True)
        
        return jsonify({
            'success': True,
            'session': session_schema.dump(chat_session),
            'messages': message_schema.dump(messages)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter sessão: {str(e)}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@chatbot_bp.route('/session/<session_id>/clear', methods=['POST'])
def clear_session(session_id):
    """
    Limpa uma sessão de chat (marca como inativa).
    """
    try:
        chat_session = ChatSession.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not chat_session:
            return jsonify({
                'error': 'Sessão não encontrada',
                'success': False
            }), 404
        
        chat_session.is_active = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Sessão limpa com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro ao limpar sessão: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@chatbot_bp.route('/cve/<cve_id>', methods=['GET'])
def get_cve_details(cve_id):
    """
    Obtém detalhes específicos de uma CVE.
    """
    try:
        cve_details = chatbot_controller.rag_service.get_cve_details(cve_id)
        
        if not cve_details:
            return jsonify({
                'error': 'CVE não encontrada',
                'success': False
            }), 404
        
        return jsonify({
            'success': True,
            'cve': cve_details
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter CVE {cve_id}: {str(e)}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@chatbot_bp.route('/trending', methods=['GET'])
def get_trending_vulnerabilities():
    """
    Obtém vulnerabilidades em tendência.
    """
    try:
        days = request.args.get('days', 30, type=int)
        
        trending = chatbot_controller.rag_service.get_trending_vulnerabilities(days)
        
        return jsonify({
            'success': True,
            'trending_vulnerabilities': trending,
            'period_days': days
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter vulnerabilidades em tendência: {str(e)}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@chatbot_bp.route('/health', methods=['GET'])
def health_check():
    """
    Verifica a saúde dos serviços do chatbot.
    """
    try:
        health_status = {
            'database': True,
            'openai_api': False,
            'rag_service': True
        }
        
        # Testar conexão com banco
        try:
            db.session.execute('SELECT 1')
        except Exception:
            health_status['database'] = False
        
        # Testar API OpenAI
        try:
            openai_service = chatbot_controller._get_openai_service()
            health_status['openai_api'] = openai_service.check_api_health()
        except Exception:
            health_status['openai_api'] = False
        
        overall_health = all(health_status.values())
        
        return jsonify({
            'success': True,
            'healthy': overall_health,
            'services': health_status
        }), 200 if overall_health else 503
        
    except Exception as e:
        logger.error(f"Erro no health check: {str(e)}")
        return jsonify({
            'success': False,
            'healthy': False,
            'error': 'Erro no health check'
        }), 500

# Registrar blueprint
def register_chatbot_routes(app):
    """
    Registra as rotas do chatbot na aplicação.
    
    Args:
        app: Instância da aplicação Flask
    """
    app.register_blueprint(chatbot_bp)
    logger.info("Rotas do chatbot registradas")
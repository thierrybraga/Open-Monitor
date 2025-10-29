"""
Chat Controller - Gerencia sessões de chat e mensagens
"""

from flask import Blueprint, request, jsonify, session, current_app
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import uuid
import json

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage, MessageType
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.session_cleanup_service import SessionCleanupService
from app.extensions import db
from app.utils.logging_config import get_request_logger

# Criar blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')
logger = get_request_logger()

# Instância do serviço de chat
chat_service = ChatService()


@chat_bp.route('/sessions', methods=['GET'])
def get_user_sessions():
    """Obter todas as sessões de chat do usuário atual"""
    try:
        # Para demo sem login, usar sessão temporária
        user_id = session.get('temp_user_id', 1)
        
        sessions = ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True,
            is_archived=False
        ).order_by(ChatSession.last_activity.desc()).all()
        
        return jsonify({
            'success': True,
            'sessions': [session.to_dict() for session in sessions]
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar sessões: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@chat_bp.route('/sessions', methods=['POST'])
def create_session():
    """Criar nova sessão de chat"""
    try:
        data = request.get_json()
        title = data.get('title', 'Nova Conversa')
        
        # Para demo sem login, usar sessão temporária
        user_id = session.get('temp_user_id', 1)
        if 'temp_user_id' not in session:
            session['temp_user_id'] = 1
        
        # Gerar token único para a sessão
        session_token = str(uuid.uuid4())
        
        # Criar nova sessão
        new_session = ChatSession(
            title=title,
            session_token=session_token,
            user_id=user_id,
            is_active=True,
            last_activity=datetime.utcnow()
        )
        
        db.session.add(new_session)
        db.session.commit()
        
        logger.info(f"Nova sessão criada: {new_session.id} para usuário {user_id}")
        
        return jsonify({
            'success': True,
            'session': new_session.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar sessão: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao criar sessão'
        }), 500


@chat_bp.route('/sessions/<int:session_id>', methods=['GET'])
def get_session(session_id):
    """Obter detalhes de uma sessão específica"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
        
        return jsonify({
            'success': True,
            'session': chat_session.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@chat_bp.route('/sessions/<int:session_id>', methods=['PUT'])
def update_session(session_id):
    """Atualizar sessão de chat (título, contexto, etc.)"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
        
        data = request.get_json()
        
        if 'title' in data:
            chat_session.title = data['title']
        
        if 'context_data' in data:
            chat_session.context_data = json.dumps(data['context_data'])
        
        if 'is_active' in data:
            chat_session.is_active = data['is_active']
        
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session': chat_session.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao atualizar sessão'
        }), 500


@chat_bp.route('/sessions/<int:session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """Obter mensagens de uma sessão"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        # Verificar se a sessão existe e pertence ao usuário
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
        
        # Buscar mensagens da sessão
        messages = ChatMessage.query.filter_by(
            session_id=session_id,
            is_deleted=False
        ).order_by(ChatMessage.created_at.asc()).all()
        
        return jsonify({
            'success': True,
            'messages': [message.to_dict() for message in messages]
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar mensagens da sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@chat_bp.route('/sessions/<int:session_id>/messages', methods=['POST'])
def send_message(session_id):
    """Enviar nova mensagem para uma sessão com integração OpenAI"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        # Verificar se a sessão existe e pertence ao usuário
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
        
        data = request.get_json()
        content = data.get('content', '').strip()
        metadata = data.get('metadata')
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'Conteúdo da mensagem é obrigatório'
            }), 400
        
        # Validar tamanho da mensagem
        if len(content) > 4000:
            return jsonify({
                'success': False,
                'error': 'Mensagem muito longa. Máximo de 4000 caracteres.'
            }), 400
        
        # Processar mensagem usando o serviço de chat
        result = chat_service.process_message(content, session_id, user_id, metadata)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result.get('message', 'Erro ao processar mensagem')
            }), 500
        
        response_data = {
            'success': True,
            'user_message': result['user_message'],
            'assistant_message': result['assistant_message'],
            'processing_time': result.get('processing_time', 0.0)
        }
        
        # Adicionar informação sobre modo demo se aplicável
        if result.get('demo_mode'):
            response_data['demo_mode'] = True
            response_data['message'] = 'Resposta gerada em modo demonstração. Configure a API OpenAI para respostas completas.'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@chat_bp.route('/messages/<int:message_id>', methods=['PUT'])
def edit_message(message_id):
    """Editar uma mensagem existente"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        message = ChatMessage.query.filter_by(
            id=message_id,
            user_id=user_id,
            is_deleted=False
        ).first()
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Mensagem não encontrada'
            }), 404
        
        # Apenas mensagens do usuário podem ser editadas
        if message.message_type != MessageType.USER:
            return jsonify({
                'success': False,
                'error': 'Apenas mensagens do usuário podem ser editadas'
            }), 403
        
        data = request.get_json()
        new_content = data.get('content', '').strip()
        
        if not new_content:
            return jsonify({
                'success': False,
                'error': 'Conteúdo da mensagem é obrigatório'
            }), 400
        
        # Atualizar mensagem
        message.content = new_content
        message.token_count = len(new_content.split())
        message.mark_as_edited()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao editar mensagem {message_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao editar mensagem'
        }), 500


@chat_bp.route('/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    """Deletar uma mensagem"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        message = ChatMessage.query.filter_by(
            id=message_id,
            user_id=user_id,
            is_deleted=False
        ).first()
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Mensagem não encontrada'
            }), 404
        
        # Soft delete
        message.soft_delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Mensagem deletada com sucesso'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar mensagem {message_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao deletar mensagem'
        }), 500


@chat_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Excluir uma sessão específica"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada'
            }), 404
        
        # Soft delete - marcar como inativa
        chat_session.is_active = False
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Sessão {session_id} excluída pelo usuário {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sessão excluída com sucesso'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao excluir sessão'
        }), 500


@chat_bp.route('/sessions/<int:session_id>/archive', methods=['POST'])
def archive_session(session_id):
    """Arquivar uma sessão específica"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada ou já inativa'
            }), 404
        
        # Arquivar a sessão
        chat_session.archive()
        db.session.commit()
        
        logger.info(f"Sessão {session_id} arquivada pelo usuário {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sessão arquivada com sucesso'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao arquivar sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao arquivar sessão'
        }), 500


@chat_bp.route('/sessions/<int:session_id>/unarchive', methods=['POST'])
def unarchive_session(session_id):
    """Desarquivar uma sessão específica"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Sessão não encontrada ou inativa'
            }), 404
        
        # Desarquivar a sessão
        chat_session.unarchive()
        db.session.commit()
        
        logger.info(f"Sessão {session_id} desarquivada pelo usuário {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sessão desarquivada com sucesso'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao desarquivar sessão {session_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao desarquivar sessão'
        }), 500


@chat_bp.route('/sessions/bulk-delete', methods=['POST'])
def bulk_delete_sessions():
    """Excluir múltiplas sessões"""
    try:
        user_id = session.get('temp_user_id', 1)
        data = request.get_json()
        session_ids = data.get('session_ids', [])
        
        if not session_ids:
            return jsonify({
                'success': False,
                'error': 'Lista de sessões não fornecida'
            }), 400
        
        # Verificar se todas as sessões pertencem ao usuário
        sessions = ChatSession.query.filter(
            ChatSession.id.in_(session_ids),
            ChatSession.user_id == user_id,
            ChatSession.is_active == True
        ).all()
        
        if len(sessions) != len(session_ids):
            return jsonify({
                'success': False,
                'error': 'Algumas sessões não foram encontradas ou não pertencem ao usuário'
            }), 404
        
        # Soft delete - marcar todas como inativas
        deleted_count = 0
        for chat_session in sessions:
            chat_session.is_active = False
            chat_session.updated_at = datetime.utcnow()
            deleted_count += 1
        
        db.session.commit()
        
        logger.info(f"{deleted_count} sessões excluídas pelo usuário {user_id}")
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} sessões excluídas com sucesso',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir sessões em lote: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao excluir sessões'
        }), 500


@chat_bp.route('/sessions/cleanup', methods=['POST'])
def cleanup_old_sessions():
    """Limpar sessões antigas baseado em critérios usando o SessionCleanupService"""
    try:
        user_id = session.get('temp_user_id', 1)
        data = request.get_json()
        
        # Critérios de limpeza
        days_old = data.get('days_old', 30)  # Padrão: 30 dias
        keep_recent = data.get('keep_recent', 10)  # Manter as 10 mais recentes
        dry_run = data.get('dry_run', False)  # Simulação
        
        # Criar instância do serviço de limpeza
        cleanup_service = SessionCleanupService()
        
        # Executar limpeza
        result = cleanup_service.cleanup_old_sessions(
            days_old=days_old,
            keep_recent=keep_recent,
            user_id=user_id,
            dry_run=dry_run
        )
        
        if result['success']:
            stats = result['stats']
            message = f"{stats['deleted_count']} sessões antigas excluídas"
            if dry_run:
                message = f"Simulação: {stats['deleted_count']} sessões seriam excluídas"
            
            logger.info(f"Limpeza automática para usuário {user_id}: {message}")
            
            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': stats['deleted_count'],
                'stats': stats,
                'criteria': {
                    'days_old': days_old,
                    'keep_recent': keep_recent,
                    'dry_run': dry_run
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro na limpeza de sessões')
            }), 500
        
    except Exception as e:
        logger.error(f"Erro na limpeza de sessões antigas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro na limpeza de sessões antigas'
        }), 500


@chat_bp.route('/sessions/stats', methods=['GET'])
def get_session_stats():
    """Obter estatísticas das sessões do usuário"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        # Contar sessões ativas
        active_sessions = ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True
        ).count()
        
        # Contar sessões inativas (excluídas)
        inactive_sessions = ChatSession.query.filter_by(
            user_id=user_id,
            is_active=False
        ).count()
        
        # Sessões por período
        from datetime import timedelta
        now = datetime.utcnow()
        
        last_7_days = ChatSession.query.filter(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
            ChatSession.last_activity >= now - timedelta(days=7)
        ).count()
        
        last_30_days = ChatSession.query.filter(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
            ChatSession.last_activity >= now - timedelta(days=30)
        ).count()
        
        # Sessão mais antiga ativa
        oldest_session = ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(ChatSession.created_at.asc()).first()
        
        return jsonify({
            'success': True,
            'stats': {
                'active_sessions': active_sessions,
                'inactive_sessions': inactive_sessions,
                'total_sessions': active_sessions + inactive_sessions,
                'last_7_days': last_7_days,
                'last_30_days': last_30_days,
                'oldest_active_session': oldest_session.created_at.isoformat() if oldest_session else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de sessões: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao obter estatísticas'
        }), 500


@chat_bp.route('/sessions/cleanup-stats', methods=['GET'])
def get_cleanup_stats():
    """Obter estatísticas detalhadas para limpeza de sessões"""
    try:
        user_id = session.get('temp_user_id', 1)
        
        # Criar instância e obter estatísticas
        cleanup_service = SessionCleanupService()
        stats = cleanup_service.get_cleanup_stats(user_id=user_id)
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de limpeza: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao obter estatísticas de limpeza'
        }), 500


@chat_bp.route('/health', methods=['GET'])
def health_check():
    """Verificação de saúde da API de chat"""
    return jsonify({
        'success': True,
        'message': 'Chat API está funcionando',
        'timestamp': datetime.utcnow().isoformat()
    }), 200



# Registrar handlers de erro
@chat_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado'
    }), 404


@chat_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor'
    }), 500
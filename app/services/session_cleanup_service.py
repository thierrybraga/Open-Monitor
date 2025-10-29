"""
Serviço de Limpeza Automática de Sessões
Responsável por limpar sessões antigas automaticamente
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import and_, desc
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.extensions import db

logger = logging.getLogger(__name__)

class SessionCleanupService:
    """Serviço para limpeza automática de sessões antigas"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def cleanup_old_sessions(
        self, 
        days_old: int = 30, 
        keep_recent: int = 10,
        user_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Limpa sessões antigas baseado nos critérios especificados
        
        Args:
            days_old: Número de dias para considerar uma sessão como antiga
            keep_recent: Número de sessões recentes para manter sempre
            user_id: ID do usuário (None para todos os usuários)
            dry_run: Se True, apenas simula a limpeza sem executar
            
        Returns:
            Dict com estatísticas da limpeza
        """
        try:
            self.logger.info(f"Iniciando limpeza de sessões - days_old: {days_old}, keep_recent: {keep_recent}")
            
            # Data limite para considerar sessões antigas
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Construir query base
            query = ChatSession.query.filter(ChatSession.is_active == True)
            
            if user_id:
                query = query.filter(ChatSession.user_id == user_id)
            
            # Buscar todas as sessões ativas
            all_sessions = query.order_by(desc(ChatSession.last_activity)).all()
            
            # Separar sessões por usuário para manter as mais recentes de cada um
            sessions_by_user = {}
            for session in all_sessions:
                uid = session.user_id
                if uid not in sessions_by_user:
                    sessions_by_user[uid] = []
                sessions_by_user[uid].append(session)
            
            sessions_to_delete = []
            stats = {
                'total_sessions': len(all_sessions),
                'sessions_by_user': len(sessions_by_user),
                'deleted_count': 0,
                'kept_recent': 0,
                'kept_by_date': 0,
                'users_affected': 0
            }
            
            # Para cada usuário, determinar quais sessões excluir
            for uid, user_sessions in sessions_by_user.items():
                user_sessions.sort(key=lambda x: x.last_activity, reverse=True)
                
                # Manter as N sessões mais recentes
                recent_sessions = user_sessions[:keep_recent]
                older_sessions = user_sessions[keep_recent:]
                
                stats['kept_recent'] += len(recent_sessions)
                
                # Das sessões mais antigas, excluir apenas as que são realmente antigas
                for session in older_sessions:
                    if session.last_activity < cutoff_date:
                        sessions_to_delete.append(session)
                    else:
                        stats['kept_by_date'] += 1
            
            stats['deleted_count'] = len(sessions_to_delete)
            stats['users_affected'] = len([uid for uid, sessions in sessions_by_user.items() 
                                         if any(s in sessions_to_delete for s in sessions)])
            
            if not dry_run and sessions_to_delete:
                # Executar a limpeza
                session_ids = [s.id for s in sessions_to_delete]
                
                # Soft delete das sessões
                ChatSession.query.filter(ChatSession.id.in_(session_ids)).update(
                    {'is_active': False, 'updated_at': datetime.utcnow()},
                    synchronize_session=False
                )
                
                # Soft delete das mensagens relacionadas
                ChatMessage.query.filter(ChatMessage.session_id.in_(session_ids)).update(
                    {'is_active': False, 'updated_at': datetime.utcnow()},
                    synchronize_session=False
                )
                
                db.session.commit()
                
                self.logger.info(f"Limpeza concluída: {stats['deleted_count']} sessões excluídas")
            
            elif dry_run:
                self.logger.info(f"Simulação de limpeza: {stats['deleted_count']} sessões seriam excluídas")
            
            return {
                'success': True,
                'stats': stats,
                'dry_run': dry_run
            }
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza de sessões: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'stats': {}
            }
    
    def get_cleanup_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas sobre sessões que podem ser limpas
        
        Args:
            user_id: ID do usuário (None para todos os usuários)
            
        Returns:
            Dict com estatísticas
        """
        try:
            query = ChatSession.query.filter(ChatSession.is_active == True)
            
            if user_id:
                query = query.filter(ChatSession.user_id == user_id)
            
            # Contar sessões por idade
            now = datetime.utcnow()
            
            stats = {
                'total_active': query.count(),
                'last_7_days': query.filter(ChatSession.last_activity >= now - timedelta(days=7)).count(),
                'last_30_days': query.filter(ChatSession.last_activity >= now - timedelta(days=30)).count(),
                'last_90_days': query.filter(ChatSession.last_activity >= now - timedelta(days=90)).count(),
                'older_than_90_days': query.filter(ChatSession.last_activity < now - timedelta(days=90)).count()
            }
            
            # Adicionar estatísticas por usuário se não filtrado
            if not user_id:
                stats['unique_users'] = db.session.query(ChatSession.user_id).filter(
                    ChatSession.is_active == True
                ).distinct().count()
            
            return {
                'success': True,
                'stats': stats
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': {}
            }
    
    def schedule_cleanup(
        self, 
        days_old: int = 30, 
        keep_recent: int = 10,
        interval_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Agenda limpeza automática (placeholder para implementação futura com scheduler)
        
        Args:
            days_old: Número de dias para considerar uma sessão como antiga
            keep_recent: Número de sessões recentes para manter
            interval_hours: Intervalo em horas entre limpezas
            
        Returns:
            Dict com informações sobre o agendamento
        """
        # TODO: Implementar com APScheduler ou similar
        return {
            'success': True,
            'message': 'Agendamento de limpeza configurado',
            'config': {
                'days_old': days_old,
                'keep_recent': keep_recent,
                'interval_hours': interval_hours
            }
        }
    
    def cleanup_inactive_sessions(self, days_inactive: int = 7) -> Dict[str, Any]:
        """
        Limpa sessões que estão inativas há muito tempo
        
        Args:
            days_inactive: Número de dias de inatividade
            
        Returns:
            Dict com resultado da limpeza
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
            
            # Buscar sessões inativas há muito tempo
            inactive_sessions = ChatSession.query.filter(
                and_(
                    ChatSession.is_active == True,
                    ChatSession.last_activity < cutoff_date
                )
            ).all()
            
            if inactive_sessions:
                session_ids = [s.id for s in inactive_sessions]
                
                # Soft delete
                ChatSession.query.filter(ChatSession.id.in_(session_ids)).update(
                    {'is_active': False, 'updated_at': datetime.utcnow()},
                    synchronize_session=False
                )
                
                ChatMessage.query.filter(ChatMessage.session_id.in_(session_ids)).update(
                    {'is_active': False, 'updated_at': datetime.utcnow()},
                    synchronize_session=False
                )
                
                db.session.commit()
                
                self.logger.info(f"Limpeza de sessões inativas: {len(inactive_sessions)} sessões excluídas")
            
            return {
                'success': True,
                'deleted_count': len(inactive_sessions),
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza de sessões inativas: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0
            }

# Instância global do serviço
session_cleanup_service = SessionCleanupService()
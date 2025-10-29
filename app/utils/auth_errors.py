# utils/auth_errors.py

import logging
from typing import Dict, Any, Optional
from flask import flash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.utils.security import log_security_event

logger = logging.getLogger(__name__)

class AuthErrorHandler:
    """Centralizador para tratamento de erros de autenticação."""
    
    # Mensagens padronizadas
    ERROR_MESSAGES = {
        'login_invalid_credentials': 'Usuário ou senha inválidos.',
        'login_account_inactive': 'Sua conta está desativada. Entre em contato com o administrador.',
        'login_rate_limit': 'Muitas tentativas de login. Tente novamente em alguns minutos.',
        'register_duplicate': 'Nome de usuário ou e-mail já existem.',
        'register_validation': 'Erro de validação: {}',
        'register_database': 'Erro interno do banco de dados durante o registro. Tente novamente.',
        'register_unexpected': 'Erro interno inesperado durante o registro. Tente novamente.',
        'register_success': 'Cadastro realizado com sucesso. Faça login.',
        'login_success': 'Bem-vindo, {}!',
        'logout_success': 'Logout realizado com sucesso.',
        'availability_error': 'Erro ao verificar disponibilidade. Tente novamente.',
        'invalid_request': 'Dados da requisição inválidos.',
        'server_error': 'Erro interno do servidor. Tente novamente.'
    }
    
    @classmethod
    def handle_login_error(cls, error_type: str, user: Optional[Any] = None, 
                          username: Optional[str] = None, **kwargs) -> None:
        """Trata erros de login de forma padronizada."""
        
        if error_type == 'invalid_credentials':
            username_for_log = user.username if user else username
            user_id_for_log = user.id if user else None
            
            log_security_event('login_failed', user_id=user_id_for_log, 
                             username=username_for_log,
                             details={'reason': 'invalid_credentials'})
            
            flash(cls.ERROR_MESSAGES['login_invalid_credentials'], 'danger')
            logger.warning(f"Login failed for username: {username}")
            
        elif error_type == 'account_inactive':
            log_security_event('login_failed', user_id=user.id, username=user.username,
                             details={'reason': 'account_inactive'})
            
            flash(cls.ERROR_MESSAGES['login_account_inactive'], 'danger')
            logger.warning(f"Login attempt for inactive account: {user.username}")
            
        elif error_type == 'rate_limit':
            flash(cls.ERROR_MESSAGES['login_rate_limit'], 'warning')
            logger.warning(f"Rate limit exceeded for login attempt from {kwargs.get('client_ip')}")
    
    @classmethod
    def handle_register_error(cls, error: Exception, username: str, 
                            db_session: Any) -> None:
        """Trata erros de registro de forma padronizada."""
        
        db_session.rollback()
        
        if isinstance(error, IntegrityError):
            log_security_event('register_failed', username=username,
                             details={'reason': 'duplicate_user_or_email'})
            
            flash(cls.ERROR_MESSAGES['register_duplicate'], 'warning')
            logger.warning(f"Registration failed for username: {username} (IntegrityError).")
            
        elif isinstance(error, ValueError):
            log_security_event('register_failed', username=username,
                             details={'reason': 'validation_error', 'error': str(error)})
            
            flash(cls.ERROR_MESSAGES['register_validation'].format(str(error)), 'danger')
            logger.warning(f"Registration validation error for {username}: {error}")
            
        elif isinstance(error, SQLAlchemyError):
            log_security_event('register_failed', username=username,
                             details={'reason': 'database_error'})
            
            flash(cls.ERROR_MESSAGES['register_database'], 'danger')
            logger.error(f"DB error during registration for user {username}: {error}", exc_info=True)
            
        else:
            log_security_event('register_failed', username=username,
                             details={'reason': 'unexpected_error'})
            
            flash(cls.ERROR_MESSAGES['register_unexpected'], 'danger')
            logger.error(f"Unexpected error during registration for user {username}: {str(error)}", exc_info=True)
    
    @classmethod
    def handle_success(cls, success_type: str, **kwargs) -> None:
        """Trata mensagens de sucesso de forma padronizada."""
        
        if success_type == 'login':
            user = kwargs.get('user')
            log_security_event('login_success', user_id=user.id, username=user.username)
            flash(cls.ERROR_MESSAGES['login_success'].format(user.username), 'success')
            logger.info(f"User {user.username} logged in successfully.")
            
        elif success_type == 'register':
            user = kwargs.get('user')
            log_security_event('register_success', user_id=user.id, username=user.username)
            flash(cls.ERROR_MESSAGES['register_success'], 'success')
            logger.info(f"New user registered: {user.username}.")
            
        elif success_type == 'logout':
            user_id = kwargs.get('user_id')
            username = kwargs.get('username')
            log_security_event('logout', user_id=user_id, username=username)
            flash(cls.ERROR_MESSAGES['logout_success'], 'success')
            logger.info("User logged out.")
    
    @classmethod
    def flash_form_errors(cls, form: Any) -> None:
        """Flasha todos os erros do formulário de maneira padronizada."""
        for field, errors in form.errors.items():
            for error in errors:
                field_label = getattr(form, field, None)
                label_text = field_label.label.text if field_label and field_label.label else field
                flash(f"{label_text}: {error}", 'danger')
                logger.warning(f"Form error on field '{field}': {error}")
    
    @classmethod
    def handle_api_error(cls, error_type: str, **kwargs) -> Dict[str, Any]:
        """Trata erros de API de forma padronizada."""
        
        if error_type == 'invalid_request':
            return {'error': cls.ERROR_MESSAGES['invalid_request']}, 400
            
        elif error_type == 'availability_check':
            field_type = kwargs.get('field_type', 'campo')
            logger.error(f"Erro ao verificar disponibilidade de {field_type}: {kwargs.get('exception')}")
            return {'error': cls.ERROR_MESSAGES['availability_error']}, 500
            
        elif error_type == 'server_error':
            return {'error': cls.ERROR_MESSAGES['server_error']}, 500
            
        else:
            return {'error': cls.ERROR_MESSAGES['server_error']}, 500

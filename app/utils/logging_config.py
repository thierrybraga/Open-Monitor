import logging
import logging.handlers
import json
import traceback
from datetime import datetime
import os
from pathlib import Path

class StructuredFormatter(logging.Formatter):
    """
    Formatter personalizado para logs estruturados em JSON.
    """
    
    def format(self, record):
        # Criar estrutura base do log
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adicionar informações de exceção se presente
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Adicionar campos extras se presentes
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'processing_time'):
            log_entry['processing_time'] = record.processing_time
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        
        return json.dumps(log_entry, ensure_ascii=False)

class AppLoggerAdapter(logging.LoggerAdapter):
    """
    Adapter para adicionar contexto específico da aplicação aos logs.
    """
    
    def process(self, msg, kwargs):
        # Adicionar informações de contexto
        extra = kwargs.get('extra', {})
        
        # Mesclar com contexto do adapter
        for key, value in self.extra.items():
            if key not in extra:
                extra[key] = value
        
        kwargs['extra'] = extra
        return msg, kwargs
    
    def log_performance(self, level, operation, processing_time, success=True, **kwargs):
        """
        Log específico para métricas de performance.
        """
        extra = kwargs.get('extra', {})
        extra.update({
            'operation': operation,
            'processing_time': processing_time,
            'success': success
        })
        
        message = f"Operation {operation} {'completed' if success else 'failed'} in {processing_time:.3f}s"
        self.log(level, message, extra=extra)
    
    def log_user_interaction(self, level, action, session_id=None, user_message_length=None, **kwargs):
        """
        Log específico para interações do usuário.
        """
        extra = kwargs.get('extra', {})
        extra.update({
            'action': action,
            'session_id': session_id,
            'user_message_length': user_message_length
        })
        
        message = f"User {action}"
        if session_id:
            message += f" (session: {session_id})"
        
        self.log(level, message, extra=extra)
    
    def log_error_with_context(self, error, operation=None, session_id=None, **kwargs):
        """
        Log de erro com contexto adicional.
        """
        extra = kwargs.get('extra', {})
        extra.update({
            'error_type': type(error).__name__,
            'operation': operation,
            'session_id': session_id
        })
        
        message = f"Error in {operation or 'unknown operation'}: {str(error)}"
        self.error(message, exc_info=True, extra=extra)

def setup_logging(app_name='chatbot', log_level='INFO', log_dir='logs'):
    """
    Configura o sistema de logging estruturado.
    
    Args:
        app_name: Nome da aplicação
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Diretório para arquivos de log
    
    Returns:
        ChatbotLoggerAdapter: Adapter configurado para logging
    """
    # Criar diretório de logs se não existir
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configurar logger principal
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remover handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Handler para arquivo (JSON estruturado)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / f'{app_name}.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)
    
    # Handler para arquivo de erros
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / f'{app_name}_errors.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    logger.addHandler(error_handler)
    
    # Handler para console (desenvolvimento)
    if os.getenv('FLASK_ENV') == 'development':
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Criar adapter com contexto base
    adapter = AppLoggerAdapter(logger, {
        'app_name': app_name,
        'version': '1.0.0'
    })
    
    return adapter

def get_request_logger(session_id=None, request_id=None):
    """
    Obtém um logger com contexto de requisição.
    
    Args:
        session_id: ID da sessão
        request_id: ID da requisição
    
    Returns:
        AppLoggerAdapter: Logger com contexto
    """
    logger = logging.getLogger('app')
    
    context = {}
    if session_id:
        context['session_id'] = session_id
    if request_id:
        context['request_id'] = request_id
    
    return AppLoggerAdapter(logger, context)

# Configuração padrão
default_logger = setup_logging()

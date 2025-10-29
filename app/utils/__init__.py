"""Utils package for Open-Monitor

Este pacote contém utilitários para logging, feedback terminal,
indicadores visuais e monitoramento de performance.
"""

# Importações principais do sistema de feedback
try:
    from app.utils.terminal_feedback import terminal_feedback, timed_operation, FeedbackType, FeedbackMessage
    from app.utils.visual_indicators import status_indicator, performance_indicator, Spinner, StatusIndicator
    from app.utils.enhanced_logging import get_app_logger, setup_logging, EnhancedLogger
    
    __all__ = [
        'terminal_feedback',
        'timed_operation', 
        'FeedbackType',
        'FeedbackMessage',
        'status_indicator',
        'performance_indicator',
        'Spinner',
        'StatusIndicator',
        'get_app_logger',
        'setup_logging',
        'EnhancedLogger'
    ]
    
except ImportError as e:
    # Em caso de erro de importação, definir uma lista vazia
    # para evitar quebrar outras partes do sistema
    __all__ = []
    print(f"Warning: Could not import some utils modules: {e}")

# Versão do pacote utils
__version__ = "1.0.0"

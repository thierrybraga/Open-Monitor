#!/usr/bin/env python3
"""
Sistema aprimorado de logging com feedback detalhado no terminal.
Fornece logging colorido, barras de progresso e feedback em tempo real.
Integrado com sistema de feedback avançado e indicadores visuais.
"""

import logging
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from enum import Enum
import threading
from contextlib import contextmanager

# Importar novos sistemas de feedback
try:
    from app.utils.terminal_feedback import terminal_feedback, FeedbackType
    from app.utils.visual_indicators import (
        spinner, SpinnerType, StatusType, 
        show_operation_status, update_operation_status, hide_operation_status,
        add_performance_metric
    )
    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False
    # Fallbacks seguros para evitar NameError quando utilitários avançados não estiverem disponíveis
    from enum import Enum as _Enum
    class SpinnerType(_Enum):
        DOTS = "DOTS"
    class StatusType(_Enum):
        RUNNING = "RUNNING"
        SUCCESS = "SUCCESS"
        ERROR = "ERROR"
    def spinner(*args, **kwargs):
        class _StubSpinner:
            def start(self):
                pass
            def update_message(self, message):
                pass
            def stop(self, message=None, status=None):
                pass
        return _StubSpinner()
    def show_operation_status(*args, **kwargs):
        pass
    def update_operation_status(*args, **kwargs):
        pass
    def hide_operation_status(*args, **kwargs):
        pass
    def add_performance_metric(*args, **kwargs):
        pass

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback para sistemas sem colorama
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''

class LogLevel(Enum):
    """Níveis de log personalizados."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    PROGRESS = "PROGRESS"

class ProgressBar:
    """
    Barra de progresso para terminal.
    """
    
    def __init__(self, total: int, description: str = "", width: int = 50):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self.start_time = time.time()
        self.last_update = 0
        self._lock = threading.Lock()
    
    def update(self, increment: int = 1, description: Optional[str] = None):
        """Atualiza a barra de progresso."""
        with self._lock:
            self.current = min(self.current + increment, self.total)
            if description:
                self.description = description
            
            # Atualizar apenas se passou tempo suficiente ou completou
            current_time = time.time()
            if current_time - self.last_update > 0.1 or self.current == self.total:
                self._render()
                self.last_update = current_time
    
    def _render(self):
        """Renderiza a barra de progresso."""
        if self.total == 0:
            percentage = 100
        else:
            percentage = (self.current / self.total) * 100
        
        filled_width = int(self.width * self.current / self.total) if self.total > 0 else 0
        bar = '█' * filled_width + '░' * (self.width - filled_width)
        
        # Calcular tempo estimado
        elapsed_time = time.time() - self.start_time
        if self.current > 0 and self.current < self.total:
            eta = (elapsed_time / self.current) * (self.total - self.current)
            eta_str = f" ETA: {self._format_time(eta)}"
        else:
            eta_str = ""
        
        # Renderizar linha
        line = f"\r{Fore.CYAN}{self.description}{Style.RESET_ALL} |{Fore.GREEN}{bar}{Style.RESET_ALL}| {percentage:6.1f}% ({self.current}/{self.total}){eta_str}"
        
        sys.stdout.write(line)
        sys.stdout.flush()
        
        if self.current == self.total:
            print()  # Nova linha quando completo
    
    def _format_time(self, seconds: float) -> str:
        """Formata tempo em formato legível."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            return f"{seconds/3600:.0f}h {(seconds%3600)/60:.0f}m"
    
    def finish(self, message: Optional[str] = None):
        """Finaliza a barra de progresso."""
        self.current = self.total
        self._render()
        if message:
            print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")

class EnhancedLogger:
    """
    Logger aprimorado com suporte a cores e feedback visual.
    """
    
    def __init__(self, name: str = "enhanced_logger", level: str = "INFO"):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        
        # Configurar handler personalizado
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(self._get_formatter())
            self.logger.addHandler(handler)
        
        # Estatísticas
        self.stats = {
            'debug': 0,
            'info': 0,
            'success': 0,
            'warning': 0,
            'error': 0,
            'critical': 0
        }
        
        # Lock para thread safety
        self._lock = threading.Lock()
        
        # Integração com sistema de feedback
        self.use_advanced_feedback = FEEDBACK_AVAILABLE
        self.active_operations = {}
        self._operation_counter = 0
    
    def _get_formatter(self) -> logging.Formatter:
        """Obtém formatter personalizado."""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _log_with_color(self, level: LogLevel, message: str, color: str = "", icon: str = ""):
        """Log com cor e ícone."""
        with self._lock:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            if COLORAMA_AVAILABLE and color:
                formatted_message = f"{color}{icon} [{timestamp}] {message}{Style.RESET_ALL}"
            else:
                formatted_message = f"{icon} [{timestamp}] {message}"
            
            print(formatted_message)
            
            # Atualizar estatísticas
            if level.value.lower() in self.stats:
                self.stats[level.value.lower()] += 1
    
    def debug(self, message: str):
        """Log de debug."""
        self._log_with_color(LogLevel.DEBUG, message, Fore.LIGHTBLACK_EX, "🔍")
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log de informação."""
        self._log_with_color(LogLevel.INFO, message, Fore.BLUE, "ℹ️")
        self.logger.info(message)
    
    def success(self, message: str):
        """Log de sucesso."""
        self._log_with_color(LogLevel.SUCCESS, message, Fore.GREEN, "✅")
        self.logger.info(f"SUCCESS: {message}")
    
    def warning(self, message: str):
        """Log de aviso."""
        self._log_with_color(LogLevel.WARNING, message, Fore.YELLOW, "⚠️")
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log de erro."""
        self._log_with_color(LogLevel.ERROR, message, Fore.RED, "❌")
        self.logger.error(message)
    
    def critical(self, message: str):
        """Log crítico."""
        self._log_with_color(LogLevel.CRITICAL, message, Fore.RED + Style.BRIGHT, "🚨")
        self.logger.critical(message)
    
    def progress(self, message: str):
        """Log de progresso."""
        self._log_with_color(LogLevel.PROGRESS, message, Fore.CYAN, "⏳")
    
    def section(self, title: str):
        """Cria uma seção visual no log."""
        separator = "=" * 60
        self._log_with_color(LogLevel.INFO, f"\n{separator}", Fore.MAGENTA)
        self._log_with_color(LogLevel.INFO, f"📋 {title.upper()}", Fore.MAGENTA + Style.BRIGHT)
        self._log_with_color(LogLevel.INFO, separator, Fore.MAGENTA)
    
    def subsection(self, title: str):
        """Cria uma subseção visual no log."""
        separator = "-" * 40
        self._log_with_color(LogLevel.INFO, f"\n{separator}", Fore.CYAN)
        self._log_with_color(LogLevel.INFO, f"📌 {title}", Fore.CYAN + Style.BRIGHT)
        self._log_with_color(LogLevel.INFO, separator, Fore.CYAN)
    
    def database_operation(self, operation: str, table: str, count: int = None):
        """Log específico para operações de banco de dados."""
        if count is not None:
            message = f"💾 {operation} - Tabela: {table} - Registros: {count}"
        else:
            message = f"💾 {operation} - Tabela: {table}"
        
        self._log_with_color(LogLevel.INFO, message, Fore.MAGENTA, "💾")
    
    def api_request(self, method: str, url: str, status_code: int = None, duration: float = None):
        """Log específico para requisições de API."""
        message = f"🌐 {method} {url}"
        
        if status_code is not None:
            message += f" - Status: {status_code}"
        
        if duration is not None:
            message += f" - Tempo: {duration:.2f}s"
        
        if status_code and status_code >= 400:
            self._log_with_color(LogLevel.ERROR, message, Fore.RED, "🌐")
        else:
            self._log_with_color(LogLevel.INFO, message, Fore.GREEN, "🌐")
    
    def performance_metric(self, metric_name: str, value: Any, unit: str = ""):
        message = f"📊 {metric_name}: {value}{unit}"
        self._log_with_color(LogLevel.INFO, message, Fore.YELLOW, "📊")
        try:
            import json
            from datetime import datetime
            payload = {
                "event": "metric",
                "metric_name": metric_name,
                "unit": unit or None,
                "logger": self.logger.name,
                "ts": datetime.utcnow().isoformat() + "Z"
            }
            if isinstance(value, dict):
                payload["fields"] = value
            else:
                payload["value"] = value
            self.logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            self.logger.info(message)
    
    def get_stats(self) -> Dict[str, int]:
        """Obtém estatísticas de logging."""
        return self.stats.copy()
    
    def print_stats(self):
        """Imprime estatísticas de logging."""
        self.subsection("Estatísticas de Log")
        for level, count in self.stats.items():
            if count > 0:
                color = {
                    'debug': Fore.LIGHTBLACK_EX,
                    'info': Fore.BLUE,
                    'success': Fore.GREEN,
                    'warning': Fore.YELLOW,
                    'error': Fore.RED,
                    'critical': Fore.RED + Style.BRIGHT
                }.get(level, Fore.WHITE)
                
                print(f"{color}  {level.upper()}: {count}{Style.RESET_ALL}")
    
    def start_operation(self, operation_name: str, show_spinner: bool = True, 
                       spinner_type: SpinnerType = SpinnerType.DOTS) -> str:
        """Inicia uma operação com feedback visual."""
        self._operation_counter += 1
        operation_id = f"{operation_name}_{self._operation_counter}"
        
        operation_data = {
            "name": operation_name,
            "start_time": time.time(),
            "spinner": None,
            "show_spinner": show_spinner
        }
        
        if self.use_advanced_feedback:
            # Usar sistema de feedback avançado
            show_operation_status(operation_id, operation_name, StatusType.RUNNING)
            
            if show_spinner:
                operation_data["spinner"] = spinner(spinner_type, f"Executando: {operation_name}")
                operation_data["spinner"].start()
        else:
            # Fallback para logging tradicional
            self.info(f"Iniciando: {operation_name}")
        
        self.active_operations[operation_id] = operation_data
        return operation_id
    
    def update_operation(self, operation_id: str, progress: Optional[float] = None, 
                        details: Optional[str] = None, message: Optional[str] = None):
        """Atualiza o progresso de uma operação."""
        if operation_id not in self.active_operations:
            return
        
        if self.use_advanced_feedback:
            update_operation_status(operation_id, progress=progress, details=details)
            
            # Atualizar spinner se existir
            operation = self.active_operations[operation_id]
            if operation.get("spinner") and message:
                operation["spinner"].update_message(message)
        else:
            # Fallback para logging tradicional
            if message:
                self.info(f"Progresso: {message}")
    
    def finish_operation(self, operation_id: str, success: bool = True, 
                        final_message: Optional[str] = None, 
                        error_message: Optional[str] = None):
        """Finaliza uma operação."""
        if operation_id not in self.active_operations:
            return
        
        operation = self.active_operations[operation_id]
        duration = time.time() - operation["start_time"]
        
        if self.use_advanced_feedback:
            # Parar spinner se existir
            if operation.get("spinner"):
                status = StatusType.SUCCESS if success else StatusType.ERROR
                message = final_message or ("Concluído" if success else "Falhou")
                operation["spinner"].stop(message, status)
            
            # Atualizar status da operação
            final_status = StatusType.SUCCESS if success else StatusType.ERROR
            hide_operation_status(operation_id, final_status)
            
            # Registrar métrica de performance
            add_performance_metric(f"operation_{operation['name']}", duration)
        else:
            # Fallback para logging tradicional
            if success:
                message = final_message or f"Operação '{operation['name']}' concluída"
                self.success(f"{message} ({duration:.2f}s)")
            else:
                message = error_message or f"Operação '{operation['name']}' falhou"
                self.error(f"{message} ({duration:.2f}s)")
        
        # Remover operação da lista ativa
        del self.active_operations[operation_id]
    
    def operation_context(self, operation_name: str, show_spinner: bool = True):
        """Context manager para operações com feedback automático."""
        @contextmanager
        def _operation_context():
            operation_id = self.start_operation(operation_name, show_spinner)
            try:
                yield operation_id
                self.finish_operation(operation_id, success=True)
            except Exception as e:
                self.finish_operation(operation_id, success=False, error_message=str(e))
                raise
        
        return _operation_context()
    
    def enhanced_progress(self, total: int, description: str = ""):
        """Cria uma barra de progresso aprimorada."""
        if self.use_advanced_feedback:
            return terminal_feedback.create_progress_bar(total, description)
        else:
            # Fallback para barra de progresso simples
            return ProgressBar(total, description)
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = ""):
        """Registra uma métrica de performance."""
        if self.use_advanced_feedback:
            add_performance_metric(metric_name, value)
            terminal_feedback.performance_metric(metric_name, value, unit)
        else:
            self.info(f"Performance: {metric_name} = {value} {unit}".strip())
    
    def enhanced_error(self, message: str, error: Optional[Exception] = None, 
                      suggestion: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Registra erro com contexto e sugestões aprimoradas."""
        error_context = context or {}
        
        if error:
            error_context["error_type"] = type(error).__name__
            error_context["error_details"] = str(error)
        
        if self.use_advanced_feedback:
            terminal_feedback.error(message, error_context, suggestion)
        else:
            # Fallback para logging tradicional
            full_message = message
            if suggestion:
                full_message += f" | Sugestão: {suggestion}"
            if error:
                full_message += f" | Erro: {error}"
            self.error(full_message)
    
    def enhanced_warning(self, message: str, action_required: Optional[str] = None, 
                        context: Optional[Dict[str, Any]] = None):
        """Registra aviso com ação recomendada."""
        warning_context = context or {}
        
        if action_required:
            warning_context["action_required"] = action_required
        
        if self.use_advanced_feedback:
            terminal_feedback.warning(message, warning_context)
        else:
            # Fallback para logging tradicional
            full_message = message
            if action_required:
                full_message += f" | Ação recomendada: {action_required}"
            self.warning(full_message)

class DatabaseLogger(EnhancedLogger):
    """
    Logger especializado para operações de banco de dados.
    """
    
    def __init__(self, name: str = "database_logger"):
        super().__init__(name)
        self.operation_stats = {
            'selects': 0,
            'inserts': 0,
            'updates': 0,
            'deletes': 0,
            'creates': 0
        }
    
    def select(self, table: str, count: int = None, duration: float = None):
        """Log de operação SELECT."""
        self.operation_stats['selects'] += 1
        message = f"SELECT - {table}"
        if count is not None:
            message += f" ({count} registros)"
        if duration is not None:
            message += f" em {duration:.3f}s"
        
        self.database_operation("SELECT", table, count)
    
    def insert(self, table: str, count: int = 1, duration: float = None):
        """Log de operação INSERT."""
        self.operation_stats['inserts'] += count
        message = f"INSERT - {table} ({count} registros)"
        if duration is not None:
            message += f" em {duration:.3f}s"
        
        self.database_operation("INSERT", table, count)
    
    def update(self, table: str, count: int = None, duration: float = None):
        """Log de operação UPDATE."""
        self.operation_stats['updates'] += count if count else 1
        message = f"UPDATE - {table}"
        if count is not None:
            message += f" ({count} registros)"
        if duration is not None:
            message += f" em {duration:.3f}s"
        
        self.database_operation("UPDATE", table, count)
    
    def delete(self, table: str, count: int = None, duration: float = None):
        """Log de operação DELETE."""
        self.operation_stats['deletes'] += count if count else 1
        message = f"DELETE - {table}"
        if count is not None:
            message += f" ({count} registros)"
        if duration is not None:
            message += f" em {duration:.3f}s"
        
        self.database_operation("DELETE", table, count)
    
    def create_table(self, table: str):
        """Log de criação de tabela."""
        self.operation_stats['creates'] += 1
        self.database_operation("CREATE TABLE", table)
    
    def transaction_start(self, description: str = ""):
        """Log de início de transação."""
        message = "🔄 TRANSAÇÃO INICIADA"
        if description:
            message += f" - {description}"
        self.info(message)
    
    def transaction_commit(self, description: str = ""):
        """Log de commit de transação."""
        message = "✅ TRANSAÇÃO CONFIRMADA"
        if description:
            message += f" - {description}"
        self.success(message)
    
    def transaction_rollback(self, description: str = "", error: str = ""):
        """Log de rollback de transação."""
        message = "🔄 TRANSAÇÃO REVERTIDA"
        if description:
            message += f" - {description}"
        if error:
            message += f" - Erro: {error}"
        self.warning(message)
    
    def print_operation_stats(self):
        """Imprime estatísticas de operações de banco."""
        self.subsection("Estatísticas de Banco de Dados")
        for operation, count in self.operation_stats.items():
            if count > 0:
                print(f"{Fore.CYAN}  {operation.upper()}: {count}{Style.RESET_ALL}")

class NVDLogger(EnhancedLogger):
    """
    Logger especializado para operações NVD.
    """
    
    def __init__(self, name: str = "nvd_logger"):
        super().__init__(name)
        self.nvd_stats = {
            'api_calls': 0,
            'vulnerabilities_processed': 0,
            'errors': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def api_call(self, endpoint: str, page: int = None, status_code: int = None, duration: float = None):
        """Log de chamada à API NVD."""
        self.nvd_stats['api_calls'] += 1
        
        message = f"🌐 API NVD - {endpoint}"
        if page is not None:
            message += f" (página {page})"
        
        self.api_request("GET", endpoint, status_code, duration)
    
    def vulnerability_processed(self, cve_id: str, action: str = "processed"):
        """Log de processamento de vulnerabilidade."""
        self.nvd_stats['vulnerabilities_processed'] += 1
        message = f"🔍 CVE {action.upper()}: {cve_id}"
        self.info(message)
    
    def batch_processed(self, count: int, total: int = None, duration: float = None):
        """Log de processamento em lote."""
        message = f"📦 LOTE PROCESSADO: {count} vulnerabilidades"
        if total is not None:
            message += f" de {total}"
        if duration is not None:
            message += f" em {duration:.2f}s"
        
        self.success(message)
    
    def cache_hit(self, key: str):
        """Log de cache hit."""
        self.nvd_stats['cache_hits'] += 1
        self.debug(f"💾 CACHE HIT: {key}")
    
    def cache_miss(self, key: str):
        """Log de cache miss."""
        self.nvd_stats['cache_misses'] += 1
        self.debug(f"💾 CACHE MISS: {key}")
    
    def sync_started(self, full_sync: bool = False):
        """Log de início de sincronização."""
        sync_type = "COMPLETA" if full_sync else "INCREMENTAL"
        self.section(f"Sincronização {sync_type} Iniciada")
    
    def sync_completed(self, processed: int, duration: float, errors: int = 0):
        message = f"✅ SINCRONIZAÇÃO CONCLUÍDA: {processed} vulnerabilidades em {duration:.2f}s"
        if errors > 0:
            message += f" ({errors} erros)"
        self.success(message)
        self.performance_metric("processing_rate", processed / duration, "vulns_per_second")
    
    def print_nvd_stats(self):
        """Imprime estatísticas NVD."""
        self.subsection("Estatísticas NVD")
        for stat, count in self.nvd_stats.items():
            if count > 0:
                print(f"{Fore.GREEN}  {stat.replace('_', ' ').upper()}: {count}{Style.RESET_ALL}")
        
        # Calcular taxa de cache
        total_cache = self.nvd_stats['cache_hits'] + self.nvd_stats['cache_misses']
        if total_cache > 0:
            cache_rate = (self.nvd_stats['cache_hits'] / total_cache) * 100
            print(f"{Fore.YELLOW}  TAXA DE CACHE: {cache_rate:.1f}%{Style.RESET_ALL}")

@contextmanager
def progress_context(total: int, description: str = ""):
    """
    Context manager para barra de progresso.
    
    Usage:
        with progress_context(100, "Processando") as progress:
            for i in range(100):
                # fazer trabalho
                progress.update(1)
    """
    progress = ProgressBar(total, description)
    try:
        yield progress
    finally:
        progress.finish()

@contextmanager
def timed_operation(logger: EnhancedLogger, operation_name: str):
    """
    Context manager para medir tempo de operação.
    
    Usage:
        with timed_operation(logger, "Operação complexa"):
            # fazer trabalho
    """
    start_time = time.time()
    logger.progress(f"Iniciando: {operation_name}")
    
    try:
        yield
        duration = time.time() - start_time
        logger.success(f"Concluído: {operation_name} em {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Falhou: {operation_name} após {duration:.2f}s - {str(e)}")
        raise

# Instâncias globais
app_logger = EnhancedLogger("app")
db_logger = DatabaseLogger("database")
nvd_logger = NVDLogger("nvd")

# Funções de conveniência
def get_app_logger() -> EnhancedLogger:
    """Obtém logger da aplicação."""
    return app_logger

def get_db_logger() -> DatabaseLogger:
    """Obtém logger do banco de dados."""
    return db_logger

def get_nvd_logger() -> NVDLogger:
    """Obtém logger NVD."""
    return nvd_logger

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    Configura logging global.
    
    Args:
        level: Nível de log
        log_file: Arquivo de log (opcional)
    """
    # Configurar nível para todos os loggers
    for logger in [app_logger, db_logger, nvd_logger]:
        logger.level = getattr(logging, level.upper())
        logger.logger.setLevel(logger.level)
    
    # Adicionar handler de arquivo se especificado
    if log_file:
        # Garantir que o diretório do arquivo de log exista
        try:
            log_path = Path(log_file)
            if log_path.parent and not log_path.parent.exists():
                log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Em caso de falha na criação do diretório, continuar sem interromper a inicialização
            pass

        file_handler = logging.FileHandler(str(log_path), encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        for logger in [app_logger, db_logger, nvd_logger]:
            logger.logger.addHandler(file_handler)

if __name__ == "__main__":
    # Exemplo de uso
    setup_logging("DEBUG")
    
    logger = get_app_logger()
    db_logger = get_db_logger()
    nvd_logger = get_nvd_logger()
    
    # Demonstração
    logger.section("Teste do Sistema de Logging")
    
    logger.info("Iniciando aplicação")
    logger.success("Conexão com banco estabelecida")
    logger.warning("Cache Redis não disponível")
    
    # Teste de progresso
    with progress_context(10, "Processando dados") as progress:
        for i in range(10):
            time.sleep(0.1)
            progress.update(1, f"Item {i+1}")
    
    # Teste de operação temporizada
    with timed_operation(logger, "Operação de teste"):
        time.sleep(1)
    
    # Estatísticas
    logger.print_stats()
    db_logger.print_operation_stats()
    nvd_logger.print_nvd_stats()

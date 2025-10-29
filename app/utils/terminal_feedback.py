#!/usr/bin/env python3
"""
Sistema aprimorado de feedback para terminal.
Integra com o sistema de logging existente e adiciona recursos avançados de feedback.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from contextlib import contextmanager
from dataclasses import dataclass
import json

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''

class FeedbackType(Enum):
    """Tipos de feedback disponíveis."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"
    SYSTEM = "system"
    DATABASE = "database"
    API = "api"
    PERFORMANCE = "performance"

@dataclass
class FeedbackMessage:
    """Estrutura de uma mensagem de feedback."""
    type: FeedbackType
    message: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None
    progress: Optional[float] = None

class AdvancedProgressBar:
    """
    Barra de progresso avançada com múltiplas funcionalidades.
    """
    
    def __init__(self, total: int, description: str = "", width: int = 50, 
                 show_eta: bool = True, show_rate: bool = True):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self.show_eta = show_eta
        self.show_rate = show_rate
        self.start_time = time.time()
        self.last_update = 0
        self.last_current = 0
        self.rate_samples = []
        self._lock = threading.Lock()
        self.completed = False
        
    def update(self, increment: int = 1, description: Optional[str] = None, 
               context: Optional[str] = None):
        """Atualiza a barra de progresso com contexto adicional."""
        with self._lock:
            self.current = min(self.current + increment, self.total)
            if description:
                self.description = description
            
            current_time = time.time()
            
            # Calcular taxa de progresso
            if current_time - self.last_update > 0.5:  # Atualizar taxa a cada 0.5s
                rate = (self.current - self.last_current) / (current_time - self.last_update)
                self.rate_samples.append(rate)
                if len(self.rate_samples) > 10:  # Manter apenas últimas 10 amostras
                    self.rate_samples.pop(0)
                self.last_current = self.current
                self.last_update = current_time
            
            # Renderizar se passou tempo suficiente ou completou
            if current_time - self.last_update > 0.1 or self.current == self.total:
                self._render(context)
                
            if self.current == self.total and not self.completed:
                self.completed = True
                print()  # Nova linha quando completo
    
    def _render(self, context: Optional[str] = None):
        """Renderiza a barra de progresso com informações avançadas."""
        if self.total == 0:
            percentage = 100
        else:
            percentage = (self.current / self.total) * 100
        
        filled_width = int(self.width * self.current / self.total) if self.total > 0 else 0
        bar = '█' * filled_width + '░' * (self.width - filled_width)
        
        # Informações de tempo e taxa
        elapsed_time = time.time() - self.start_time
        info_parts = []
        
        if self.show_rate and self.rate_samples:
            avg_rate = sum(self.rate_samples) / len(self.rate_samples)
            info_parts.append(f"{avg_rate:.1f}/s")
        
        if self.show_eta and self.current > 0 and self.current < self.total:
            if self.rate_samples:
                avg_rate = sum(self.rate_samples) / len(self.rate_samples)
                if avg_rate > 0:
                    eta = (self.total - self.current) / avg_rate
                    info_parts.append(f"ETA: {self._format_time(eta)}")
        
        info_str = " | ".join(info_parts)
        if info_str:
            info_str = f" | {info_str}"
        
        # Contexto adicional
        context_str = f" | {context}" if context else ""
        
        # Renderizar linha
        line = (f"\r{Fore.CYAN}{self.description}{Style.RESET_ALL} "
                f"|{Fore.GREEN}{bar}{Style.RESET_ALL}| "
                f"{percentage:6.1f}% ({self.current}/{self.total})"
                f"{info_str}{context_str}")
        
        # Limitar tamanho da linha
        if len(line) > 120:
            line = line[:117] + "..."
        
        sys.stdout.write(line)
        sys.stdout.flush()
    
    def _format_time(self, seconds: float) -> str:
        """Formata tempo em formato legível."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            return f"{seconds/3600:.0f}h {(seconds%3600)/60:.0f}m"
    
    def __enter__(self):
        """Entrada do context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Saída do context manager."""
        if not self.completed:
            self.update(self.total - self.current)  # Completar se não foi finalizado
        return False

class TerminalFeedback:
    """
    Sistema principal de feedback para terminal.
    """
    
    def __init__(self, enable_colors: bool = True, log_to_file: bool = False, 
                 log_file: Optional[str] = None):
        self.enable_colors = enable_colors and COLORAMA_AVAILABLE
        self.log_to_file = log_to_file
        self.log_file = log_file
        self.message_history: List[FeedbackMessage] = []
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Configurações de cores e ícones
        self.colors = {
            FeedbackType.INFO: Fore.BLUE,
            FeedbackType.SUCCESS: Fore.GREEN,
            FeedbackType.WARNING: Fore.YELLOW,
            FeedbackType.ERROR: Fore.RED,
            FeedbackType.PROGRESS: Fore.CYAN,
            FeedbackType.SYSTEM: Fore.MAGENTA,
            FeedbackType.DATABASE: Fore.BLUE,
            FeedbackType.API: Fore.CYAN,
            FeedbackType.PERFORMANCE: Fore.YELLOW
        }
        
        self.icons = {
            FeedbackType.INFO: "ℹ️",
            FeedbackType.SUCCESS: "✅",
            FeedbackType.WARNING: "⚠️",
            FeedbackType.ERROR: "❌",
            FeedbackType.PROGRESS: "🔄",
            FeedbackType.SYSTEM: "⚙️",
            FeedbackType.DATABASE: "🗄️",
            FeedbackType.API: "🌐",
            FeedbackType.PERFORMANCE: "📊"
        }
    
    def message(self, feedback_type: FeedbackType, message: str, 
                context: Optional[Dict[str, Any]] = None, 
                duration: Optional[float] = None):
        """Exibe uma mensagem de feedback."""
        timestamp = datetime.now()
        
        # Criar objeto de feedback
        feedback_msg = FeedbackMessage(
            type=feedback_type,
            message=message,
            timestamp=timestamp,
            context=context,
            duration=duration
        )
        
        with self._lock:
            self.message_history.append(feedback_msg)
            if len(self.message_history) > 1000:  # Limitar histórico
                self.message_history.pop(0)
        
        # Renderizar mensagem
        self._render_message(feedback_msg)
        
        # Log para arquivo se habilitado
        if self.log_to_file and self.log_file:
            self._log_to_file(feedback_msg)
    
    def _render_message(self, feedback_msg: FeedbackMessage):
        """Renderiza uma mensagem no terminal."""
        color = self.colors.get(feedback_msg.type, "") if self.enable_colors else ""
        icon = self.icons.get(feedback_msg.type, "")
        reset = Style.RESET_ALL if self.enable_colors else ""
        
        # Timestamp formatado
        time_str = feedback_msg.timestamp.strftime("%H:%M:%S")
        
        # Duração se disponível
        duration_str = f" ({feedback_msg.duration:.2f}s)" if feedback_msg.duration else ""
        
        # Contexto se disponível
        context_str = ""
        if feedback_msg.context:
            context_parts = []
            for key, value in feedback_msg.context.items():
                context_parts.append(f"{key}={value}")
            if context_parts:
                context_str = f" [{', '.join(context_parts)}]"
        
        # Montar mensagem final
        full_message = (f"{color}{icon} [{time_str}] {feedback_msg.message}"
                       f"{duration_str}{context_str}{reset}")
        
        print(full_message)
    
    def _log_to_file(self, feedback_msg: FeedbackMessage):
        """Registra mensagem em arquivo de log."""
        try:
            log_entry = {
                "timestamp": feedback_msg.timestamp.isoformat(),
                "type": feedback_msg.type.value,
                "message": feedback_msg.message,
                "context": feedback_msg.context,
                "duration": feedback_msg.duration
            }
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Erro ao escrever log: {e}")
    
    # Métodos de conveniência
    def info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Mensagem informativa."""
        self.message(FeedbackType.INFO, message, context)
    
    def success(self, message: str, context: Optional[Dict[str, Any]] = None, 
                duration: Optional[float] = None):
        """Mensagem de sucesso."""
        self.message(FeedbackType.SUCCESS, message, context, duration)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None, 
                suggestion: Optional[str] = None):
        """Mensagem de aviso com sugestão opcional."""
        if suggestion:
            context = context or {}
            context["suggestion"] = suggestion
        self.message(FeedbackType.WARNING, message, context)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None, 
              suggestion: Optional[str] = None):
        """Mensagem de erro com sugestão opcional."""
        if suggestion:
            context = context or {}
            context["suggestion"] = suggestion
        self.message(FeedbackType.ERROR, message, context)
    
    def progress(self, message: str, progress: float, context: Optional[Dict[str, Any]] = None):
        """Mensagem de progresso com porcentagem."""
        progress_msg = FeedbackMessage(
            type=FeedbackType.PROGRESS,
            message=message,
            timestamp=datetime.now(),
            context=context,
            progress=progress
        )
        self._render_message(progress_msg)
        self.message_history.append(progress_msg)
        
        if self.log_to_file:
            self._log_to_file(progress_msg)
    
    def system(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Mensagem de sistema."""
        self.message(FeedbackType.SYSTEM, message, context)
    
    def performance(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Mensagem de performance."""
        self.message(FeedbackType.PERFORMANCE, message, context)
    
    def database_operation(self, operation: str, table: str, count: Optional[int] = None, 
                          duration: Optional[float] = None):
        """Feedback para operações de banco de dados."""
        context = {"operation": operation, "table": table}
        if count is not None:
            context["count"] = count
        
        message = f"Database {operation} on {table}"
        if count is not None:
            message += f" ({count} records)"
        
        self.message(FeedbackType.DATABASE, message, context, duration)
    
    def api_request(self, method: str, url: str, status_code: Optional[int] = None, 
                   duration: Optional[float] = None):
        """Feedback para requisições de API."""
        context = {"method": method, "url": url}
        if status_code is not None:
            context["status_code"] = status_code
        
        message = f"API {method} {url}"
        if status_code is not None:
            message += f" -> {status_code}"
        
        self.message(FeedbackType.API, message, context, duration)
    
    def performance_metric(self, metric_name: str, value: Any, unit: str = ""):
        """Feedback para métricas de performance."""
        context = {"metric": metric_name, "value": value, "unit": unit}
        message = f"Performance: {metric_name} = {value} {unit}".strip()
        self.message(FeedbackType.PERFORMANCE, message, context)
    
    @contextmanager
    def operation(self, operation_name: str, context: Optional[Dict[str, Any]] = None):
        """Context manager para operações com timing automático."""
        start_time = time.time()
        operation_id = f"{operation_name}_{int(start_time)}"
        
        with self._lock:
            self.active_operations[operation_id] = {
                "name": operation_name,
                "start_time": start_time,
                "context": context or {}
            }
        
        self.info(f"Iniciando: {operation_name}", context)
        
        try:
            yield operation_id
            duration = time.time() - start_time
            self.success(f"Concluído: {operation_name}", context, duration)
        except Exception as e:
            duration = time.time() - start_time
            error_context = (context or {}).copy()
            error_context["error"] = str(e)
            self.error(f"Falhou: {operation_name}", error_context)
            raise
        finally:
            with self._lock:
                self.active_operations.pop(operation_id, None)
    
    def create_progress_bar(self, total: int, description: str = "", 
                           show_eta: bool = True, show_rate: bool = True) -> AdvancedProgressBar:
        """Cria uma nova barra de progresso."""
        return AdvancedProgressBar(total, description, show_eta=show_eta, show_rate=show_rate)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema de feedback."""
        with self._lock:
            type_counts = {}
            for msg in self.message_history:
                type_counts[msg.type.value] = type_counts.get(msg.type.value, 0) + 1
            
            return {
                "total_messages": len(self.message_history),
                "message_types": type_counts,
                "active_operations": len(self.active_operations),
                "operations": list(self.active_operations.keys())
            }

# Instância global
terminal_feedback = TerminalFeedback()

# Funções de conveniência
def info(message: str, context: Optional[Dict[str, Any]] = None):
    """Função de conveniência para mensagens informativas."""
    terminal_feedback.info(message, context)

def success(message: str, context: Optional[Dict[str, Any]] = None, 
           duration: Optional[float] = None):
    """Função de conveniência para mensagens de sucesso."""
    terminal_feedback.success(message, context, duration)

def warning(message: str, context: Optional[Dict[str, Any]] = None):
    """Função de conveniência para mensagens de aviso."""
    terminal_feedback.warning(message, context)

def error(message: str, context: Optional[Dict[str, Any]] = None, 
         suggestion: Optional[str] = None):
    """Função de conveniência para mensagens de erro."""
    terminal_feedback.error(message, context, suggestion)

def progress_bar(total: int, description: str = "") -> AdvancedProgressBar:
    """Função de conveniência para criar barra de progresso."""
    return terminal_feedback.create_progress_bar(total, description)

@contextmanager
def timed_operation(operation_name: str, context: Optional[Dict[str, Any]] = None):
    """Context manager para operações com timing automático."""
    with terminal_feedback.operation(operation_name, context) as op_id:
        yield op_id

if __name__ == "__main__":
    # Teste do sistema
    feedback = TerminalFeedback()
    
    feedback.info("Sistema de feedback inicializado")
    feedback.success("Conexão estabelecida", {"host": "localhost", "port": 5432})
    feedback.warning("Cache Redis indisponível")
    feedback.error("Falha na autenticação", suggestion="Verifique as credenciais")
    
    # Teste de barra de progresso
    progress = feedback.create_progress_bar(100, "Processando dados")
    for i in range(100):
        time.sleep(0.01)
        progress.update(1, context=f"Item {i+1}")
    
    # Teste de operação com timing
    with feedback.operation("Operação de teste", {"tipo": "exemplo"}):
        time.sleep(1)
    
    print("\nEstatísticas:")
    stats = feedback.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

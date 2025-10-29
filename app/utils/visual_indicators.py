#!/usr/bin/env python3
"""
Sistema de indicadores visuais para operações longas.
Fornece spinners, animações e indicadores de status em tempo real.
"""

import sys
import time
import threading
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, timedelta

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

class SpinnerType(Enum):
    """Tipos de spinners disponíveis."""
    DOTS = "dots"
    BARS = "bars"
    ARROWS = "arrows"
    CLOCK = "clock"
    BOUNCE = "bounce"
    PULSE = "pulse"

class StatusType(Enum):
    """Tipos de status para indicadores."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PAUSED = "paused"

class Spinner:
    """
    Spinner animado para indicar operações em andamento.
    """
    
    ANIMATIONS = {
        SpinnerType.DOTS: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
        SpinnerType.BARS: ['▁', '▃', '▄', '▅', '▆', '▇', '█', '▇', '▆', '▅', '▄', '▃'],
        SpinnerType.ARROWS: ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
        SpinnerType.CLOCK: ['🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚', '🕛'],
        SpinnerType.BOUNCE: ['⠁', '⠂', '⠄', '⠂'],
        SpinnerType.PULSE: ['●', '○', '●', '○']
    }
    
    def __init__(self, spinner_type: SpinnerType = SpinnerType.DOTS, 
                 message: str = "Processando...", color: str = Fore.CYAN):
        self.spinner_type = spinner_type
        self.message = message
        self.color = color if COLORAMA_AVAILABLE else ""
        self.frames = self.ANIMATIONS[spinner_type]
        self.current_frame = 0
        self.running = False
        self.thread = None
        self.start_time = None
        self.update_interval = 0.1
        
    def start(self):
        """Inicia o spinner."""
        if not self.running:
            self.running = True
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
    
    def stop(self, final_message: Optional[str] = None, status: StatusType = StatusType.SUCCESS):
        """Para o spinner com mensagem final opcional."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1)
            
            # Limpar linha atual
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            
            if final_message:
                status_icon = self._get_status_icon(status)
                status_color = self._get_status_color(status)
                elapsed = time.time() - self.start_time if self.start_time else 0
                
                final_line = (f"{status_color}{status_icon} {final_message} "
                             f"({elapsed:.1f}s){Style.RESET_ALL}")
                print(final_line)
            else:
                print()  # Nova linha
    
    def update_message(self, message: str):
        """Atualiza a mensagem do spinner."""
        self.message = message
    
    def _animate(self):
        """Loop de animação do spinner."""
        while self.running:
            frame = self.frames[self.current_frame]
            elapsed = time.time() - self.start_time if self.start_time else 0
            
            line = (f"\r{self.color}{frame} {self.message} "
                   f"({elapsed:.1f}s){Style.RESET_ALL}")
            
            sys.stdout.write(line)
            sys.stdout.flush()
            
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            time.sleep(self.update_interval)
    
    def _get_status_icon(self, status: StatusType) -> str:
        """Retorna ícone para o status."""
        icons = {
            StatusType.SUCCESS: "✅",
            StatusType.WARNING: "⚠️",
            StatusType.ERROR: "❌",
            StatusType.PAUSED: "⏸️",
            StatusType.IDLE: "⏹️",
            StatusType.RUNNING: "▶️"
        }
        return icons.get(status, "ℹ️")
    
    def _get_status_color(self, status: StatusType) -> str:
        """Retorna cor para o status."""
        if not COLORAMA_AVAILABLE:
            return ""
        
        colors = {
            StatusType.SUCCESS: Fore.GREEN,
            StatusType.WARNING: Fore.YELLOW,
            StatusType.ERROR: Fore.RED,
            StatusType.PAUSED: Fore.YELLOW,
            StatusType.IDLE: Fore.WHITE,
            StatusType.RUNNING: Fore.CYAN
        }
        return colors.get(status, Fore.WHITE)

class StatusIndicator:
    """
    Indicador de status para múltiplas operações simultâneas.
    """
    
    def __init__(self, max_operations: int = 5):
        self.max_operations = max_operations
        self.operations: Dict[str, Dict[str, Any]] = {}
        self.display_thread = None
        self.running = False
        self._lock = threading.Lock()
        
    def add_operation(self, operation_id: str, name: str, 
                     status: StatusType = StatusType.RUNNING):
        """Adiciona uma nova operação ao indicador."""
        with self._lock:
            self.operations[operation_id] = {
                "name": name,
                "status": status,
                "start_time": time.time(),
                "last_update": time.time(),
                "progress": 0.0,
                "details": ""
            }
            
            # Limitar número de operações exibidas
            if len(self.operations) > self.max_operations:
                oldest_id = min(self.operations.keys(), 
                              key=lambda x: self.operations[x]["start_time"])
                del self.operations[oldest_id]
    
    def update_operation(self, operation_id: str, status: Optional[StatusType] = None,
                        progress: Optional[float] = None, details: Optional[str] = None):
        """Atualiza uma operação existente."""
        with self._lock:
            if operation_id in self.operations:
                op = self.operations[operation_id]
                if status is not None:
                    op["status"] = status
                if progress is not None:
                    op["progress"] = max(0.0, min(1.0, progress))
                if details is not None:
                    op["details"] = details
                op["last_update"] = time.time()
    
    def remove_operation(self, operation_id: str, final_status: StatusType = StatusType.SUCCESS):
        """Remove uma operação do indicador."""
        with self._lock:
            if operation_id in self.operations:
                self.operations[operation_id]["status"] = final_status
                # Manter por alguns segundos antes de remover
                threading.Timer(3.0, lambda: self.operations.pop(operation_id, None)).start()
    
    def finish_operation(self, operation_id: str, success: bool = True, details: Optional[str] = None):
        """Finaliza uma operação com status de sucesso ou erro."""
        final_status = StatusType.SUCCESS if success else StatusType.ERROR
        self.update_operation(operation_id, status=final_status, progress=1.0, details=details)
        self.remove_operation(operation_id, final_status)
    
    def start_display(self):
        """Inicia a exibição do indicador."""
        if not self.running:
            self.running = True
            self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
            self.display_thread.start()
    
    def stop_display(self):
        """Para a exibição do indicador."""
        if self.running:
            self.running = False
            if self.display_thread:
                self.display_thread.join(timeout=1)
            
            # Limpar display
            self._clear_display()
    
    def _display_loop(self):
        """Loop principal de exibição."""
        while self.running:
            self._render_display()
            time.sleep(0.5)
    
    def _render_display(self):
        """Renderiza o display atual."""
        with self._lock:
            if not self.operations:
                return
            
            # Mover cursor para posição inicial
            lines_to_clear = len(self.operations) + 2
            sys.stdout.write(f'\033[{lines_to_clear}A')  # Mover cursor para cima
            
            # Header
            header = f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}"
            print(f"\r{header}")
            print(f"\r{Fore.CYAN}  Operações Ativas ({len(self.operations)}){Style.RESET_ALL}")
            
            # Operações
            for op_id, op_data in list(self.operations.items()):
                self._render_operation(op_id, op_data)
            
            # Footer
            footer = f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}"
            print(f"\r{footer}")
    
    def _render_operation(self, op_id: str, op_data: Dict[str, Any]):
        """Renderiza uma operação individual."""
        status = op_data["status"]
        name = op_data["name"]
        progress = op_data["progress"]
        details = op_data["details"]
        elapsed = time.time() - op_data["start_time"]
        
        # Ícone e cor do status
        status_icon = self._get_status_icon(status)
        status_color = self._get_status_color(status)
        
        # Barra de progresso simples
        if progress > 0:
            bar_width = 20
            filled = int(bar_width * progress)
            bar = '█' * filled + '░' * (bar_width - filled)
            progress_str = f" |{Fore.GREEN}{bar}{Style.RESET_ALL}| {progress*100:5.1f}%"
        else:
            progress_str = ""
        
        # Detalhes
        details_str = f" - {details}" if details else ""
        
        # Linha completa
        line = (f"\r{status_color}{status_icon} {name}{Style.RESET_ALL}"
               f"{progress_str} ({elapsed:.1f}s){details_str}")
        
        # Truncar se muito longo
        if len(line) > 80:
            line = line[:77] + "..."
        
        print(line)
    
    def _clear_display(self):
        """Limpa o display."""
        lines_to_clear = len(self.operations) + 3
        for _ in range(lines_to_clear):
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            sys.stdout.write('\033[1A')  # Mover cursor uma linha para cima
        sys.stdout.flush()
    
    def _get_status_icon(self, status: StatusType) -> str:
        """Retorna ícone para o status."""
        icons = {
            StatusType.SUCCESS: "✅",
            StatusType.WARNING: "⚠️",
            StatusType.ERROR: "❌",
            StatusType.PAUSED: "⏸️",
            StatusType.IDLE: "⏹️",
            StatusType.RUNNING: "🔄"
        }
        return icons.get(status, "ℹ️")
    
    def _get_status_color(self, status: StatusType) -> str:
        """Retorna cor para o status."""
        if not COLORAMA_AVAILABLE:
            return ""
        
        colors = {
            StatusType.SUCCESS: Fore.GREEN,
            StatusType.WARNING: Fore.YELLOW,
            StatusType.ERROR: Fore.RED,
            StatusType.PAUSED: Fore.YELLOW,
            StatusType.IDLE: Fore.WHITE,
            StatusType.RUNNING: Fore.CYAN
        }
        return colors.get(status, Fore.WHITE)

class PerformanceIndicator:
    """
    Indicador de performance em tempo real.
    """
    
    def __init__(self, update_interval: float = 1.0):
        self.update_interval = update_interval
        self.metrics: Dict[str, List[float]] = {}
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        
    def add_metric(self, name: str, value: float):
        """Adiciona uma métrica."""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = []
            
            self.metrics[name].append(value)
            
            # Manter apenas últimos 60 valores (1 minuto se update_interval = 1s)
            if len(self.metrics[name]) > 60:
                self.metrics[name].pop(0)
    
    def start_display(self):
        """Inicia a exibição das métricas."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._display_loop, daemon=True)
            self.thread.start()
    
    def stop_display(self):
        """Para a exibição das métricas."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1)
    
    def _display_loop(self):
        """Loop de exibição das métricas."""
        while self.running:
            self._render_metrics()
            time.sleep(self.update_interval)
    
    def _render_metrics(self):
        """Renderiza as métricas atuais."""
        with self._lock:
            if not self.metrics:
                return
            
            # Limpar área de exibição
            lines_count = len(self.metrics) + 2
            for _ in range(lines_count):
                sys.stdout.write('\r' + ' ' * 80)
                sys.stdout.write('\033[1A')
            
            # Header
            print(f"\r{Fore.YELLOW}📊 Performance Metrics{Style.RESET_ALL}")
            print(f"\r{Fore.YELLOW}{'-'*40}{Style.RESET_ALL}")
            
            # Métricas
            for name, values in self.metrics.items():
                if values:
                    current = values[-1]
                    avg = sum(values) / len(values)
                    trend = self._get_trend(values)
                    
                    trend_icon = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
                    
                    line = (f"\r{name}: {current:.2f} (avg: {avg:.2f}) {trend_icon}")
                    print(line)
    
    def _get_trend(self, values: List[float]) -> float:
        """Calcula tendência dos valores (positiva/negativa/estável)."""
        if len(values) < 2:
            return 0
        
        # Comparar últimos 5 valores com 5 anteriores
        recent_count = min(5, len(values) // 2)
        if recent_count < 2:
            return 0
        
        recent_avg = sum(values[-recent_count:]) / recent_count
        previous_avg = sum(values[-recent_count*2:-recent_count]) / recent_count
        
        return recent_avg - previous_avg

# Instâncias globais
status_indicator = StatusIndicator()
performance_indicator = PerformanceIndicator()

# Funções de conveniência
def spinner(spinner_type: SpinnerType = SpinnerType.DOTS, 
           message: str = "Processando...") -> Spinner:
    """Cria um novo spinner."""
    return Spinner(spinner_type, message)

def show_operation_status(operation_id: str, name: str, 
                         status: StatusType = StatusType.RUNNING):
    """Adiciona operação ao indicador de status."""
    status_indicator.add_operation(operation_id, name, status)

def update_operation_status(operation_id: str, status: Optional[StatusType] = None,
                           progress: Optional[float] = None, details: Optional[str] = None):
    """Atualiza status de uma operação."""
    status_indicator.update_operation(operation_id, status, progress, details)

def hide_operation_status(operation_id: str, final_status: StatusType = StatusType.SUCCESS):
    """Remove operação do indicador de status."""
    status_indicator.remove_operation(operation_id, final_status)

def add_performance_metric(name: str, value: float):
    """Adiciona métrica de performance."""
    performance_indicator.add_metric(name, value)

if __name__ == "__main__":
    # Teste dos indicadores visuais
    import random
    
    print("Testando sistema de indicadores visuais...\n")
    
    # Teste do spinner
    spinner_test = spinner(SpinnerType.DOTS, "Carregando dados")
    spinner_test.start()
    time.sleep(3)
    spinner_test.stop("Dados carregados com sucesso", StatusType.SUCCESS)
    
    # Teste do indicador de status
    status_indicator.start_display()
    
    # Simular operações
    operations = [
        ("sync_nvd", "Sincronização NVD"),
        ("db_backup", "Backup do banco"),
        ("report_gen", "Geração de relatório")
    ]
    
    for op_id, op_name in operations:
        show_operation_status(op_id, op_name)
        time.sleep(1)
    
    # Simular progresso
    for i in range(100):
        for op_id, _ in operations:
            progress = (i + random.randint(0, 10)) / 100
            progress = min(1.0, progress)
            update_operation_status(op_id, progress=progress, 
                                  details=f"Processando item {i+1}")
        time.sleep(0.1)
    
    # Finalizar operações
    for op_id, _ in operations:
        hide_operation_status(op_id, StatusType.SUCCESS)
    
    time.sleep(2)
    status_indicator.stop_display()
    
    print("\nTeste concluído!")

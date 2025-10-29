import psutil
import logging
import gc
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """
    Monitor de memória em tempo real para otimização durante sincronização NVD.
    """
    
    def __init__(self, warning_threshold_mb: int = 1024, critical_threshold_mb: int = 2048):
        """
        Inicializa o monitor de memória.
        
        Args:
            warning_threshold_mb: Limite de aviso em MB
            critical_threshold_mb: Limite crítico em MB
        """
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Converter para bytes
        self.critical_threshold = critical_threshold_mb * 1024 * 1024
        self.process = psutil.Process()
        self.initial_memory = self.get_current_memory()
        self.peak_memory = self.initial_memory
        self.gc_count = 0
        
    def get_current_memory(self) -> int:
        """
        Obtém o uso atual de memória em bytes.
        
        Returns:
            Uso de memória em bytes
        """
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss  # Resident Set Size
        except Exception as e:
            logger.error(f"Erro ao obter informações de memória: {e}")
            return 0
    
    def get_memory_stats(self) -> Dict[str, float]:
        """
        Obtém estatísticas detalhadas de memória.
        
        Returns:
            Dicionário com estatísticas de memória
        """
        current_memory = self.get_current_memory()
        
        # Atualizar pico de memória
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
        
        return {
            'current_mb': current_memory / (1024 * 1024),
            'peak_mb': self.peak_memory / (1024 * 1024),
            'initial_mb': self.initial_memory / (1024 * 1024),
            'increase_mb': (current_memory - self.initial_memory) / (1024 * 1024),
            'warning_threshold_mb': self.warning_threshold / (1024 * 1024),
            'critical_threshold_mb': self.critical_threshold / (1024 * 1024),
            'gc_count': self.gc_count
        }
    
    def check_memory_status(self) -> str:
        """
        Verifica o status atual da memória.
        
        Returns:
            Status: 'normal', 'warning', 'critical'
        """
        current_memory = self.get_current_memory()
        
        if current_memory >= self.critical_threshold:
            return 'critical'
        elif current_memory >= self.warning_threshold:
            return 'warning'
        else:
            return 'normal'
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """
        Força garbage collection e retorna estatísticas.
        
        Returns:
            Estatísticas do garbage collection
        """
        memory_before = self.get_current_memory()
        
        # Executar garbage collection
        collected = gc.collect()
        self.gc_count += 1
        
        memory_after = self.get_current_memory()
        freed_mb = (memory_before - memory_after) / (1024 * 1024)
        
        stats = {
            'objects_collected': collected,
            'memory_freed_mb': freed_mb,
            'memory_before_mb': memory_before / (1024 * 1024),
            'memory_after_mb': memory_after / (1024 * 1024)
        }
        
        logger.info(f"Garbage collection executado: {collected} objetos coletados, "
                   f"{freed_mb:.2f} MB liberados")
        
        return stats
    
    def log_memory_status(self, context: str = "") -> None:
        """
        Registra o status atual da memória no log.
        
        Args:
            context: Contexto adicional para o log
        """
        stats = self.get_memory_stats()
        status = self.check_memory_status()
        
        log_message = (
            f"Memória {context}: {stats['current_mb']:.1f}MB atual, "
            f"{stats['peak_mb']:.1f}MB pico, "
            f"+{stats['increase_mb']:.1f}MB desde início, "
            f"Status: {status}"
        )
        
        if status == 'critical':
            logger.error(log_message)
        elif status == 'warning':
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def should_trigger_gc(self) -> bool:
        """
        Determina se deve executar garbage collection baseado no uso de memória.
        
        Returns:
            True se deve executar GC
        """
        status = self.check_memory_status()
        return status in ['warning', 'critical']
    
    def auto_manage_memory(self, context: str = "") -> Optional[Dict[str, int]]:
        """
        Gerencia automaticamente a memória, executando GC se necessário.
        
        Args:
            context: Contexto para logging
            
        Returns:
            Estatísticas do GC se executado, None caso contrário
        """
        status = self.check_memory_status()
        
        if status == 'critical':
            logger.warning(f"Memória crítica detectada {context}, executando GC forçado")
            return self.force_garbage_collection()
        elif status == 'warning':
            logger.info(f"Memória em aviso {context}, executando GC preventivo")
            return self.force_garbage_collection()
        
        return None
    
    def get_memory_usage_mb(self) -> float:
        """
        Obtém o uso atual de memória em MB.
        
        Returns:
            Uso de memória em MB
        """
        current_memory = self.get_current_memory()
        return current_memory / (1024 * 1024)
    
    def get_system_memory_info(self) -> Dict[str, float]:
        """
        Obtém informações de memória do sistema.
        
        Returns:
            Informações de memória do sistema
        """
        try:
            memory = psutil.virtual_memory()
            return {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_gb': memory.used / (1024**3),
                'percent_used': memory.percent
            }
        except Exception as e:
            logger.error(f"Erro ao obter informações de memória do sistema: {e}")
            return {}

# Instância global para uso em toda a aplicação
memory_monitor = MemoryMonitor()

import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from functools import wraps

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Serviço para monitoramento de performance e métricas da aplicação.
    """
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'avg_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'errors': 0,
            'recent_times': deque(maxlen=100)  # Últimas 100 execuções
        })
        self.lock = threading.Lock()
        self.start_time = datetime.utcnow()
        
    def record_execution(self, operation_name, execution_time, success=True):
        """
        Registra uma execução de operação.
        
        Args:
            operation_name: Nome da operação
            execution_time: Tempo de execução em segundos
            success: Se a operação foi bem-sucedida
        """
        with self.lock:
            metric = self.metrics[operation_name]
            
            metric['count'] += 1
            
            if success:
                metric['total_time'] += execution_time
                metric['avg_time'] = metric['total_time'] / metric['count']
                metric['min_time'] = min(metric['min_time'], execution_time)
                metric['max_time'] = max(metric['max_time'], execution_time)
                metric['recent_times'].append(execution_time)
            else:
                metric['errors'] += 1
    
    def get_metrics(self, operation_name=None):
        """
        Obtém métricas de performance.
        
        Args:
            operation_name: Nome específico da operação (opcional)
            
        Returns:
            dict: Métricas de performance
        """
        with self.lock:
            if operation_name:
                if operation_name in self.metrics:
                    metric = self.metrics[operation_name].copy()
                    # Converter deque para lista para serialização
                    metric['recent_times'] = list(metric['recent_times'])
                    return metric
                return None
            
            # Retornar todas as métricas
            all_metrics = {}
            for name, metric in self.metrics.items():
                all_metrics[name] = metric.copy()
                all_metrics[name]['recent_times'] = list(metric['recent_times'])
            
            return all_metrics
    
    def get_health_status(self):
        """
        Obtém status de saúde do sistema.
        
        Returns:
            dict: Status de saúde
        """
        with self.lock:
            uptime = datetime.utcnow() - self.start_time
            
            # Calcular taxa de erro geral
            total_requests = sum(m['count'] for m in self.metrics.values())
            total_errors = sum(m['errors'] for m in self.metrics.values())
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            # Verificar performance recente
            recent_times = []
            for metric in self.metrics.values():
                recent_times.extend(list(metric.get('recent_times', [])))
            
            avg_response_time = sum(recent_times) / len(recent_times) if recent_times else 0
            
            # Determinar status de saúde
            health_status = 'healthy'
            if error_rate > 10:  # Mais de 10% de erro
                health_status = 'unhealthy'
            elif error_rate > 5 or avg_response_time > 5:  # 5% erro ou >5s resposta
                health_status = 'degraded'
            
            return {
                'status': health_status,
                'uptime_seconds': int(uptime.total_seconds()),
                'total_requests': total_requests,
                'total_errors': total_errors,
                'error_rate_percent': round(error_rate, 2),
                'avg_response_time_seconds': round(avg_response_time, 3),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def reset_metrics(self):
        """
        Reseta todas as métricas.
        """
        with self.lock:
            self.metrics.clear()
            self.start_time = datetime.utcnow()
            logger.info("Métricas de performance resetadas")

# Instância global do monitor
performance_monitor = PerformanceMonitor()

def monitor_performance(operation_name):
    """
    Decorator para monitorar performance de funções.
    
    Args:
        operation_name: Nome da operação para métricas
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                performance_monitor.record_execution(
                    operation_name, 
                    execution_time, 
                    success
                )
                
                # Log performance lenta
                if execution_time > 5:  # Mais de 5 segundos
                    logger.warning(
                        f"Operação lenta detectada: {operation_name} "
                        f"levou {execution_time:.2f}s"
                    )
        
        return wrapper
    return decorator

class HealthChecker:
    """
    Verificador de saúde dos serviços.
    """
    
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name, check_function):
        """
        Registra uma verificação de saúde.
        
        Args:
            name: Nome da verificação
            check_function: Função que retorna True se saudável
        """
        self.checks[name] = check_function
    
    def run_checks(self):
        """
        Executa todas as verificações de saúde.
        
        Returns:
            dict: Resultado das verificações
        """
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                is_healthy = check_func()
                check_time = time.time() - start_time
                
                results[name] = {
                    'healthy': bool(is_healthy),
                    'response_time': round(check_time, 3)
                }
                
                if not is_healthy:
                    overall_healthy = False
                    
            except Exception as e:
                logger.error(f"Erro na verificação de saúde {name}: {str(e)}")
                results[name] = {
                    'healthy': False,
                    'error': str(e),
                    'response_time': None
                }
                overall_healthy = False
        
        return {
            'overall_healthy': overall_healthy,
            'checks': results,
            'timestamp': datetime.utcnow().isoformat()
        }

# Instância global do verificador de saúde
health_checker = HealthChecker()

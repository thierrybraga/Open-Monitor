#!/usr/bin/env python3
"""
Sistema de monitoramento de performance para operações NVD e banco de dados.
Coleta métricas detalhadas e gera relatórios de performance.
"""

import asyncio
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager
import psutil
import json

from sqlalchemy import text
from app.extensions import db

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Métrica individual de performance"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    
@dataclass
class OperationMetrics:
    """Métricas de uma operação específica"""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error_message: Optional[str] = None):
        """Finaliza a operação e calcula a duração."""
        self.end_time = datetime.utcnow()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.success = success
        self.error_message = error_message

@dataclass
class SystemMetrics:
    """Métricas do sistema"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class DatabaseMetrics:
    """Métricas do banco de dados"""
    active_connections: int
    idle_connections: int
    total_connections: int
    queries_per_second: float
    slow_queries: int
    cache_hit_ratio: float
    table_sizes_mb: Dict[str, float] = field(default_factory=dict)
    index_usage: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

class PerformanceMonitor:
    """
    Monitor de performance para operações NVD e banco de dados.
    
    Características:
    - Coleta automática de métricas do sistema
    - Monitoramento de operações específicas
    - Métricas de banco de dados
    - Alertas baseados em thresholds
    - Relatórios detalhados
    - Exportação de dados para análise
    """
    
    def __init__(self, collection_interval: int = 30, max_history: int = 1000):
        """
        Inicializa o monitor de performance.
        
        Args:
            collection_interval: Intervalo de coleta em segundos
            max_history: Máximo de registros históricos
        """
        self.collection_interval = collection_interval
        self.max_history = max_history
        
        # Armazenamento de métricas
        self.system_metrics_history = deque(maxlen=max_history)
        self.database_metrics_history = deque(maxlen=max_history)
        self.operation_metrics = defaultdict(list)
        self.custom_metrics = defaultdict(list)
        
        # Controle de coleta
        self._collecting = False
        self._collection_thread = None
        self._lock = threading.Lock()
        
        # Thresholds para alertas
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_io_mb_per_sec': 100.0,
            'response_time_seconds': 5.0,
            'error_rate_percent': 5.0,
            'database_connections': 80
        }
        
        # Callbacks para alertas
        self.alert_callbacks = []
        
        # Cache para cálculos
        self._last_disk_io = None
        self._last_network_io = None
        self._last_timestamp = None
        
        logger.info("Monitor de performance inicializado")
    
    def start_monitoring(self):
        """Inicia a coleta automática de métricas."""
        if self._collecting:
            logger.warning("Monitoramento já está ativo")
            return
        
        self._collecting = True
        self._collection_thread = threading.Thread(target=self._collect_metrics_loop, daemon=True)
        self._collection_thread.start()
        
        logger.info(f"Monitoramento iniciado com intervalo de {self.collection_interval}s")
    
    def stop_monitoring(self):
        """Para a coleta automática de métricas."""
        self._collecting = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        
        logger.info("Monitoramento parado")
    
    def _collect_metrics_loop(self):
        """Loop principal de coleta de métricas."""
        while self._collecting:
            try:
                # Coletar métricas do sistema
                system_metrics = self._collect_system_metrics()
                with self._lock:
                    self.system_metrics_history.append(system_metrics)
                
                # Coletar métricas do banco de dados
                try:
                    db_metrics = self._collect_database_metrics()
                    with self._lock:
                        self.database_metrics_history.append(db_metrics)
                except Exception as e:
                    logger.warning(f"Erro ao coletar métricas do banco: {e}")
                
                # Verificar thresholds e gerar alertas
                self._check_thresholds(system_metrics)
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Erro na coleta de métricas: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Coleta métricas do sistema."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memória
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        current_timestamp = time.time()
        
        disk_io_read_mb = 0.0
        disk_io_write_mb = 0.0
        
        if self._last_disk_io and self._last_timestamp:
            time_delta = current_timestamp - self._last_timestamp
            if time_delta > 0:
                read_delta = disk_io.read_bytes - self._last_disk_io.read_bytes
                write_delta = disk_io.write_bytes - self._last_disk_io.write_bytes
                
                disk_io_read_mb = (read_delta / (1024 * 1024)) / time_delta
                disk_io_write_mb = (write_delta / (1024 * 1024)) / time_delta
        
        self._last_disk_io = disk_io
        
        # Network I/O
        network_io = psutil.net_io_counters()
        network_sent_mb = 0.0
        network_recv_mb = 0.0
        
        if self._last_network_io and self._last_timestamp:
            time_delta = current_timestamp - self._last_timestamp
            if time_delta > 0:
                sent_delta = network_io.bytes_sent - self._last_network_io.bytes_sent
                recv_delta = network_io.bytes_recv - self._last_network_io.bytes_recv
                
                network_sent_mb = (sent_delta / (1024 * 1024)) / time_delta
                network_recv_mb = (recv_delta / (1024 * 1024)) / time_delta
        
        self._last_network_io = network_io
        self._last_timestamp = current_timestamp
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb
        )
    
    def _collect_database_metrics(self) -> DatabaseMetrics:
        """Coleta métricas do banco de dados."""
        try:
            with db.engine.connect() as conn:
                # Detectar tipo do banco
                dialect = db.engine.dialect.name.lower()
                
                if 'postgresql' in dialect:
                    return self._collect_postgresql_metrics(conn)
                elif 'mysql' in dialect:
                    return self._collect_mysql_metrics(conn)
                elif 'sqlite' in dialect:
                    return self._collect_sqlite_metrics(conn)
                else:
                    return self._collect_generic_metrics(conn)
                    
        except Exception as e:
            logger.error(f"Erro ao coletar métricas do banco: {e}")
            return DatabaseMetrics(
                active_connections=0,
                idle_connections=0,
                total_connections=0,
                queries_per_second=0.0,
                slow_queries=0,
                cache_hit_ratio=0.0
            )
    
    def _collect_postgresql_metrics(self, conn) -> DatabaseMetrics:
        """Coleta métricas específicas do PostgreSQL."""
        # Conexões
        result = conn.execute(text(
            "SELECT state, COUNT(*) FROM pg_stat_activity GROUP BY state"
        )).fetchall()
        
        active_connections = 0
        idle_connections = 0
        total_connections = 0
        
        for row in result:
            state, count = row
            total_connections += count
            if state == 'active':
                active_connections = count
            elif state == 'idle':
                idle_connections = count
        
        # Cache hit ratio
        cache_result = conn.execute(text(
            "SELECT sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100 "
            "FROM pg_statio_user_tables WHERE heap_blks_read > 0"
        )).fetchone()
        
        cache_hit_ratio = float(cache_result[0]) if cache_result and cache_result[0] else 0.0
        
        # Tamanhos das tabelas
        table_sizes = conn.execute(text(
            "SELECT tablename, pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024 as size_mb "
            "FROM pg_tables WHERE schemaname = 'public'"
        )).fetchall()
        
        table_sizes_mb = {row[0]: float(row[1]) for row in table_sizes}
        
        return DatabaseMetrics(
            active_connections=active_connections,
            idle_connections=idle_connections,
            total_connections=total_connections,
            queries_per_second=0.0,  # Requer cálculo temporal
            slow_queries=0,  # Requer configuração específica
            cache_hit_ratio=cache_hit_ratio,
            table_sizes_mb=table_sizes_mb
        )
    
    def _collect_mysql_metrics(self, conn) -> DatabaseMetrics:
        """Coleta métricas específicas do MySQL."""
        # Status das conexões
        result = conn.execute(text("SHOW STATUS LIKE 'Threads_%'")).fetchall()
        
        active_connections = 0
        total_connections = 0
        
        for row in result:
            variable_name, value = row
            if variable_name == 'Threads_connected':
                total_connections = int(value)
            elif variable_name == 'Threads_running':
                active_connections = int(value)
        
        idle_connections = total_connections - active_connections
        
        # Cache hit ratio (InnoDB)
        cache_result = conn.execute(text(
            "SELECT (1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)) * 100 "
            "FROM INFORMATION_SCHEMA.GLOBAL_STATUS "
            "WHERE VARIABLE_NAME IN ('Innodb_buffer_pool_reads', 'Innodb_buffer_pool_read_requests')"
        )).fetchone()
        
        cache_hit_ratio = float(cache_result[0]) if cache_result and cache_result[0] else 0.0
        
        return DatabaseMetrics(
            active_connections=active_connections,
            idle_connections=idle_connections,
            total_connections=total_connections,
            queries_per_second=0.0,
            slow_queries=0,
            cache_hit_ratio=cache_hit_ratio
        )
    
    def _collect_sqlite_metrics(self, conn) -> DatabaseMetrics:
        """Coleta métricas específicas do SQLite."""
        # SQLite é single-threaded, métricas limitadas
        return DatabaseMetrics(
            active_connections=1,
            idle_connections=0,
            total_connections=1,
            queries_per_second=0.0,
            slow_queries=0,
            cache_hit_ratio=0.0
        )
    
    def _collect_generic_metrics(self, conn) -> DatabaseMetrics:
        """Coleta métricas genéricas para bancos não suportados."""
        return DatabaseMetrics(
            active_connections=0,
            idle_connections=0,
            total_connections=0,
            queries_per_second=0.0,
            slow_queries=0,
            cache_hit_ratio=0.0
        )
    
    def _check_thresholds(self, system_metrics: SystemMetrics):
        """Verifica thresholds e gera alertas."""
        alerts = []
        
        # CPU
        if system_metrics.cpu_percent > self.thresholds['cpu_percent']:
            alerts.append({
                'type': 'cpu_high',
                'message': f'CPU usage high: {system_metrics.cpu_percent:.1f}%',
                'value': system_metrics.cpu_percent,
                'threshold': self.thresholds['cpu_percent']
            })
        
        # Memória
        if system_metrics.memory_percent > self.thresholds['memory_percent']:
            alerts.append({
                'type': 'memory_high',
                'message': f'Memory usage high: {system_metrics.memory_percent:.1f}%',
                'value': system_metrics.memory_percent,
                'threshold': self.thresholds['memory_percent']
            })
        
        # Disk I/O
        total_disk_io = system_metrics.disk_io_read_mb + system_metrics.disk_io_write_mb
        if total_disk_io > self.thresholds['disk_io_mb_per_sec']:
            alerts.append({
                'type': 'disk_io_high',
                'message': f'Disk I/O high: {total_disk_io:.1f} MB/s',
                'value': total_disk_io,
                'threshold': self.thresholds['disk_io_mb_per_sec']
            })
        
        # Executar callbacks de alerta
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Erro no callback de alerta: {e}")
    
    @contextmanager
    def track_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager para rastrear uma operação."""
        operation = OperationMetrics(
            operation_name=operation_name,
            start_time=datetime.utcnow(),
            tags=tags or {}
        )
        
        try:
            yield operation
            operation.finish(success=True)
        except Exception as e:
            operation.finish(success=False, error_message=str(e))
            raise
        finally:
            with self._lock:
                self.operation_metrics[operation_name].append(operation)
                # Manter apenas os últimos registros
                if len(self.operation_metrics[operation_name]) > self.max_history:
                    self.operation_metrics[operation_name] = \
                        self.operation_metrics[operation_name][-self.max_history:]
    
    def record_metric(self, name: str, value: float, unit: str = "", 
                     tags: Optional[Dict[str, str]] = None):
        """Registra uma métrica customizada."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        
        with self._lock:
            self.custom_metrics[name].append(metric)
            # Manter apenas os últimos registros
            if len(self.custom_metrics[name]) > self.max_history:
                self.custom_metrics[name] = self.custom_metrics[name][-self.max_history:]
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Gera relatório de performance."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            # Métricas do sistema
            recent_system_metrics = [
                m for m in self.system_metrics_history 
                if m.timestamp >= cutoff_time
            ]
            
            # Métricas do banco
            recent_db_metrics = [
                m for m in self.database_metrics_history 
                if m.timestamp >= cutoff_time
            ]
            
            # Operações
            recent_operations = {}
            for op_name, operations in self.operation_metrics.items():
                recent_ops = [
                    op for op in operations 
                    if op.start_time >= cutoff_time
                ]
                if recent_ops:
                    recent_operations[op_name] = recent_ops
        
        # Calcular estatísticas
        report = {
            'period_hours': hours,
            'generated_at': datetime.utcnow().isoformat(),
            'system_metrics': self._analyze_system_metrics(recent_system_metrics),
            'database_metrics': self._analyze_database_metrics(recent_db_metrics),
            'operations': self._analyze_operations(recent_operations),
            'alerts_summary': self._get_alerts_summary()
        }
        
        return report
    
    def _analyze_system_metrics(self, metrics: List[SystemMetrics]) -> Dict[str, Any]:
        """Analisa métricas do sistema."""
        if not metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in metrics]
        memory_values = [m.memory_percent for m in metrics]
        disk_read_values = [m.disk_io_read_mb for m in metrics]
        disk_write_values = [m.disk_io_write_mb for m in metrics]
        
        return {
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'disk_io': {
                'avg_read_mb_per_sec': sum(disk_read_values) / len(disk_read_values),
                'avg_write_mb_per_sec': sum(disk_write_values) / len(disk_write_values),
                'max_read_mb_per_sec': max(disk_read_values),
                'max_write_mb_per_sec': max(disk_write_values)
            },
            'sample_count': len(metrics)
        }
    
    def _analyze_database_metrics(self, metrics: List[DatabaseMetrics]) -> Dict[str, Any]:
        """Analisa métricas do banco de dados."""
        if not metrics:
            return {}
        
        connection_values = [m.total_connections for m in metrics]
        cache_hit_values = [m.cache_hit_ratio for m in metrics if m.cache_hit_ratio > 0]
        
        return {
            'connections': {
                'avg': sum(connection_values) / len(connection_values),
                'max': max(connection_values),
                'min': min(connection_values)
            },
            'cache_hit_ratio': {
                'avg': sum(cache_hit_values) / len(cache_hit_values) if cache_hit_values else 0,
                'max': max(cache_hit_values) if cache_hit_values else 0,
                'min': min(cache_hit_values) if cache_hit_values else 0
            },
            'sample_count': len(metrics)
        }
    
    def _analyze_operations(self, operations: Dict[str, List[OperationMetrics]]) -> Dict[str, Any]:
        """Analisa métricas de operações."""
        analysis = {}
        
        for op_name, ops in operations.items():
            if not ops:
                continue
            
            durations = [op.duration for op in ops if op.duration is not None]
            successful_ops = [op for op in ops if op.success]
            failed_ops = [op for op in ops if not op.success]
            
            analysis[op_name] = {
                'total_operations': len(ops),
                'successful_operations': len(successful_ops),
                'failed_operations': len(failed_ops),
                'success_rate': (len(successful_ops) / len(ops)) * 100 if ops else 0,
                'duration_stats': {
                    'avg_seconds': sum(durations) / len(durations) if durations else 0,
                    'max_seconds': max(durations) if durations else 0,
                    'min_seconds': min(durations) if durations else 0
                } if durations else None
            }
        
        return analysis
    
    def _get_alerts_summary(self) -> Dict[str, Any]:
        """Retorna resumo dos alertas."""
        return {
            'thresholds': self.thresholds,
            'active_callbacks': len(self.alert_callbacks)
        }
    
    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Adiciona callback para alertas."""
        self.alert_callbacks.append(callback)
    
    def export_metrics(self, filename: str, format: str = 'json'):
        """Exporta métricas para arquivo."""
        data = {
            'exported_at': datetime.utcnow().isoformat(),
            'system_metrics': [{
                'timestamp': m.timestamp.isoformat(),
                'cpu_percent': m.cpu_percent,
                'memory_percent': m.memory_percent,
                'memory_used_mb': m.memory_used_mb,
                'disk_io_read_mb': m.disk_io_read_mb,
                'disk_io_write_mb': m.disk_io_write_mb
            } for m in self.system_metrics_history],
            'operation_metrics': {
                op_name: [{
                    'start_time': op.start_time.isoformat(),
                    'end_time': op.end_time.isoformat() if op.end_time else None,
                    'duration': op.duration,
                    'success': op.success,
                    'error_message': op.error_message,
                    'tags': op.tags
                } for op in ops]
                for op_name, ops in self.operation_metrics.items()
            }
        }
        
        if format.lower() == 'json':
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(f"Formato não suportado: {format}")
        
        logger.info(f"Métricas exportadas para {filename}")

# Instância global
performance_monitor = PerformanceMonitor()

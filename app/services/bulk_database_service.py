#!/usr/bin/env python3
"""
Serviço otimizado para operações de banco de dados em lote.
Implementa bulk operations, índices otimizados e transações eficientes.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from contextlib import contextmanager

from sqlalchemy import text, Index, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.cvss_metric import CVSSMetric
from app.models.sync_metadata import SyncMetadata

logger = logging.getLogger(__name__)

@dataclass
class BulkOperationStats:
    """Estatísticas de operações em lote"""
    total_records: int = 0
    inserted_records: int = 0
    updated_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def records_per_second(self) -> float:
        if self.duration == 0:
            return 0.0
        return self.total_records / self.duration
    
    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        successful = self.inserted_records + self.updated_records + self.skipped_records
        return (successful / self.total_records) * 100

class BulkDatabaseService:
    """
    Serviço otimizado para operações de banco de dados em lote.
    
    Características:
    - Bulk insert/update otimizado por dialeto SQL
    - Transações em lotes para melhor performance
    - Índices otimizados para consultas frequentes
    - Detecção automática de conflitos e duplicatas
    - Estatísticas detalhadas de performance
    - Rollback automático em caso de erro
    """
    
    def __init__(self, batch_size: int = 1000, max_batch_size: int = 5000):
        """
        Inicializa o serviço de operações em lote.
        
        Args:
            batch_size: Tamanho padrão do lote
            max_batch_size: Tamanho máximo permitido do lote
        """
        self.batch_size = min(batch_size, max_batch_size)
        self.max_batch_size = max_batch_size
        
        # Detectar dialeto do banco
        self.db_dialect = self._detect_database_dialect()
        logger.info(f"Dialeto do banco detectado: {self.db_dialect}")
        
        # Configurações específicas por dialeto
        self.dialect_config = self._get_dialect_config()
        
        # Cache de preparação de statements
        self._prepared_statements = {}
        
        # Estatísticas
        self.stats = BulkOperationStats()
    
    def _detect_database_dialect(self) -> str:
        """Detecta o dialeto do banco de dados."""
        try:
            engine = db.get_engine()
            dialect_name = engine.dialect.name.lower()
            
            if 'postgresql' in dialect_name:
                return 'postgresql'
            elif 'mysql' in dialect_name:
                return 'mysql'
            elif 'sqlite' in dialect_name:
                return 'sqlite'
            else:
                logger.warning(f"Dialeto não reconhecido: {dialect_name}, usando padrão")
                return 'generic'
                
        except Exception as e:
            logger.error(f"Erro ao detectar dialeto: {e}")
            return 'generic'
    
    def _get_dialect_config(self) -> Dict[str, Any]:
        """Retorna configurações específicas do dialeto."""
        configs = {
            'postgresql': {
                'supports_upsert': True,
                'upsert_method': 'ON CONFLICT',
                'batch_size_multiplier': 1.0,
                'supports_returning': True,
                'supports_bulk_insert': True
            },
            'mysql': {
                'supports_upsert': True,
                'upsert_method': 'ON DUPLICATE KEY UPDATE',
                'batch_size_multiplier': 0.8,
                'supports_returning': False,
                'supports_bulk_insert': True
            },
            'sqlite': {
                'supports_upsert': True,
                'upsert_method': 'ON CONFLICT',
                'batch_size_multiplier': 0.6,
                'supports_returning': False,
                'supports_bulk_insert': False
            },
            'generic': {
                'supports_upsert': False,
                'upsert_method': None,
                'batch_size_multiplier': 0.5,
                'supports_returning': False,
                'supports_bulk_insert': False
            }
        }
        
        return configs.get(self.db_dialect, configs['generic'])
    
    def _get_effective_batch_size(self) -> int:
        """Calcula tamanho efetivo do lote baseado no dialeto."""
        multiplier = self.dialect_config['batch_size_multiplier']
        return int(self.batch_size * multiplier)
    
    @contextmanager
    def bulk_transaction(self, session: Optional[Session] = None):
        """Context manager para transações em lote otimizadas."""
        if session is None:
            session = db.session
        
        # Configurações de otimização
        original_autocommit = session.autocommit
        original_autoflush = session.autoflush
        
        try:
            # Otimizar para bulk operations
            session.autocommit = False
            session.autoflush = False
            
            # Configurações específicas do dialeto
            if self.db_dialect == 'postgresql':
                session.execute(text("SET synchronous_commit = OFF"))
                session.execute(text("SET wal_buffers = '16MB'"))
            elif self.db_dialect == 'mysql':
                session.execute(text("SET autocommit = 0"))
                session.execute(text("SET unique_checks = 0"))
                session.execute(text("SET foreign_key_checks = 0"))
            
            yield session
            
            # Commit final
            session.commit()
            
        except Exception as e:
            logger.error(f"Erro na transação em lote: {e}")
            session.rollback()
            raise
        finally:
            # Restaurar configurações
            session.autocommit = original_autocommit
            session.autoflush = original_autoflush
            
            # Restaurar configurações do dialeto
            try:
                if self.db_dialect == 'postgresql':
                    session.execute(text("SET synchronous_commit = ON"))
                elif self.db_dialect == 'mysql':
                    session.execute(text("SET unique_checks = 1"))
                    session.execute(text("SET foreign_key_checks = 1"))
                    session.execute(text("SET autocommit = 1"))
            except Exception as e:
                logger.warning(f"Erro ao restaurar configurações: {e}")
    
    def bulk_upsert_vulnerabilities(self, vulnerabilities_data: List[Dict[str, Any]], 
                                  session: Optional[Session] = None) -> BulkOperationStats:
        """
        Executa upsert em lote de vulnerabilidades.
        
        Args:
            vulnerabilities_data: Lista de dados de vulnerabilidades
            session: Sessão do banco (opcional)
            
        Returns:
            Estatísticas da operação
        """
        stats = BulkOperationStats()
        stats.start_time = time.time()
        stats.total_records = len(vulnerabilities_data)
        
        if not vulnerabilities_data:
            stats.end_time = time.time()
            return stats
        
        logger.info(f"Iniciando bulk upsert de {len(vulnerabilities_data)} vulnerabilidades")
        
        if session is None:
            session = db.session
        
        try:
            with self.bulk_transaction(session):
                effective_batch_size = self._get_effective_batch_size()
                
                # Processar em lotes
                for i in range(0, len(vulnerabilities_data), effective_batch_size):
                    batch = vulnerabilities_data[i:i + effective_batch_size]
                    batch_stats = self._upsert_vulnerability_batch(batch, session)
                    
                    # Agregar estatísticas
                    stats.inserted_records += batch_stats.inserted_records
                    stats.updated_records += batch_stats.updated_records
                    stats.skipped_records += batch_stats.skipped_records
                    stats.failed_records += batch_stats.failed_records
                    
                    logger.debug(f"Lote {i//effective_batch_size + 1} processado: "
                               f"{batch_stats.inserted_records} inseridos, "
                               f"{batch_stats.updated_records} atualizados")
                
                # Atualizar índices se necessário
                self._update_indexes_if_needed(session)
                
        except Exception as e:
            logger.error(f"Erro durante bulk upsert: {e}")
            stats.failed_records = stats.total_records
            raise
        finally:
            stats.end_time = time.time()
        
        logger.info(f"Bulk upsert concluído: {stats.inserted_records} inseridos, "
                   f"{stats.updated_records} atualizados em {stats.duration:.2f}s "
                   f"({stats.records_per_second:.2f} registros/s)")
        
        return stats
    
    def _upsert_vulnerability_batch(self, batch_data: List[Dict[str, Any]], 
                                  session: Session) -> BulkOperationStats:
        """Executa upsert de um lote de vulnerabilidades."""
        batch_stats = BulkOperationStats()
        batch_stats.total_records = len(batch_data)
        
        try:
            if self.dialect_config['supports_upsert']:
                # Usar upsert nativo do banco
                batch_stats = self._native_upsert_vulnerabilities(batch_data, session)
            else:
                # Fallback para upsert manual
                batch_stats = self._manual_upsert_vulnerabilities(batch_data, session)
                
        except Exception as e:
            logger.error(f"Erro no lote de vulnerabilidades: {e}")
            batch_stats.failed_records = batch_stats.total_records
            raise
        
        return batch_stats
    
    def _native_upsert_vulnerabilities(self, batch_data: List[Dict[str, Any]], 
                                     session: Session) -> BulkOperationStats:
        """Executa upsert usando recursos nativos do banco."""
        stats = BulkOperationStats()
        stats.total_records = len(batch_data)
        
        try:
            if self.db_dialect == 'postgresql':
                # PostgreSQL com ON CONFLICT
                stmt = pg_insert(Vulnerability.__table__).values(batch_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['cve_id'],
                    set_={
                        'description': stmt.excluded.description,
                        'last_modified': stmt.excluded.last_modified,
                        'cvss_score': stmt.excluded.cvss_score,
                        'base_severity': stmt.excluded.base_severity,
                        'updated_at': stmt.excluded.updated_at
                    },
                    where=Vulnerability.__table__.c.last_modified < stmt.excluded.last_modified
                )
                
                if self.dialect_config['supports_returning']:
                    stmt = stmt.returning(Vulnerability.__table__.c.id)
                    result = session.execute(stmt)
                    stats.inserted_records = len(result.fetchall())
                else:
                    session.execute(stmt)
                    stats.inserted_records = len(batch_data)  # Aproximação
                
            elif self.db_dialect == 'mysql':
                # MySQL com ON DUPLICATE KEY UPDATE
                stmt = mysql_insert(Vulnerability.__table__).values(batch_data)
                stmt = stmt.on_duplicate_key_update(
                    description=stmt.inserted.description,
                    last_modified=stmt.inserted.last_modified,
                    cvss_score=stmt.inserted.cvss_score,
                    base_severity=stmt.inserted.base_severity,
                    updated_at=stmt.inserted.updated_at
                )
                
                result = session.execute(stmt)
                stats.inserted_records = result.rowcount
                
            elif self.db_dialect == 'sqlite':
                # SQLite com ON CONFLICT
                stmt = sqlite_insert(Vulnerability.__table__).values(batch_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['cve_id'],
                    set_={
                        'description': stmt.excluded.description,
                        'last_modified': stmt.excluded.last_modified,
                        'cvss_score': stmt.excluded.cvss_score,
                        'base_severity': stmt.excluded.base_severity,
                        'updated_at': stmt.excluded.updated_at
                    }
                )
                
                session.execute(stmt)
                stats.inserted_records = len(batch_data)  # Aproximação
            
        except Exception as e:
            logger.error(f"Erro no upsert nativo: {e}")
            raise
        
        return stats
    
    def _manual_upsert_vulnerabilities(self, batch_data: List[Dict[str, Any]], 
                                     session: Session) -> BulkOperationStats:
        """Executa upsert manual para bancos sem suporte nativo."""
        stats = BulkOperationStats()
        stats.total_records = len(batch_data)
        
        try:
            # Extrair CVE IDs para verificação
            cve_ids = [item['cve_id'] for item in batch_data]
            
            # Buscar registros existentes
            existing_vulns = session.query(Vulnerability).filter(
                Vulnerability.cve_id.in_(cve_ids)
            ).all()
            
            existing_cve_map = {vuln.cve_id: vuln for vuln in existing_vulns}
            
            # Separar inserções e atualizações
            to_insert = []
            to_update = []
            
            for item in batch_data:
                cve_id = item['cve_id']
                if cve_id in existing_cve_map:
                    existing_vuln = existing_cve_map[cve_id]
                    
                    # Verificar se precisa atualizar
                    item_last_modified = item.get('last_modified')
                    if (item_last_modified and existing_vuln.last_modified and 
                        item_last_modified > existing_vuln.last_modified):
                        
                        # Atualizar campos
                        existing_vuln.description = item.get('description', existing_vuln.description)
                        existing_vuln.last_modified = item_last_modified
                        existing_vuln.cvss_score = item.get('cvss_score', existing_vuln.cvss_score)
                        existing_vuln.base_severity = item.get('base_severity', existing_vuln.base_severity)
                        existing_vuln.updated_at = datetime.utcnow()
                        
                        to_update.append(existing_vuln)
                    else:
                        stats.skipped_records += 1
                else:
                    to_insert.append(item)
            
            # Executar inserções em lote
            if to_insert:
                session.bulk_insert_mappings(Vulnerability, to_insert)
                stats.inserted_records = len(to_insert)
            
            # Executar atualizações
            if to_update:
                for vuln in to_update:
                    session.merge(vuln)
                stats.updated_records = len(to_update)
            
        except Exception as e:
            logger.error(f"Erro no upsert manual: {e}")
            raise
        
        return stats
    
    def bulk_insert_cvss_metrics(self, metrics_data: List[Dict[str, Any]], 
                               session: Optional[Session] = None) -> BulkOperationStats:
        """
        Executa inserção em lote de métricas CVSS.
        
        Args:
            metrics_data: Lista de dados de métricas CVSS
            session: Sessão do banco (opcional)
            
        Returns:
            Estatísticas da operação
        """
        stats = BulkOperationStats()
        stats.start_time = time.time()
        stats.total_records = len(metrics_data)
        
        if not metrics_data:
            stats.end_time = time.time()
            return stats
        
        logger.info(f"Iniciando bulk insert de {len(metrics_data)} métricas CVSS")
        
        if session is None:
            session = db.session
        
        try:
            with self.bulk_transaction(session):
                effective_batch_size = self._get_effective_batch_size()
                
                # Processar em lotes
                for i in range(0, len(metrics_data), effective_batch_size):
                    batch = metrics_data[i:i + effective_batch_size]
                    
                    try:
                        session.bulk_insert_mappings(CVSSMetric, batch)
                        stats.inserted_records += len(batch)
                        
                    except IntegrityError as e:
                        logger.warning(f"Conflito de integridade no lote {i}: {e}")
                        # Tentar inserção individual para identificar duplicatas
                        for item in batch:
                            try:
                                session.bulk_insert_mappings(CVSSMetric, [item])
                                stats.inserted_records += 1
                            except IntegrityError:
                                stats.skipped_records += 1
                    
                    except Exception as e:
                        logger.error(f"Erro no lote {i}: {e}")
                        stats.failed_records += len(batch)
                
        except Exception as e:
            logger.error(f"Erro durante bulk insert de métricas: {e}")
            stats.failed_records = stats.total_records
            raise
        finally:
            stats.end_time = time.time()
        
        logger.info(f"Bulk insert de métricas concluído: {stats.inserted_records} inseridos "
                   f"em {stats.duration:.2f}s ({stats.records_per_second:.2f} registros/s)")
        
        return stats
    
    def _update_indexes_if_needed(self, session: Session):
        """Atualiza índices se necessário após operações em lote."""
        try:
            if self.db_dialect == 'postgresql':
                # Reindex apenas se muitos registros foram inseridos
                if self.stats.inserted_records > 10000:
                    session.execute(text("REINDEX INDEX CONCURRENTLY idx_vulnerability_cve_id"))
                    session.execute(text("REINDEX INDEX CONCURRENTLY idx_vulnerability_last_modified"))
                    logger.info("Índices atualizados após bulk operation")
                    
        except Exception as e:
            logger.warning(f"Erro ao atualizar índices: {e}")
    
    def optimize_database(self, session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executa otimizações no banco de dados.
        
        Args:
            session: Sessão do banco (opcional)
            
        Returns:
            Relatório das otimizações executadas
        """
        if session is None:
            session = db.session
        
        optimization_report = {
            'dialect': self.db_dialect,
            'optimizations_applied': [],
            'errors': []
        }
        
        try:
            if self.db_dialect == 'postgresql':
                # Análise de estatísticas
                session.execute(text("ANALYZE vulnerabilities"))
                session.execute(text("ANALYZE cvss_metrics"))
                optimization_report['optimizations_applied'].append('ANALYZE tables')
                
                # Vacuum se necessário
                result = session.execute(text(
                    "SELECT schemaname, tablename, n_dead_tup FROM pg_stat_user_tables "
                    "WHERE n_dead_tup > 1000"
                )).fetchall()
                
                for row in result:
                    table_name = row[1]
                    session.execute(text(f"VACUUM {table_name}"))
                    optimization_report['optimizations_applied'].append(f'VACUUM {table_name}')
                
            elif self.db_dialect == 'mysql':
                # Otimizar tabelas
                session.execute(text("OPTIMIZE TABLE vulnerabilities"))
                session.execute(text("OPTIMIZE TABLE cvss_metrics"))
                optimization_report['optimizations_applied'].append('OPTIMIZE tables')
                
            elif self.db_dialect == 'sqlite':
                # Vacuum e análise
                session.execute(text("VACUUM"))
                session.execute(text("ANALYZE"))
                optimization_report['optimizations_applied'].append('VACUUM and ANALYZE')
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Erro durante otimização: {e}")
            optimization_report['errors'].append(str(e))
            session.rollback()
        
        return optimization_report
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de performance das operações.
        
        Returns:
            Dicionário com estatísticas detalhadas
        """
        return {
            'database_dialect': self.db_dialect,
            'batch_size': self.batch_size,
            'effective_batch_size': self._get_effective_batch_size(),
            'supports_upsert': self.dialect_config['supports_upsert'],
            'supports_bulk_insert': self.dialect_config['supports_bulk_insert'],
            'last_operation_stats': {
                'total_records': self.stats.total_records,
                'inserted_records': self.stats.inserted_records,
                'updated_records': self.stats.updated_records,
                'skipped_records': self.stats.skipped_records,
                'failed_records': self.stats.failed_records,
                'duration_seconds': round(self.stats.duration, 2),
                'records_per_second': round(self.stats.records_per_second, 2),
                'success_rate_percent': round(self.stats.success_rate, 2)
            }
        }
    
    def create_optimized_indexes(self, session: Optional[Session] = None) -> List[str]:
        """
        Cria índices otimizados para consultas frequentes.
        
        Args:
            session: Sessão do banco (opcional)
            
        Returns:
            Lista de índices criados
        """
        if session is None:
            session = db.session
        
        created_indexes = []
        
        try:
            # Índices para vulnerabilidades
            vulnerability_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_cve_id ON vulnerabilities(cve_id)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_last_modified ON vulnerabilities(last_modified DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_published_date ON vulnerabilities(published_date DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_cvss_score ON vulnerabilities(cvss_score DESC) WHERE cvss_score IS NOT NULL",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_base_severity ON vulnerabilities(base_severity)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vulnerability_created_at ON vulnerabilities(created_at DESC)"
            ]
            
            # Índices para métricas CVSS
            cvss_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvss_vulnerability_id ON cvss_metrics(cve_id)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvss_base_score ON cvss_metrics(base_score DESC) WHERE base_score IS NOT NULL",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cvss_version ON cvss_metrics(version)"
            ]
            
            all_indexes = vulnerability_indexes + cvss_indexes
            
            for index_sql in all_indexes:
                try:
                    if self.db_dialect == 'postgresql':
                        session.execute(text(index_sql))
                    else:
                        # Remover CONCURRENTLY para outros bancos
                        index_sql_clean = index_sql.replace('CONCURRENTLY ', '')
                        session.execute(text(index_sql_clean))
                    
                    created_indexes.append(index_sql)
                    
                except Exception as e:
                    logger.warning(f"Erro ao criar índice: {e}")
            
            session.commit()
            logger.info(f"Criados {len(created_indexes)} índices otimizados")
            
        except Exception as e:
            logger.error(f"Erro ao criar índices: {e}")
            session.rollback()
        
        return created_indexes

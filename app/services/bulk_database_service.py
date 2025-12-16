#!/usr/bin/env python3
"""
Serviço otimizado para operações de banco de dados em lote.
Implementa bulk operations, índices otimizados e transações eficientes.
"""

import logging
import re
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
    def records_per_minute(self) -> float:
        if self.duration == 0:
            return 0.0
        return (self.inserted_records + self.updated_records) * 60.0 / self.duration
    
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
        try:
            # Abrir transação explícita compatível com SQLAlchemy 2.x
            txn_ctx = session.begin_nested() if getattr(session, "in_transaction", None) and session.in_transaction() else session.begin()
            with txn_ctx:
                # Configurações específicas do dialeto (melhores esforços)
                try:
                    if self.db_dialect == 'postgresql':
                        session.execute(text("SET synchronous_commit = OFF"))
                    elif self.db_dialect == 'mysql':
                        session.execute(text("SET unique_checks = 0"))
                        session.execute(text("SET foreign_key_checks = 0"))
                except Exception as cfg_err:
                    logger.debug(f"Config otimização ignorada: {cfg_err}")
                
                yield session
                
                # Restaurar configurações do dialeto
                try:
                    if self.db_dialect == 'postgresql':
                        session.execute(text("SET synchronous_commit = ON"))
                    elif self.db_dialect == 'mysql':
                        session.execute(text("SET unique_checks = 1"))
                        session.execute(text("SET foreign_key_checks = 1"))
                except Exception as cfg_err:
                    logger.debug(f"Restauração de otimização ignorada: {cfg_err}")
        except Exception as e:
            logger.error(f"Erro na transação em lote: {e}")
            raise
    
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
        # Normalizar chaves para o schema atual (last_update) e valores nulos
        normalized = []
        allowed = {
            'cve_id','description','published_date','last_update','cvss_score','base_severity',
            'patch_available','assigner','source_identifier','vuln_status','evaluator_comment',
            'evaluator_solution','evaluator_impact','nvd_vendors_data','nvd_products_data',
            'nvd_cpe_configurations','nvd_version_ranges'
        }
        for item in batch_data:
            itm = dict(item)
            # Renomear last_modified -> last_update
            if 'last_update' not in itm:
                if 'last_modified' in itm:
                    itm['last_update'] = itm.pop('last_modified')
            if 'vendors' in itm and 'nvd_vendors_data' not in itm:
                itm['nvd_vendors_data'] = itm.pop('vendors')
            if 'products' in itm and 'nvd_products_data' not in itm:
                itm['nvd_products_data'] = itm.pop('products')
            if 'cpe_configurations' in itm and 'nvd_cpe_configurations' not in itm:
                itm['nvd_cpe_configurations'] = itm.pop('cpe_configurations')
            if 'version_ranges' in itm and 'nvd_version_ranges' not in itm:
                itm['nvd_version_ranges'] = itm.pop('version_ranges')
            # cvss_score não pode ser nulo
            if itm.get('cvss_score') is None:
                itm['cvss_score'] = 0.0
            # Filtrar apenas campos suportados pela tabela 'vulnerabilities'
            filtered = {k: v for k, v in itm.items() if k in allowed}
            normalized.append(filtered)
        batch_data = normalized
        
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
        
        try:
            from app.models.vendor import Vendor
            from app.models.cve_vendor import CVEVendor
            cve_to_vendor_names = {}
            all_names = set()
            for itm in batch_data:
                cve_id = itm.get('cve_id')
                data = itm.get('nvd_vendors_data')
                names = set()
                if isinstance(data, list):
                    for v in data:
                        if isinstance(v, str) and v.strip():
                            names.add(v.strip())
                        elif isinstance(v, dict):
                            name = v.get('name') or v.get('vendor') or v.get('vendor_name')
                            if isinstance(name, str) and name.strip():
                                names.add(name.strip())
                elif isinstance(data, dict):
                    vs = data.get('vendors')
                    if isinstance(vs, list):
                        for v in vs:
                            if isinstance(v, str) and v.strip():
                                names.add(v.strip())
                            elif isinstance(v, dict):
                                name = v.get('name') or v.get('vendor') or v.get('vendor_name')
                                if isinstance(name, str) and name.strip():
                                    names.add(name.strip())
                    elif isinstance(data.get('name'), str) and data.get('name').strip():
                        names.add(data.get('name').strip())
                elif isinstance(data, str) and data.strip():
                    names.add(data.strip())
                if cve_id and names:
                    cve_to_vendor_names[cve_id] = names
                    all_names.update(names)

            if cve_to_vendor_names:
                try:
                    existing_rows = session.query(Vendor.id, Vendor.name).all()
                    name_to_vendor = { (n or '').strip().lower(): (vid, n) for vid, n in existing_rows if n }
                except Exception:
                    name_to_vendor = {}

                to_create = []
                for n in sorted(all_names):
                    key = (n or '').strip().lower()
                    if not key or key in name_to_vendor:
                        continue
                    to_create.append({'name': n})
                if to_create:
                    try:
                        session.bulk_insert_mappings(Vendor, to_create)
                        session.flush()
                        new_rows = session.query(Vendor.id, Vendor.name).filter(Vendor.name.in_([x['name'] for x in to_create])).all()
                        for vid, nm in new_rows:
                            name_to_vendor[(nm or '').strip().lower()] = (vid, nm)
                    except Exception:
                        pass

                try:
                    cve_ids = list(cve_to_vendor_names.keys())
                    if cve_ids:
                        session.query(CVEVendor).filter(CVEVendor.cve_id.in_(cve_ids)).delete(synchronize_session=False)
                except Exception:
                    pass

                try:
                    to_link = []
                    for cve_id, names in cve_to_vendor_names.items():
                        for n in names:
                            key = (n or '').strip().lower()
                            vid = name_to_vendor.get(key, (None, None))[0]
                            if vid:
                                to_link.append({'cve_id': cve_id, 'vendor_id': vid})
                    if to_link:
                        session.bulk_insert_mappings(CVEVendor, to_link)
                except Exception:
                    pass
        except Exception:
            pass
        
        return batch_stats
    
    def upsert_single_vulnerability(self, vuln_data: Dict[str, Any], session: Optional[Session] = None) -> BulkOperationStats:
        stats = BulkOperationStats()
        stats.start_time = time.time()
        stats.total_records = 1
        if session is None:
            session = db.session
        try:
            with session.begin():
                single_stats = self._upsert_vulnerability_batch([dict(vuln_data)], session)
            stats.inserted_records = single_stats.inserted_records
            stats.updated_records = single_stats.updated_records
            stats.skipped_records = single_stats.skipped_records
        except Exception:
            stats.failed_records = 1
            try:
                session.rollback()
            except Exception:
                pass
            raise
        stats.end_time = time.time()
        return stats
    
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
                        'last_update': stmt.excluded.last_update,
                        'cvss_score': stmt.excluded.cvss_score,
                        'base_severity': stmt.excluded.base_severity
                    },
                    where=Vulnerability.__table__.c.last_update < stmt.excluded.last_update
                )
                
                if self.dialect_config['supports_returning']:
                    stmt = stmt.returning(Vulnerability.__table__.c.cve_id)
                    result = session.execute(stmt)
                    stats.inserted_records = result.rowcount if hasattr(result, 'rowcount') else len(result.fetchall())
                else:
                    result = session.execute(stmt)
                    stats.inserted_records = result.rowcount if hasattr(result, 'rowcount') else len(batch_data)
                
            elif self.db_dialect == 'mysql':
                # MySQL com ON DUPLICATE KEY UPDATE
                stmt = mysql_insert(Vulnerability.__table__).values(batch_data)
                stmt = stmt.on_duplicate_key_update(
                    description=stmt.inserted.description,
                    last_update=stmt.inserted.last_update,
                    cvss_score=stmt.inserted.cvss_score,
                    base_severity=stmt.inserted.base_severity
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
                        'last_update': stmt.excluded.last_update,
                        'cvss_score': stmt.excluded.cvss_score,
                        'base_severity': stmt.excluded.base_severity
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
                    item_last_modified = item.get('last_update')
                    if (item_last_modified and existing_vuln.last_update and 
                        item_last_modified > existing_vuln.last_update):
                        # Atualizar campos
                        existing_vuln.description = item.get('description', existing_vuln.description)
                        existing_vuln.last_update = item_last_modified
                        existing_vuln.cvss_score = item.get('cvss_score', existing_vuln.cvss_score)
                        existing_vuln.base_severity = item.get('base_severity', existing_vuln.base_severity)
                        # updated_at não existe; last_update já foi ajustado
                        to_update.append(existing_vuln)
                    else:
                        batch_stats.skipped_records += 1
                else:
                    to_insert.append(item)
            
            # Executar inserções em lote
            if to_insert:
                session.bulk_insert_mappings(Vulnerability, to_insert)
                batch_stats.inserted_records = len(to_insert)
            
            # Executar atualizações
            if to_update:
                for vuln in to_update:
                    session.merge(vuln)
                batch_stats.updated_records = len(to_update)
            
        except Exception as e:
            logger.error(f"Erro no upsert manual: {e}")
            raise
        
        return batch_stats
    
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
                'records_per_minute': round(self.stats.records_per_minute, 2),
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

    def backfill_vendors_from_vulnerabilities(self, session: Optional[Session] = None, batch_limit: int = 5000) -> Dict[str, int]:
        """
        Executa backfill das tabelas normalizadas de vendors e associações CVEVendor
        a partir do campo JSON `vulnerabilities.nvd_vendors_data`.

        Retorna estatísticas: {'vendors_created': X, 'associations_created': Y, 'cves_processed': Z}
        """
        if session is None:
            session = db.session
        stats = {'vendors_created': 0, 'associations_created': 0, 'cves_processed': 0}
        try:
            from app.models.vendor import Vendor
            from app.models.cve_vendor import CVEVendor
            from app.models.vulnerability import Vulnerability
            import json

            with self.bulk_transaction(session):
                offset = 0
                while True:
                    rows = (
                        session.query(
                            Vulnerability.cve_id,
                            Vulnerability.nvd_vendors_data,
                            Vulnerability.nvd_cpe_configurations,
                            Vulnerability.description,
                        )
                        .offset(offset)
                        .limit(batch_limit)
                        .all()
                    )
                    if not rows:
                        break
                    offset += len(rows)

                    cve_to_names: Dict[str, set] = {}
                    all_names: set = set()
                    from app.jobs.nvd_fetcher import EnhancedCPEParser
                    from app.models.references import Reference
                    parser = EnhancedCPEParser()

                    for cve_id, vendors_json, cpe_json, description in rows:
                        names = set()
                        data = vendors_json
                        try:
                            if isinstance(data, str):
                                try:
                                    data = json.loads(data)
                                except Exception:
                                    pass
                            if isinstance(data, list):
                                for v in data:
                                    if isinstance(v, str) and v.strip():
                                        names.add(v.strip())
                                    elif isinstance(v, dict):
                                        nm = v.get('name') or v.get('vendor') or v.get('vendor_name')
                                        if isinstance(nm, str) and nm.strip():
                                            names.add(nm.strip())
                            elif isinstance(data, dict):
                                vs = data.get('vendors')
                                if isinstance(vs, list):
                                    for v in vs:
                                        if isinstance(v, str) and v.strip():
                                            names.add(v.strip())
                                        elif isinstance(v, dict):
                                            nm = v.get('name') or v.get('vendor') or v.get('vendor_name')
                                            if isinstance(nm, str) and nm.strip():
                                                names.add(nm.strip())
                                elif isinstance(data.get('name'), str) and data.get('name').strip():
                                    names.add(data.get('name').strip())
                            elif isinstance(data, str) and data.strip():
                                names.add(data.strip())
                        except Exception:
                            pass
                        if not names:
                            try:
                                cj = cpe_json
                                if isinstance(cj, str):
                                    try:
                                        cj = json.loads(cj)
                                    except Exception:
                                        cj = None
                                if isinstance(cj, list):
                                    for cfg in cj:
                                        for node in (cfg.get('nodes') or []):
                                            for cpe in (node.get('cpeMatch') or []):
                                                crit = cpe.get('criteria') or ''
                                                if isinstance(crit, str) and crit.startswith('cpe:2.3:'):
                                                    parts = crit.split(':')
                                                    if len(parts) >= 5:
                                                        vendor = parts[3]
                                                        if vendor and vendor not in ('*','-'):
                                                            vendor = re.sub(r'[^a-zA-Z0-9_-]', '', vendor)
                                                            if vendor:
                                                                names.add(vendor)
                                elif isinstance(cj, dict):
                                    for node in (cj.get('nodes') or []):
                                        for cpe in (node.get('cpeMatch') or []):
                                            crit = cpe.get('criteria') or ''
                                            if isinstance(crit, str) and crit.startswith('cpe:2.3:'):
                                                parts = crit.split(':')
                                                if len(parts) >= 5:
                                                    vendor = parts[3]
                                                    if vendor and vendor not in ('*','-'):
                                                        vendor = re.sub(r'[^a-zA-Z0-9_-]', '', vendor)
                                                        if vendor:
                                                            names.add(vendor)
                            except Exception:
                                pass
                        # Fallback adicional: extrair vendors da descrição
                        if not names:
                            try:
                                if isinstance(description, str) and description.strip():
                                    desc_vendors, _desc_products = parser.extract_from_description(description)
                                    for vn in desc_vendors:
                                        if isinstance(vn, str) and vn.strip():
                                            names.add(vn.strip())
                            except Exception:
                                pass
                        # Fallback adicional: extrair vendors das referências associadas
                        if not names:
                            try:
                                ref_rows = session.query(Reference.url, Reference.source).filter(Reference.cve_id == cve_id).all()
                                ref_list = [{'url': url, 'source': src} for url, src in ref_rows]
                                ref_vendors, _ref_products = parser.extract_from_references(ref_list)
                                for vn in ref_vendors:
                                    if isinstance(vn, str) and vn.strip():
                                        names.add(vn.strip())
                            except Exception:
                                pass
                        if cve_id and names:
                            cve_to_names[cve_id] = names
                            all_names.update(names)

                    if not cve_to_names:
                        continue

                    try:
                        existing_rows = session.query(Vendor.id, Vendor.name).all()
                        name_to_vendor = { (n or '').strip().lower(): (vid, n) for vid, n in existing_rows if n }
                    except Exception:
                        name_to_vendor = {}

                    to_create = []
                    for n in sorted(all_names):
                        key = (n or '').strip().lower()
                        if not key or key in name_to_vendor:
                            continue
                        to_create.append({'name': n})
                    if to_create:
                        try:
                            session.bulk_insert_mappings(Vendor, to_create)
                            session.flush()
                            stats['vendors_created'] += len(to_create)
                            new_rows = session.query(Vendor.id, Vendor.name).filter(Vendor.name.in_([x['name'] for x in to_create])).all()
                            for vid, nm in new_rows:
                                name_to_vendor[(nm or '').strip().lower()] = (vid, nm)
                        except Exception:
                            pass

                    try:
                        cve_ids = list(cve_to_names.keys())
                        if cve_ids:
                            session.query(CVEVendor).filter(CVEVendor.cve_id.in_(cve_ids)).delete(synchronize_session=False)
                    except Exception:
                        pass

                    to_link = []
                    for cve_id, names in cve_to_names.items():
                        for n in names:
                            key = (n or '').strip().lower()
                            vid = name_to_vendor.get(key, (None, None))[0]
                            if vid:
                                to_link.append({'cve_id': cve_id, 'vendor_id': vid})
                    if to_link:
                        try:
                            session.bulk_insert_mappings(CVEVendor, to_link)
                            stats['associations_created'] += len(to_link)
                        except Exception:
                            pass
                    stats['cves_processed'] += len(cve_to_names)

            return stats
        except Exception as e:
            logger.error(f"Erro no backfill de vendors: {e}")
            raise

    def backfill_products_from_vulnerabilities(self, session: Optional[Session] = None, batch_limit: int = 5000) -> Dict[str, int]:
        """
        Executa backfill das tabelas normalizadas de produtos e associações CVEProduct
        a partir dos campos JSON `vulnerabilities.nvd_version_ranges` (preferencial)
        com fallback para `nvd_products_data` pareado aos vendors presentes.

        Retorna estatísticas: {'products_created': X, 'associations_created': Y, 'cves_processed': Z, 'vendors_created': V}
        """
        if session is None:
            session = db.session
        stats = {'products_created': 0, 'associations_created': 0, 'cves_processed': 0, 'vendors_created': 0}
        try:
            from app.models.vendor import Vendor
            from app.models.product import Product
            from app.models.cve_product import CVEProduct
            from app.models.vulnerability import Vulnerability
            import json

            with self.bulk_transaction(session):
                offset = 0
                while True:
                    rows = (
                        session.query(
                            Vulnerability.cve_id,
                            Vulnerability.nvd_version_ranges,
                            Vulnerability.nvd_vendors_data,
                            Vulnerability.nvd_products_data,
                            Vulnerability.nvd_cpe_configurations,
                            Vulnerability.description,
                        )
                        .offset(offset)
                        .limit(batch_limit)
                        .all()
                    )
                    if not rows:
                        break
                    offset += len(rows)

                    # Mapear nomes de vendor -> id
                    try:
                        existing_vendors = session.query(Vendor.id, Vendor.name).all()
                        name_to_vendor = { (n or '').strip().lower(): (vid, n) for vid, n in existing_vendors if n }
                    except Exception:
                        name_to_vendor = {}

                    # Coleta de pares (vendor_name, product_name) por CVE
                    cve_pairs: Dict[str, set] = {}
                    unique_pairs: set = set()
                    # Também coletar todos vendor names e product names para criação
                    vendor_names_all: set = set()
                    from app.jobs.nvd_fetcher import EnhancedCPEParser
                    parser = EnhancedCPEParser()

                    for cve_id, ranges_json, vendors_json, products_json, cpe_json, description in rows:
                        pairs = set()
                        vendor_names = set()
                        product_names = set()

                        # Parse vendor names do campo vendors_json
                        try:
                            data = vendors_json
                            if isinstance(data, str):
                                try:
                                    data = json.loads(data)
                                except Exception:
                                    pass
                            if isinstance(data, list):
                                for v in data:
                                    if isinstance(v, str) and v.strip():
                                        vendor_names.add(v.strip())
                                    elif isinstance(v, dict):
                                        nm = v.get('name') or v.get('vendor') or v.get('vendor_name')
                                        if isinstance(nm, str) and nm.strip():
                                            vendor_names.add(nm.strip())
                            elif isinstance(data, dict):
                                vs = data.get('vendors')
                                if isinstance(vs, list):
                                    for v in vs:
                                        if isinstance(v, str) and v.strip():
                                            vendor_names.add(v.strip())
                                        elif isinstance(v, dict):
                                            nm = v.get('name') or v.get('vendor') or v.get('vendor_name')
                                            if isinstance(nm, str) and nm.strip():
                                                vendor_names.add(nm.strip())
                                elif isinstance(data.get('name'), str) and data.get('name').strip():
                                    vendor_names.add(data.get('name').strip())
                            elif isinstance(data, str) and data.strip():
                                vendor_names.add(data.strip())
                        except Exception:
                            pass

                        # Preferir pares vindos de nvd_version_ranges (já contém vendor/product)
                        try:
                            vr = ranges_json
                            if isinstance(vr, str):
                                try:
                                    vr = json.loads(vr)
                                except Exception:
                                    pass
                            if isinstance(vr, list):
                                for it in vr:
                                    if not isinstance(it, dict):
                                        continue
                                    vn = str(it.get('vendor') or '').strip()
                                    pn = str(it.get('product') or '').strip()
                                    if vn and pn:
                                        pairs.add((vn, pn))
                        except Exception:
                            pass

                        # Fallback: parear todos `nvd_products_data` com vendors disponíveis
                        if not pairs:
                            try:
                                pd = products_json
                                if isinstance(pd, str):
                                    try:
                                        pd = json.loads(pd)
                                    except Exception:
                                        pass
                                prod_names = []
                                if isinstance(pd, list):
                                    for p in pd:
                                        if isinstance(p, str) and p.strip():
                                            prod_names.append(p.strip())
                                        elif isinstance(p, dict):
                                            nm = p.get('name') or p.get('product') or p.get('product_name')
                                            if isinstance(nm, str) and nm.strip():
                                                prod_names.append(nm.strip())
                                elif isinstance(pd, dict):
                                    ps = pd.get('products')
                                    if isinstance(ps, list):
                                        for p in ps:
                                            if isinstance(p, str) and p.strip():
                                                prod_names.append(p.strip())
                                            elif isinstance(p, dict):
                                                nm = p.get('name') or p.get('product') or p.get('product_name')
                                                if isinstance(nm, str) and nm.strip():
                                                    prod_names.append(nm.strip())
                                    elif isinstance(pd.get('name'), str) and pd.get('name').strip():
                                        prod_names.append(pd.get('name').strip())
                                elif isinstance(pd, str) and pd.strip():
                                    prod_names.append(pd.strip())

                                # Parear cada produto com cada vendor conhecido do CVE
                                for vn in vendor_names:
                                    for pn in prod_names:
                                        if vn.strip() and pn.strip():
                                            pairs.add((vn.strip(), pn.strip()))
                            except Exception:
                                pass

                        # Fallback adicional: extrair pares de `nvd_cpe_configurations` completos
                        if not pairs:
                            try:
                                data = cpe_json
                                if isinstance(data, str):
                                    try:
                                        data = json.loads(data)
                                    except Exception:
                                        pass
                                if isinstance(data, list):
                                    for config in data:
                                        nodes = config.get('nodes', []) if isinstance(config, dict) else []
                                        for node in nodes:
                                            matches = node.get('cpeMatch', []) if isinstance(node, dict) else []
                                            for m in matches:
                                                cpe_uri = m.get('criteria') if isinstance(m, dict) else None
                                                if isinstance(cpe_uri, str) and cpe_uri.startswith('cpe:2.3:'):
                                                    parts = cpe_uri.split(':')
                                                    if len(parts) >= 5:
                                                        vn = parts[3]
                                                        pn = parts[4]
                                                        if vn and vn not in ('*','-') and pn and pn not in ('*','-'):
                                                            vn = vn.strip()
                                                            pn = pn.strip()
                                                            if vn and pn:
                                                                pairs.add((vn, pn))
                            except Exception:
                                pass

                        # Fallback final: extrair de descrição (vendors/products) e parear
                        if not pairs:
                            try:
                                desc_vendors = []
                                desc_products = []
                                if isinstance(description, str) and description.strip():
                                    dv, dp = parser.extract_from_description(description)
                                    desc_vendors = [x for x in dv if isinstance(x, str) and x.strip()]
                                    desc_products = [x for x in dp if isinstance(x, str) and x.strip()]
                                # Consolidar vendor names
                                for vn in desc_vendors:
                                    vendor_names.add(vn.strip())
                                # Parear todos produtos extraídos com vendors conhecidos
                                for vn in (vendor_names or set(desc_vendors)):
                                    for pn in (product_names or set(desc_products)):
                                        if vn.strip() and pn.strip():
                                            pairs.add((vn.strip(), pn.strip()))
                            except Exception:
                                pass

                    if cve_id and pairs:
                        cve_pairs[cve_id] = pairs
                        unique_pairs.update(pairs)
                        vendor_names_all.update({vn.strip() for vn in vendor_names if vn and vn.strip()})

                    # Criar vendors ausentes
                    to_create_vendors = []
                    for vn in sorted(vendor_names_all):
                        key = (vn or '').strip().lower()
                        if not key or key in name_to_vendor:
                            continue
                        to_create_vendors.append({'name': vn})
                    if to_create_vendors:
                        try:
                            session.bulk_insert_mappings(Vendor, to_create_vendors)
                            session.flush()
                            stats['vendors_created'] += len(to_create_vendors)
                            new_rows = session.query(Vendor.id, Vendor.name).filter(
                                Vendor.name.in_([x['name'] for x in to_create_vendors])
                            ).all()
                            for vid, nm in new_rows:
                                name_to_vendor[(nm or '').strip().lower()] = (vid, nm)
                        except Exception:
                            pass

                    # Mapear par (vendor_id, product_name_lower) -> product_id
                    try:
                        existing_products = session.query(Product.id, Product.vendor_id, Product.name).all()
                        key_to_product = {}
                        for pid, vid, nm in existing_products:
                            key_to_product[(int(vid) if vid is not None else None, (nm or '').strip().lower())] = (pid, nm)
                    except Exception:
                        key_to_product = {}

                    # Criar produtos ausentes
                    to_create_products = []
                    for vn, pn in sorted(unique_pairs):
                        vkey = (vn or '').strip().lower()
                        pkey = (pn or '').strip().lower()
                        if not vkey or not pkey:
                            continue
                        vid = name_to_vendor.get(vkey, (None, None))[0]
                        if not vid:
                            continue
                        if (vid, pkey) in key_to_product:
                            continue
                        to_create_products.append({'vendor_id': int(vid), 'name': pn})
                    if to_create_products:
                        try:
                            session.bulk_insert_mappings(Product, to_create_products)
                            session.flush()
                            stats['products_created'] += len(to_create_products)
                            new_rows = session.query(Product.id, Product.vendor_id, Product.name).filter(
                                Product.name.in_([x['name'] for x in to_create_products])
                            ).all()
                            for pid, vid, nm in new_rows:
                                key_to_product[(int(vid) if vid is not None else None, (nm or '').strip().lower())] = (pid, nm)
                        except Exception:
                            pass

                    # Remover associações existentes para estes CVEs e recriar
                    try:
                        cve_ids = list(cve_pairs.keys())
                        if cve_ids:
                            session.query(CVEProduct).filter(CVEProduct.cve_id.in_(cve_ids)).delete(synchronize_session=False)
                    except Exception:
                        pass

                    # Criar ligações CVEProduct
                    to_link = []
                    for cve_id, pairs in cve_pairs.items():
                        for vn, pn in pairs:
                            vkey = (vn or '').strip().lower()
                            pkey = (pn or '').strip().lower()
                            vid = name_to_vendor.get(vkey, (None, None))[0]
                            if not vid:
                                continue
                            pid = key_to_product.get((int(vid), pkey), (None, None))[0]
                            if pid:
                                to_link.append({'cve_id': cve_id, 'product_id': int(pid)})
                    if to_link:
                        try:
                            session.bulk_insert_mappings(CVEProduct, to_link)
                            stats['associations_created'] += len(to_link)
                        except Exception:
                            pass
                    stats['cves_processed'] += len(cve_pairs)

            return stats
        except Exception as e:
            logger.error(f"Erro no backfill de produtos: {e}")
            raise

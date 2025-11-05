import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.sync_metadata import SyncMetadata

logger = logging.getLogger(__name__)


def upsert_sync_metadata(
    session: Optional[Session],
    key: str,
    value: Optional[str] = None,
    status: Optional[str] = None,
    sync_type: Optional[str] = None,
    last_modified: Optional[datetime] = None,
) -> Tuple[bool, Optional[SyncMetadata]]:
    """
    Upsert de metadados de sincronização utilizando ORM/dialetos do SQLAlchemy.

    - Usa ON CONFLICT/ON DUPLICATE KEY quando suportado pelo dialeto.
    - Faz fallback para get/update ou insert se o dialeto não suportar nativamente.

    Retorna (sucesso, instancia_atualizada_ou_criada).
    """
    sess: Session = session or db.session

    try:
        # Resolver dialeto de forma robusta em Flask-SQLAlchemy >=3
        engine = None
        try:
            # Preferir get_bind quando disponível
            if hasattr(sess, 'get_bind'):
                engine = sess.get_bind()
            else:
                engine = getattr(sess, 'bind', None)
        except Exception:
            engine = getattr(sess, 'bind', None)

        if engine is None:
            try:
                engine = db.session.get_bind()
            except Exception:
                engine = getattr(db, 'engine', None)

        if engine is None:
            raise RuntimeError("Não foi possível resolver engine/bind para sessão do SQLAlchemy")

        dialect_name = engine.dialect.name
        now_dt = last_modified or datetime.utcnow()
        # Limitar tamanho de value/status para evitar erros em colunas pequenas
        safe_value = (value or '').strip()
        if len(safe_value) > 255:
            safe_value = safe_value[:252] + '...'
        safe_status = (status or '').strip() or None
        safe_sync_type = (sync_type or '').strip() or None

        if dialect_name in ("sqlite", "postgresql"):
            # Usa insert().on_conflict_do_update
            try:
                if dialect_name == "sqlite":
                    from sqlalchemy.dialects.sqlite import insert as dialect_insert
                else:
                    from sqlalchemy.dialects.postgresql import insert as dialect_insert

                ins = dialect_insert(SyncMetadata.__table__).values(
                    key=key,
                    value=safe_value or None,
                    status=safe_status,
                    last_modified=now_dt,
                    sync_type=safe_sync_type,
                )
                upsert_stmt = ins.on_conflict_do_update(
                    index_elements=[SyncMetadata.key],
                    set_={
                        'value': ins.excluded.value,
                        'status': ins.excluded.status,
                        'last_modified': ins.excluded.last_modified,
                        'sync_type': ins.excluded.sync_type,
                    },
                )
                sess.execute(upsert_stmt)
                # Busca instância atualizada
                instance = sess.execute(
                    select(SyncMetadata).where(SyncMetadata.key == key)
                ).scalar_one_or_none()
                return True, instance
            except Exception as e:
                logger.debug(f"Upsert dialético falhou ({dialect_name}); aplicando fallback ORM. Erro: {e}")
                # Fallback para lógica ORM abaixo

        elif dialect_name == "mysql":
            # Usa on_duplicate_key_update
            try:
                from sqlalchemy.dialects.mysql import insert as dialect_insert
                ins = dialect_insert(SyncMetadata.__table__).values(
                    key=key,
                    value=safe_value or None,
                    status=safe_status,
                    last_modified=now_dt,
                    sync_type=safe_sync_type,
                )
                upsert_stmt = ins.on_duplicate_key_update(
                    value=ins.inserted.value,
                    status=ins.inserted.status,
                    last_modified=ins.inserted.last_modified,
                    sync_type=ins.inserted.sync_type,
                )
                sess.execute(upsert_stmt)
                instance = sess.execute(
                    select(SyncMetadata).where(SyncMetadata.key == key)
                ).scalar_one_or_none()
                return True, instance
            except Exception as e:
                logger.debug(f"Upsert MySQL falhou; aplicando fallback ORM. Erro: {e}")
                # Fallback para lógica ORM abaixo

        # Fallback genérico via ORM (get/update ou insert)
        instance = sess.execute(
            select(SyncMetadata).where(SyncMetadata.key == key)
        ).scalar_one_or_none()
        if instance:
            instance.value = safe_value or instance.value
            instance.status = safe_status or instance.status
            instance.last_modified = now_dt
            instance.sync_type = safe_sync_type or instance.sync_type
        else:
            instance = SyncMetadata(
                key=key,
                value=safe_value or None,
                status=safe_status,
                last_modified=now_dt,
                sync_type=safe_sync_type,
            )
            sess.add(instance)

        return True, instance
    except Exception as e:
        logger.error(f"Falha no upsert de SyncMetadata(key={key}): {e}", exc_info=True)
        return False, None


def get_last_sync_info(session: Optional[Session] = None) -> Optional[SyncMetadata]:
    """Obtém o registro de última sincronização ('nvd_last_sync') se existir."""
    sess: Session = session or db.session
    try:
        return sess.execute(
            select(SyncMetadata).where(SyncMetadata.key == 'nvd_last_sync')
        ).scalar_one_or_none()
    except Exception as e:
        logger.warning(f"Erro ao buscar última sincronização: {e}")
        return None
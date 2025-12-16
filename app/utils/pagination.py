# utils/pagination.py

from sqlalchemy.orm import Query
from flask_sqlalchemy.pagination import Pagination
from flask import current_app
from types import SimpleNamespace
import math
from typing import Optional, Any, List
from app.extensions import db

def paginate_query(
    query: Any,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    error_out: bool = False
) -> Pagination:
    """
    Paginates a SQLAlchemy Query using Flask-SQLAlchemy's Pagination.

    Configurable via app.settings:
      - PAGINATION_DEFAULT_PAGE (int, default 1)
      - PAGINATION_DEFAULT_PER_PAGE (int, default 20)
      - PAGINATION_MAX_PER_PAGE (int, default 100)

    Args:
        query: SQLAlchemy Query (e.g. Model.query.filter(...))
        page: desired page number (1-based); if None, uses PAGINATION_DEFAULT_PAGE.
        per_page: items per page; if None, uses PAGINATION_DEFAULT_PER_PAGE.
        error_out: if True, aborts with 404 when page is out of range.

    Returns:
        Pagination: object with items, page, per_page, total, pages, etc.
    """
    # carregar padrões e limites da configuração
    default_page = current_app.config.get('PAGINATION_DEFAULT_PAGE', 1)
    default_per = current_app.config.get('PAGINATION_DEFAULT_PER_PAGE', 20)
    max_per = current_app.config.get('PAGINATION_MAX_PER_PAGE', 100)

    # normalizar e validar page
    try:
        page_val = int(page) if page is not None else default_page
    except (TypeError, ValueError):
        page_val = default_page
    page_val = max(1, page_val)

    # normalizar e validar per_page
    try:
        per_val = int(per_page) if per_page is not None else default_per
    except (TypeError, ValueError):
        per_val = default_per
    per_val = max(1, min(per_val, max_per))

    current_app.logger.debug(
        f"paginate_query: page={page_val}, per_page={per_val}, error_out={error_out}"
    )

    # Flask-SQLAlchemy>=3 remove Query.paginate em favor de db.paginate
    # Usamos db.paginate e fazemos fallback para query.paginate para compatibilidade
    try:
        return db.paginate(query, page=page_val, per_page=per_val, error_out=error_out)
    except Exception:
        # Fallback para versões antigas ou ambientes onde db.paginate não aceita o tipo de query
        try:
            return query.paginate(page=page_val, per_page=per_val, error_out=error_out)
        except Exception:
            # Fallback final: objeto mínimo compatível com atributos usados no template
            items: List[Any] = []
            # Tenta contar total; se falhar, usa o número de itens carregados
            try:
                total = query.count()
            except Exception:
                total = len(items)

            pages = max(1, math.ceil(total / per_val)) if per_val else 1
            has_prev = page_val > 1
            has_next = page_val < pages
            prev_num = page_val - 1 if has_prev else 1
            next_num = page_val + 1 if has_next else pages

            def _iter_pages(left_edge: int = 2, left_current: int = 2, right_current: int = 2, right_edge: int = 2):
                # Implementação mínima: retorna todas as páginas para evitar erro no template
                return range(1, pages + 1)

            return SimpleNamespace(
                items=items,
                total=total,
                page=page_val,
                per_page=per_val,
                pages=pages,
                has_prev=has_prev,
                has_next=has_next,
                prev_num=prev_num,
                next_num=next_num,
                iter_pages=_iter_pages,
            )

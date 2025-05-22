# utils/pagination.py

from sqlalchemy.orm import Query
from flask_sqlalchemy.pagination import Pagination
from flask import current_app
from typing import Optional

def paginate_query(
    query: Query,
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

    return query.paginate(page=page_val, per_page=per_val, error_out=error_out)

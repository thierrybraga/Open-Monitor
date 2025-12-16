import os
import pickle
import threading
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class NewsCacheService:
    """
    Cache persistente para notícias agregadas.

    - Mantém itens por fonte e categoria em disco (pickle) e em memória.
    - Garante deduplicação por `link` (fallback por `title`).
    - Fornece agregação ordenada por `published_at`.
    """

    _store_file: str = os.path.join('app', 'cache', 'news_store.pkl')
    _json_feed_file: str = os.path.join('app', 'cache', 'news_feed.json')
    _lock = threading.Lock()
    _store: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    _max_per_category: int = 500

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._store:
            return
        with cls._lock:
            if cls._store:
                return
            try:
                if os.path.exists(cls._store_file):
                    with open(cls._store_file, 'rb') as f:
                        data = pickle.load(f) or {}
                        # Estrutura esperada: {source: {category: [items]}}
                        if isinstance(data, dict):
                            cls._store = data
                        else:
                            cls._store = {}
                else:
                    cls._store = {}
            except Exception as e:
                logger.warning(f"Falha ao carregar cache de notícias: {e}")
                cls._store = {}

    @classmethod
    def _save(cls) -> None:
        with cls._lock:
            try:
                os.makedirs(os.path.dirname(cls._store_file), exist_ok=True)
                with open(cls._store_file, 'wb') as f:
                    pickle.dump(cls._store, f)
            except Exception as e:
                logger.warning(f"Falha ao salvar cache de notícias: {e}")

    @classmethod
    def add_items(
        cls,
        source: str,
        category: str,
        items: List[Dict[str, Any]],
        max_per_category: Optional[int] = None,
    ) -> int:
        """
        Adiciona itens à store persistente com deduplicação.

        Retorna quantidade de novos itens de fato adicionados.
        """
        cls._ensure_loaded()
        added = 0
        with cls._lock:
            store_source = cls._store.setdefault(source, {})
            bucket = store_source.setdefault(category, [])

            # Índices de dedupe
            seen_links = {it.get('link') for it in bucket if it.get('link')}
            seen_titles = {it.get('title') for it in bucket if it.get('title')}

            for item in items:
                lk = item.get('link')
                tt = item.get('title')
                if lk and lk in seen_links:
                    continue
                if tt and tt in seen_titles:
                    continue
                # manter published_at como datetime; se string, tenta parse simples
                pa = item.get('published_at')
                if isinstance(pa, str):
                    try:
                        item['published_at'] = datetime.fromisoformat(pa)
                    except Exception:
                        pass
                bucket.append(item)
                if lk:
                    seen_links.add(lk)
                if tt:
                    seen_titles.add(tt)
                added += 1

            # Ordenar por data e truncar
            try:
                bucket.sort(key=lambda i: i.get('published_at') or datetime.min, reverse=True)
            except Exception:
                pass
            limit = max_per_category or cls._max_per_category
            if len(bucket) > limit:
                del bucket[limit:]

        if added:
            cls._save()
        return added

    @classmethod
    def get_aggregated(
        cls,
        source_filter: Optional[str] = None,
        categories: Optional[List[str]] = None,
        limit: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Retorna itens agregados por fonte/categorias, ordenados por `published_at`.
        """
        cls._ensure_loaded()

        items: List[Dict[str, Any]] = []
        with cls._lock:
            sources = [source_filter] if source_filter else list(cls._store.keys())
            for src in sources:
                cat_map = cls._store.get(src, {})
                if categories:
                    cats = categories
                else:
                    cats = list(cat_map.keys())
                for c in cats:
                    items.extend(cat_map.get(c, []))

        try:
            items.sort(key=lambda i: i.get('published_at') or datetime.min, reverse=True)
        except Exception:
            pass
        return items[:limit]

    @classmethod
    def save_json_feed(cls, items: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> str:
        try:
            try:
                items_sorted = sorted(
                    items,
                    key=lambda i: i.get('published_at') or datetime.min
                )
            except Exception:
                items_sorted = items
            serializable: List[Dict[str, Any]] = []
            for it in items_sorted:
                d = dict(it)
                pa = d.get('published_at')
                if isinstance(pa, datetime):
                    if getattr(pa, 'tzinfo', None) is None:
                        pa = pa.replace(tzinfo=timezone.utc)
                    d['published_at'] = pa.isoformat()
                serializable.append(d)
            payload = {
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'sources': sources or [],
                'items': serializable,
            }
            path = Path(cls._json_feed_file)
            os.makedirs(str(path.parent), exist_ok=True)
            with open(str(path), 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False)
            return str(path)
        except Exception as e:
            logger.warning(f"Falha ao salvar feed JSON: {e}")
            return ''

    @classmethod
    def load_json_feed(cls) -> Dict[str, Any]:
        try:
            path = Path(cls._json_feed_file)
            if not path.exists():
                return {'items': [], 'sources': [], 'updated_at': None}
            with open(str(path), 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
            return data if isinstance(data, dict) else {'items': [], 'sources': [], 'updated_at': None}
        except Exception as e:
            logger.warning(f"Falha ao carregar feed JSON: {e}")
            return {'items': [], 'sources': [], 'updated_at': None}

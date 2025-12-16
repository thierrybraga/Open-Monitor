import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import os
import pickle
import threading
from app.services.tagging_service import TaggingService

logger = logging.getLogger(__name__)


class RSSFeedService:
    """Serviço para coletar notícias de feeds RSS e normalizar para o schema da aplicação.

    Saída normalizada:
    {title, summary, source, published_at, tags, link}
    """

    _cache: Dict[str, Dict] = {}
    _ttl_seconds: int = 1800  # 30 minutos
    _disk_cache_file: str = os.path.join('app', 'cache', 'rss_cache.pkl')
    _feed_meta_file: str = os.path.join('app', 'cache', 'rss_meta.pkl')

    @classmethod
    def _now(cls) -> datetime:
        try:
            from datetime import UTC
            return datetime.now(UTC)
        except Exception:
            from datetime import timezone
            return datetime.now(timezone.utc)

    @staticmethod
    def _extract_source(url: Optional[str]) -> str:
        if not url:
            return ""
        try:
            netloc = urlparse(url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    @staticmethod
    def _parse_rss_datetime(text: Optional[str], fallback: datetime) -> datetime:
        if not text:
            return fallback
        # Tenta formatos comuns de RSS/Atom
        fmts = [
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC822 ex: Tue, 10 Sep 2024 07:00:00 GMT
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%SZ",        # ISO8601 UTC
            "%Y-%m-%dT%H:%M:%S%z",       # ISO8601 com timezone
        ]
        for fmt in fmts:
            try:
                return datetime.strptime(text.strip(), fmt)
            except Exception:
                continue
        return fallback

    @classmethod
    def _from_cache(cls, key: str) -> Optional[List[Dict]]:
        try:
            entry = cls._cache.get(key)
            if not entry:
                # Tentar carregar do disco
                disk_entry = cls._from_disk_cache(key)
                if disk_entry:
                    return disk_entry.get("items") or None
                return None
            ts = entry.get("ts")
            if not ts or (cls._now() - ts).total_seconds() > cls._ttl_seconds:
                return None
            return entry.get("items") or None
        except Exception:
            return None

    @classmethod
    def _from_cache_allow_stale(cls, key: str) -> Optional[List[Dict]]:
        """Obtém itens do cache mesmo se expirados (stale)."""
        try:
            entry = cls._cache.get(key)
            if entry and entry.get("items"):
                return entry.get("items") or None
            # Disco sem validar TTL
            if os.path.exists(cls._disk_cache_file):
                try:
                    with open(cls._disk_cache_file, 'rb') as f:
                        data = pickle.load(f) or {}
                    disk_entry = data.get(key)
                    if disk_entry:
                        return disk_entry.get("items") or None
                except Exception:
                    return None
            return None
        except Exception:
            return None

    @classmethod
    def _save_cache(cls, key: str, items: List[Dict]) -> None:
        try:
            cls._cache[key] = {"ts": cls._now(), "items": items}
        except Exception:
            pass

        # Salvar em disco
        try:
            os.makedirs(os.path.dirname(cls._disk_cache_file), exist_ok=True)
            data = {}
            if os.path.exists(cls._disk_cache_file):
                try:
                    with open(cls._disk_cache_file, 'rb') as f:
                        data = pickle.load(f) or {}
                except Exception:
                    data = {}
            data[key] = {"ts": cls._now(), "items": items}
            with open(cls._disk_cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            pass

    @classmethod
    def _from_disk_cache(cls, key: str) -> Optional[Dict]:
        try:
            if not os.path.exists(cls._disk_cache_file):
                return None
            with open(cls._disk_cache_file, 'rb') as f:
                data = pickle.load(f) or {}
            entry = data.get(key)
            if not entry:
                return None
            ts = entry.get("ts")
            if not ts or (cls._now() - ts).total_seconds() > cls._ttl_seconds:
                return None
            return entry
        except Exception:
            return None

    @classmethod
    def _load_feed_meta(cls) -> Dict[str, Dict[str, str]]:
        try:
            if not os.path.exists(cls._feed_meta_file):
                return {}
            with open(cls._feed_meta_file, 'rb') as f:
                data = pickle.load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _save_feed_meta(cls, meta: Dict[str, Dict[str, str]]) -> None:
        try:
            os.makedirs(os.path.dirname(cls._feed_meta_file), exist_ok=True)
            with open(cls._feed_meta_file, 'wb') as f:
                pickle.dump(meta, f)
        except Exception:
            pass

    @classmethod
    def get_news(cls, limit: int = 60, feeds: Optional[List[Dict[str, str]]] = None) -> List[Dict]:
        """Coleta itens de múltiplos feeds RSS populares e normaliza.

        Parâmetro `feeds` aceita uma lista de dicts com chaves:
        - url: URL do feed
        - tag: tag básica para classificação (ex.: 'rss')

        Retorna lista de itens normalizados.
        """
        default_feeds = [
            {"url": "https://feeds.feedburner.com/TheHackersNews", "tag": "rss"},
            {"url": "https://krebsonsecurity.com/feed/", "tag": "rss"},
            {"url": "https://www.bleepingcomputer.com/feed/", "tag": "rss"},
            {"url": "https://www.darkreading.com/rss.xml", "tag": "rss"},
        ]
        feed_list = feeds or default_feeds

        key = f"rss|limit:{limit}|feeds:{len(feed_list)}"
        cached = cls._from_cache(key)
        if cached is not None:
            return cached[:limit]

        aggregated: List[Dict] = []
        fallback_time = cls._now()

        feed_meta = cls._load_feed_meta()

        for idx, f in enumerate(feed_list):
            url = f.get("url")
            base_tag = f.get("tag") or "rss"
            if not url:
                continue
            try:
                # Conditional GET com Last-Modified/ETag se disponível
                headers = {}
                meta = feed_meta.get(url) or {}
                if meta.get('last_modified'):
                    headers['If-Modified-Since'] = meta['last_modified']
                if meta.get('etag'):
                    headers['If-None-Match'] = meta['etag']
                req = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        content = resp.read()
                        info = resp.info()
                        last_modified = info.get('Last-Modified')
                        etag = info.get('ETag')
                        if last_modified:
                            meta['last_modified'] = last_modified
                        if etag:
                            meta['etag'] = etag
                        if meta:
                            feed_meta[url] = meta
                    root = ET.fromstring(content)
                except urllib.error.HTTPError as he:
                    if he.code == 304:
                        # Não modificado: pular este feed (usaremos itens anteriores no agregado)
                        logger.info(f"RSS não modificado (304): {url}")
                        continue
                    raise he
            except Exception as e:
                logger.warning(f"Falha ao obter/parsing RSS '{url}': {e}")
                continue

            # Suporte a RSS (<channel><item>) e Atom (<entry>)
            items = []
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
            else:
                items = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")

            for i, node in enumerate(items):
                try:
                    title = None
                    link = None
                    summary = None
                    pub = None
                    raw_tags = []

                    # RSS item
                    title_el = node.find("title")
                    link_el = node.find("link")
                    desc_el = node.find("description")
                    pub_el = node.find("pubDate")

                    # Atom fallback
                    if title_el is None:
                        title_el = node.find("{http://www.w3.org/2005/Atom}title")
                    if link_el is None:
                        link_el = node.find("{http://www.w3.org/2005/Atom}link")
                    if desc_el is None:
                        desc_el = node.find("{http://www.w3.org/2005/Atom}summary")
                    if pub_el is None:
                        pub_el = node.find("{http://www.w3.org/2005/Atom}updated")

                    # RSS categories
                    for cat_el in node.findall("category"):
                        txt = (cat_el.text or "").strip()
                        if txt:
                            raw_tags.append(txt)
                    # Atom categories
                    for cat_el in node.findall("{http://www.w3.org/2005/Atom}category"):
                        term = (cat_el.get("term") or "").strip()
                        label = (cat_el.get("label") or "").strip()
                        for v in [term, label]:
                            if v:
                                raw_tags.append(v)

                    title = (title_el.text or "").strip() if title_el is not None else ""
                    # Atom link pode estar no atributo href
                    if link_el is not None and link_el.get("href"):
                        link = (link_el.get("href") or "").strip()
                    else:
                        link = (link_el.text or "").strip() if link_el is not None else ""

                    summary = (desc_el.text or "").strip() if desc_el is not None else ""
                    pub_text = (pub_el.text or "").strip() if pub_el is not None else None
                    published_at = cls._parse_rss_datetime(pub_text, fallback=fallback_time - timedelta(minutes=i + idx * 5))

                    source = cls._extract_source(link)
                    tags = TaggingService.enrich_tags([base_tag] + raw_tags, title=title, summary=summary, source=source)

                    item = {
                        "title": title,
                        "summary": summary,
                        "source": source,
                        "published_at": published_at,
                        "tags": tags,
                        "link": link,
                    }
                    if not item["title"] or not item["link"]:
                        continue
                    aggregated.append(item)
                except Exception:
                    continue

        # Dedup por link/título
        seen_links = set()
        seen_titles = set()
        deduped: List[Dict] = []
        for it in aggregated:
            lk = it.get("link")
            tt = it.get("title")
            if lk and lk in seen_links:
                continue
            if tt and tt in seen_titles:
                continue
            if lk:
                seen_links.add(lk)
            if tt:
                seen_titles.add(tt)
            deduped.append(it)

        try:
            deduped.sort(key=lambda i: i.get("published_at"), reverse=True)
        except Exception:
            pass

        # Persistir meta de feeds (ETag/Last-Modified)
        try:
            cls._save_feed_meta(feed_meta)
        except Exception:
            pass

        cls._save_cache(key, deduped)
        return deduped[:limit]

    @classmethod
    def _refresh_cache_in_background(cls, limit: int, feeds: Optional[List[Dict[str, str]]]) -> None:
        def _task():
            try:
                cls.get_news(limit=limit, feeds=feeds)
            except Exception:
                pass
        try:
            t = threading.Thread(target=_task, daemon=True)
            t.start()
        except Exception:
            pass

    @classmethod
    def get_news_fast(cls, limit: int = 60, feeds: Optional[List[Dict[str, str]]] = None, allow_stale: bool = True) -> List[Dict]:
        """Retorna itens rapidamente usando stale-while-revalidate para RSS.

        - Cache válido: retorna imediatamente.
        - Cache expirado: retorna stale e atualiza em background.
        - Sem cache: faz fetch normal.
        """
        default_feeds = [
            {"url": "https://feeds.feedburner.com/TheHackersNews", "tag": "rss"},
            {"url": "https://krebsonsecurity.com/feed/", "tag": "rss"},
            {"url": "https://www.bleepingcomputer.com/feed/", "tag": "rss"},
            {"url": "https://www.darkreading.com/rss.xml", "tag": "rss"},
        ]
        feed_list = feeds or default_feeds
        key = f"rss|limit:{limit}|feeds:{len(feed_list)}"

        fresh = cls._from_cache(key)
        if fresh is not None:
            return fresh[:limit]

        if allow_stale:
            stale = cls._from_cache_allow_stale(key)
            if stale is not None and len(stale) > 0:
                cls._refresh_cache_in_background(limit=limit, feeds=feed_list)
                return stale[:limit]

        return cls.get_news(limit=limit, feeds=feed_list)
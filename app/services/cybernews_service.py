import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse
import os
import pickle

logger = logging.getLogger(__name__)


class CyberNewsService:
    """Service to fetch cybersecurity news using the CyberNews Python package.

    This wraps the third-party library and normalizes output to the app's schema:
    {title, summary, source, published_at, tags, link}
    """

    # Simple in-memory cache to avoid frequent external calls
    _cache: Dict[str, Dict] = {}
    _ttl_seconds: int = 3600  # 1 hour to align with hourly refresh
    _disk_cache_file: str = os.path.join('app', 'cache', 'cybernews_cache.pkl')

    @classmethod
    def _now(cls) -> datetime:
        return datetime.utcnow()

    @classmethod
    def _cache_key(cls, categories: Optional[List[str]], limit: int) -> str:
        cats = ",".join(sorted(categories or []))
        return f"cats:{cats}|limit:{limit}"

    @classmethod
    def _from_cache(cls, key: str) -> Optional[List[Dict]]:
        try:
            entry = cls._cache.get(key)
            if not entry:
                # Tentar carregar do disco se não estiver em memória
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
    def _save_cache(cls, key: str, items: List[Dict]) -> None:
        try:
            cls._cache[key] = {"ts": cls._now(), "items": items}
            cls._save_disk_cache(key, items)
        except Exception:
            pass

    @classmethod
    def _from_disk_cache(cls, key: str) -> Optional[Dict]:
        try:
            if not os.path.exists(cls._disk_cache_file):
                return None
            with open(cls._disk_cache_file, 'rb') as f:
                data = pickle.load(f)
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
    def _save_disk_cache(cls, key: str, items: List[Dict]) -> None:
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
    def _absolute_link(link: str, source: str) -> str:
        """Ensure link is absolute; if relative and source provided, build https URL.

        This is a pragmatic fix for providers that return paths like "/news/...".
        If source is not a hostname, choose host by path or fall back to ET.
        """
        try:
            if not link:
                return ""
            if link.startswith("http://") or link.startswith("https://"):
                return link
            if link.startswith("/"):
                host = source if (source and "." in source and source.lower() != "n/a") else CyberNewsService._choose_host_for_path(link)
                return f"https://{host}{link}"
        except Exception:
            pass
        return ""

    @staticmethod
    def _choose_host_for_path(path: str) -> str:
        """Heurística para escolher subdomínio ET com base no caminho.

        - /news/internet -> telecom.economictimes.indiatimes.com
        - /news/next-gen-technologies, /news/security -> ciosea.economictimes.indiatimes.com
        - /news/cybercrime-fraud, /news/data-breaches, /news/vulnerabilities-exploits -> ciso.economictimes.indiatimes.com
        - fallback -> economictimes.indiatimes.com
        """
        try:
            p = (path or '').lower()
            if p.startswith('/news/internet'):
                return 'telecom.economictimes.indiatimes.com'
            if p.startswith('/news/next-gen-technologies') or p.startswith('/news/security'):
                return 'ciosea.economictimes.indiatimes.com'
            if p.startswith('/news/cybercrime-fraud') or p.startswith('/news/data-breaches') or p.startswith('/news/vulnerabilities-exploits'):
                return 'ciso.economictimes.indiatimes.com'
        except Exception:
            pass
        return 'economictimes.indiatimes.com'

    @staticmethod
    def _parse_date(date_str: Optional[str], fallback: datetime) -> datetime:
        if not date_str:
            return fallback
        # Try a few common formats; if it fails, return fallback
        fmts = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d %b %Y",
            "%b %d, %Y",
        ]
        for fmt in fmts:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except Exception:
                continue
        return fallback

    @classmethod
    def get_news(cls, limit: int = 60, categories: Optional[List[str]] = None) -> List[Dict]:
        """Fetch and normalize news items from CyberNews.

        Args:
            limit: Max number of items to return after aggregation and sorting.
            categories: Optional list of categories to query. If None, use defaults.

        Returns:
            List of normalized news items.
        """
        try:
            from cybernews.cybernews import CyberNews  # type: ignore
        except Exception as e:
            logger.error(f"CyberNews package not available: {e}")
            return []

        try:
            default_categories = [
                "general",
                "security",
                "malware",
                "cyberAttack",
                "dataBreach",
                # Some versions of the package reference a misspelling; include both for safety
                "vulnerability",
                "vulenrability",
            ]
            cats = categories or default_categories

            news = CyberNews()

            aggregated: List[Dict] = []
            fallback_time = cls._now()

            # Cache check
            key = cls._cache_key(cats, limit)
            cached = cls._from_cache(key)
            if cached is not None:
                return cached[:limit]

            for idx, cat in enumerate(cats):
                try:
                    raw_items = news.get_news(cat) or []
                except Exception as e:
                    logger.warning(f"Failed to fetch category '{cat}': {e}")
                    raw_items = []

                for i, r in enumerate(raw_items):
                    # Normalize common field names across sources
                    title = str(
                        r.get("title")
                        or r.get("headline")
                        or r.get("headlines")
                        or ""
                    ).strip()
                    link = str(
                        r.get("article_url")
                        or r.get("url")
                        or r.get("newsURL")
                        or ""
                    ).strip()
                    summary = str(
                        r.get("description")
                        or r.get("summary")
                        or r.get("short")
                        or r.get("fullNews")
                        or ""
                    ).strip()
                    # Determine source domain sensibly:
                    # - Prefer explicit domain if provided in 'source'
                    # - If link is absolute, extract its domain
                    # - Otherwise, use a pragmatic default host for ET B2B
                    raw_source = str(r.get("source") or "").strip()
                    if raw_source and "." in raw_source:
                        source = raw_source
                    else:
                        source = cls._extract_source(link) or ""
                    date_str = (
                        r.get("date")
                        or r.get("published")
                        or r.get("published_at")
                        or r.get("newsDate")
                    )
                    published_at = cls._parse_date(date_str if isinstance(date_str, str) else None,
                                                  fallback=fallback_time - timedelta(minutes=i + idx * 5))

                    # Enforce absolute link when possible
                    link = cls._absolute_link(link, source)
                    if not source:
                        source = cls._extract_source(link) or "economictimes.indiatimes.com"

                    item = {
                        "title": title,
                        "summary": summary,
                        "source": source,
                        "published_at": published_at,
                        "tags": [cat],
                        "link": link,
                    }
                    # Skip invalid titles or links. Prefer absolute URLs to avoid broken anchors.
                    if not item["title"] or not item["link"]:
                        continue
                    aggregated.append(item)

            # Deduplicate by link then title
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

            # Sort newest first by published_at
            try:
                deduped.sort(key=lambda i: i.get("published_at"), reverse=True)
            except Exception:
                pass

            # Save cache and return limited slice
            cls._save_cache(key, deduped)
            return deduped[:limit]

        except Exception as e:
            logger.error(f"Error fetching CyberNews data: {e}")
            return []
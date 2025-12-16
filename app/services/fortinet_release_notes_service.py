import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import urllib.request
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class FortinetReleaseNotesService:
    """Coletor de notas de release do Fortinet FortiGate.

    Expande o suporte para múltiplas versões (7.0/7.2/7.4) e tenta extrair
    datas reais das páginas de documentos específicas quando disponível.

    Schema dos itens:
    {title, summary, source, published_at, tags, link}

    Observações:
    - O site não expõe RSS oficial; usamos parsing HTML básico tolerante.
    - Em caso de indisponibilidade de metadados de data, aplica fallback relativo.
    - O parser evita exceções — em falha retorna lista vazia.
    """

    PRODUCT_BASE_URL: str = "https://docs.fortinet.com/product/fortigate/{version}"

    @staticmethod
    def _extract_domain(url: Optional[str]) -> str:
        if not url:
            return ""
        try:
            netloc = urlparse(url).netloc.lower()
            return netloc[4:] if netloc.startswith("www.") else netloc
        except Exception:
            return ""

    @staticmethod
    def _safe_get(url: str, timeout: int = 10) -> Optional[str]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

    @classmethod
    def _extract_date_from_document(cls, url: str) -> Optional[datetime]:
        """Tenta extrair uma data real da página de documento.

        Heurísticas usadas:
        - JSON-LD com "datePublished" ou "dateModified"
        - meta tags: article:published_time, itemprop datePublished, name="date"
        - padrões textuais: "Published", "Release date", "Last updated" seguidos de data
        """
        html = cls._safe_get(url)
        if not html:
            return None

        # JSON-LD
        try:
            jsonld_blocks = re.findall(r"<script[^>]+type=\"application/ld\+json\"[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
            for block in jsonld_blocks:
                # Buscar chaves comuns
                for key in ("datePublished", "dateModified"):
                    m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', block)
                    if m:
                        dt = cls._parse_date_string(m.group(1))
                        if dt:
                            return dt
        except Exception:
            pass

        # Meta tags
        meta_patterns = [
            r"<meta[^>]+property=\"article:published_time\"[^>]+content=\"([^\"]+)\"",
            r"<meta[^>]+itemprop=\"datePublished\"[^>]+content=\"([^\"]+)\"",
            r"<meta[^>]+name=\"date\"[^>]+content=\"([^\"]+)\"",
            r"<time[^>]+datetime=\"([^\"]+)\"",
        ]
        try:
            for pat in meta_patterns:
                m = re.search(pat, html, flags=re.IGNORECASE)
                if m:
                    dt = cls._parse_date_string(m.group(1))
                    if dt:
                        return dt
        except Exception:
            pass

        # Padrões textuais
        text_patterns = [
            r"Published\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Release\s*date\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Last\s*updated\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ]
        try:
            for pat in text_patterns:
                m = re.search(pat, html, flags=re.IGNORECASE)
                if m:
                    dt = cls._parse_date_string(m.group(1))
                    if dt:
                        return dt
        except Exception:
            pass

        return None

    @staticmethod
    def _parse_date_string(s: str) -> Optional[datetime]:
        if not s:
            return None
        s = s.strip()
        # Tentar formatos comuns ISO8601
        fmts = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                # Normalizar para UTC quando há timezone
                return dt
            except Exception:
                continue
        # Remover milissegundos e tentar novamente
        try:
            s2 = re.sub(r"\.[0-9]+Z$", "Z", s)
            return datetime.strptime(s2, "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return None

    @classmethod
    def _collect_from_product_page(cls, product_url: str, product_label: str, version_label: str, limit: int, base_index: int = 0) -> List[Dict]:
        """Coleta links de release notes a partir de uma página de produto/version.

        Filtra por âncoras que mencionem release notes e normaliza itens.
        """
        html = cls._safe_get(product_url)
        if not html:
            return []

        anchors = re.findall(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, flags=re.IGNORECASE | re.DOTALL)
        items: List[Dict] = []
        seen_links = set()
        fallback_time = datetime.now(timezone.utc)

        for idx, (href, text) in enumerate(anchors):
            try:
                label = re.sub(r"<[^>]+>", " ", text or "").strip()
                href_norm = (href or "").strip()
                if not href_norm or not label:
                    continue

                label_lower = label.lower()
                href_lower = href_norm.lower()
                if "release" not in label_lower and "release" not in href_lower:
                    continue
                if "fortigate" not in href_lower:
                    continue
                if f"/{version_label}" not in href_lower:
                    continue

                if href_norm.startswith("/"):
                    href_norm = f"https://{cls._extract_domain(product_url)}{href_norm}"

                if href_norm in seen_links:
                    continue
                seen_links.add(href_norm)

                domain = cls._extract_domain(href_norm) or "docs.fortinet.com"

                # Tentar extrair data real da página do documento
                real_date = cls._extract_date_from_document(href_norm)
                published_at = real_date or (fallback_time - timedelta(minutes=base_index + idx))

                item = {
                    "title": label,
                    "summary": f"Notas de release do Fortinet {product_label} {version_label}",
                    "source": domain,
                    "published_at": published_at,
                    "tags": ["vendor", "release-notes", "fortinet", "fortigate"],
                    "link": href_norm,
                }
                items.append(item)
                if len(items) >= limit:
                    break
            except Exception:
                continue

        return items

    @classmethod
    def get_fortigate_release_notes_multi_versions(cls, versions: Optional[List[str]] = None, limit: int = 60) -> List[Dict]:
        """Obtém itens de notas de release para FortiGate em múltiplas versões.

        Args:
            versions: lista de versões, por exemplo ["7.0", "7.2", "7.4"].
            limit: máximo total de itens agregados.
        """
        versions = versions or ["7.0", "7.2", "7.4"]

        aggregated: List[Dict] = []
        base_index = 0
        for ver in versions:
            try:
                url = cls.PRODUCT_BASE_URL.format(version=ver)
                items = cls._collect_from_product_page(url, "FortiGate", ver, limit=limit, base_index=base_index)
                aggregated.extend(items)
                base_index += len(items)
                if len(aggregated) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Fortinet: falha ao coletar versão {ver}: {e}")
                continue

        try:
            aggregated.sort(key=lambda i: i.get("published_at") or datetime.now(timezone.utc), reverse=True)
        except Exception:
            pass
        return aggregated[:limit]

    @classmethod
    def get_fortigate_release_notes(cls, limit: int = 30) -> List[Dict]:
        """Mantido para compatibilidade: retorna notas para 7.2 apenas."""
        return cls.get_fortigate_release_notes_multi_versions(["7.2"], limit=limit)

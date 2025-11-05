import re
from typing import List, Dict, Set


class TaggingService:
    """Serviço de categorização por tags com regras simples de palavras‑chave.

    - Normaliza tags (slug simples)
    - Enriquece tags baseado em título, resumo e fonte
    """

    # Vocabulário canônico com sinônimos/keywords (minúsculas)
    KEYWORDS: Dict[str, List[str]] = {
        "ransomware": [
            "ransomware", "locker", "encrypt", "blackcat", "alphv", "lockbit",
        ],
        "data-breach": [
            "data breach", "breach", "leak", "exposed", "compromised", "hackers leaked",
        ],
        "vulnerability": [
            "vulnerability", "cve-", "flaw", "zero-day", "buffer overflow",
        ],
        "patch": [
            "patch", "security update", "patched", "updates released",
        ],
        "exploit": [
            "exploit", "exploitation", "poc", "proof of concept", "rce",
        ],
        "malware": [
            "malware", "trojan", "worm", "spyware", "botnet",
        ],
        "phishing": [
            "phishing", "spearphishing", "email scam", "credential theft",
        ],
        "apt": [
            "apt", "advanced persistent threat", "state-sponsored",
        ],
        "cloud": [
            "cloud", "aws", "azure", "gcp", "s3 bucket", "iam",
        ],
        "iot": [
            "iot", "firmware", "embedded", "industrial control",
        ],
        "privacy": [
            "privacy", "gdpr", "personal data", "pii",
        ],
        "policy": [
            "policy", "regulation", "law", "compliance",
        ],
        "supply-chain": [
            "supply chain", "software bill of materials", "sbom", "dependency",
        ],
        "identity": [
            "identity", "oauth", "openid", "authentication", "password",
        ],
    }

    SOURCE_HINTS: Dict[str, List[str]] = {
        # Ajuda a reforçar algumas tags com base na fonte
        "bleepingcomputer.com": ["malware", "vulnerability"],
        "krebsonsecurity.com": ["data-breach", "identity"],
        "darkreading.com": ["policy", "apt", "cloud"],
        "thehackernews.com": ["vulnerability", "exploit", "malware"],
        "docs.fortinet.com": ["vendor", "release-notes", "fortinet", "fortigate"],
    }

    @staticmethod
    def _slugify(tag: str) -> str:
        t = tag.strip().lower()
        t = re.sub(r"\s+", "-", t)
        t = re.sub(r"[^a-z0-9\-]", "", t)
        return t

    @classmethod
    def normalize(cls, tags: List[str]) -> List[str]:
        uniq: List[str] = []
        seen: Set[str] = set()
        for t in tags:
            s = cls._slugify(t)
            if not s:
                continue
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq

    @classmethod
    def enrich_tags(cls, existing_tags: List[str], title: str = "", summary: str = "", source: str = "") -> List[str]:
        base = " ".join([(title or ""), (summary or "")]).lower()
        enriched: Set[str] = set(cls.normalize(existing_tags))

        # Regras por palavras‑chave
        for canonical, words in cls.KEYWORDS.items():
            for w in words:
                if w in base:
                    enriched.add(canonical)
                    break

        # Regras por fonte
        if source:
            hints = cls.SOURCE_HINTS.get(source.lower(), [])
            for h in hints:
                enriched.add(h)

        # Se nenhuma tag encontrada, tentar heurística simples por termos gerais
        if not enriched:
            for canonical, words in cls.KEYWORDS.items():
                if any(w in base for w in words[:2]):  # primeiros termos mais fortes
                    enriched.add(canonical)
                    break

        return sorted(enriched)
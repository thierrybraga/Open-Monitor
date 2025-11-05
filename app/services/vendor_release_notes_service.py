import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VendorReleaseNotesService:
    """Interface unificada para coleta de notas de release de vendors.

    Agrega múltiplas fontes sob um mesmo contrato, retornando itens normalizados:
    {title, summary, source, published_at, tags, link}

    No momento, inclui Fortinet (FortiGate) com suporte a múltiplas versões.
    """

    @classmethod
    def get_vendor_release_notes(cls, limit: int = 100, vendor_filter: Optional[List[str]] = None) -> List[Dict]:
        """Coleta notas de release de vendors suportados.

        Args:
            limit: máximo de itens agregados.
            vendor_filter: lista opcional de vendors a incluir (e.g., ["fortinet"]).

        Returns:
            Lista de itens normalizados, ordenados por data desc.
        """
        aggregated: List[Dict] = []
        try:
            if not vendor_filter or any(v.lower() == "fortinet" for v in vendor_filter):
                try:
                    from app.services.fortinet_release_notes_service import FortinetReleaseNotesService
                    fortinet_items = FortinetReleaseNotesService.get_fortigate_release_notes_multi_versions(
                        versions=["7.0", "7.2", "7.4"],
                        limit=min(60, limit)
                    )
                    aggregated.extend(fortinet_items)
                except Exception as e:
                    logger.error(f"VendorReleaseNotes: erro ao coletar Fortinet: {e}")
        except Exception:
            # Garantir tolerância a falhas de agregação
            pass

        try:
            aggregated.sort(key=lambda i: i.get('published_at'), reverse=True)
        except Exception:
            pass
        return aggregated[:limit]
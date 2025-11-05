import requests
from typing import Dict, Optional


class GeoIPService:
    """Simple GeoIP resolver using ip-api.com.

    Resolves an IP address to approximate geo coordinates and basic metadata.
    Designed for non-critical use (default map center), with graceful fallbacks.
    """

    API_URL = "http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon,timezone,isp,org,query"

    @classmethod
    def get_location_for_ip(cls, ip: str) -> Optional[Dict[str, str]]:
        try:
            url = cls.API_URL.format(ip=ip)
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json() or {}
            if data.get("status") == "success":
                return {
                    "ip": data.get("query"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": data.get("country"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                }
            return None
        except Exception:
            # Quiet fallback: no location
            return None
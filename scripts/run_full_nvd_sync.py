import sys
from pathlib import Path
import asyncio
import aiohttp

# Garantir que a raiz do projeto esteja no PYTHONPATH
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.app import create_app
from app.extensions import db
from app.services.vulnerability_service import VulnerabilityService
from app.jobs.nvd_fetcher import NVDFetcher


def build_nvd_config(app):
    return {
        "NVD_API_BASE": getattr(app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
        "NVD_API_KEY": getattr(app.config, 'NVD_API_KEY', None),
        "NVD_PAGE_SIZE": getattr(app.config, 'NVD_PAGE_SIZE', 2000),
        "NVD_MAX_RETRIES": getattr(app.config, 'NVD_MAX_RETRIES', 5),
        "NVD_RATE_LIMIT": getattr(app.config, 'NVD_RATE_LIMIT', (2, 1)),
        "NVD_CACHE_DIR": getattr(app.config, 'NVD_CACHE_DIR', "cache"),
        "NVD_REQUEST_TIMEOUT": getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
        "NVD_USER_AGENT": getattr(app.config, 'NVD_USER_AGENT', "Sec4all.co NVD Fetcher"),
        "NVD_MAX_WINDOW_DAYS": getattr(app.config, 'NVD_MAX_WINDOW_DAYS', 120),
    }


async def run_sync(env_name: str = None, full: bool = True):
    app = create_app(env_name)
    with app.app_context():
        nvd_config = build_nvd_config(app)
        async with aiohttp.ClientSession() as http_session:
            fetcher = NVDFetcher(http_session, nvd_config)
            vulnerability_service = VulnerabilityService(db.session)
            processed = await fetcher.update(vulnerability_service=vulnerability_service, full=full)
            print(f"Processed {processed} CVEs")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full NVD synchronization")
    parser.add_argument("--config", type=str, default=None, help="Flask environment (e.g., development, production)")
    parser.add_argument("--full", action="store_true", help="Perform full sync")
    args = parser.parse_args()

    try:
        asyncio.run(run_sync(env_name=args.config, full=args.full or True))
        sys.exit(0)
    except Exception as e:
        print(f"Error running NVD full sync: {e}")
        sys.exit(1)
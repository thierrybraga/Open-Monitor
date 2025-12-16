import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import asyncio
import argparse

from app.main_startup import create_app, initialize_database
from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
from app.services.bulk_database_service import BulkDatabaseService
from app.extensions import db


def main():
    os.environ.setdefault("OM_DISABLE_SYNC_THREADS", "true")
    parser = argparse.ArgumentParser(prog="nvd_populate_sqlite")
    parser.add_argument("--env", default=os.getenv("FLASK_ENV", "development"))
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--backfill", choices=["none", "vendors", "products", "all"], default="all")
    parser.add_argument("--batch-limit", type=int, default=5000)
    args = parser.parse_args()

    app = create_app(args.env)
    if not initialize_database(app):
        print("Erro ao inicializar banco", file=sys.stderr)
        sys.exit(1)

    with app.app_context():
        fetcher = EnhancedNVDFetcher(app=app, max_workers=10, enable_cache=True)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                fetcher.sync_nvd(
                    full=True,
                    max_pages=None,
                    use_parallel=args.parallel
                )
            )
        finally:
            loop.close()

        try:
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        try:
            db.session.remove()
        except Exception:
            try:
                db.session.close()
            except Exception:
                pass

        if args.backfill != "none":
            svc = BulkDatabaseService(batch_size=app.config.get("DB_BATCH_SIZE", 500))
            stats = {}
            if args.backfill in ("vendors", "all"):
                try:
                    s = svc.backfill_vendors_from_vulnerabilities(session=db.session, batch_limit=args.batch_limit)
                    stats["vendors"] = s
                except Exception:
                    pass
            if args.backfill in ("products", "all"):
                try:
                    s = svc.backfill_products_from_vulnerabilities(session=db.session, batch_limit=args.batch_limit)
                    stats["products"] = s
                except Exception:
                    pass
            try:
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass

        print(str(result))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from flask import Flask, current_app

from app.extensions import db
from app.models.sync_metadata import SyncMetadata
from app.models.vulnerability import Vulnerability
try:
    from app.services.parallel_nvd_service import ParallelNVDService as _ParallelNVDService
    _HAS_PARALLEL = True
except Exception:
    _HAS_PARALLEL = False
    _ParallelNVDService = None
from app.services.vulnerability_service import VulnerabilityService
from app.services.redis_cache_service import RedisCacheService
from sqlalchemy import func


class EnhancedNVDFetcher:
    """Orquestrador de sincronização NVD com serviço paralelo e sinalização de progresso."""

    def __init__(
        self,
        app: Flask,
        max_workers: int = 10,
        enable_cache: bool = True,
        enable_monitoring: bool = False,
        batch_size: Optional[int] = None,
    ) -> None:
        self.app = app
        self.max_workers = max_workers
        self.enable_cache = enable_cache
        self.enable_monitoring = enable_monitoring
        self.batch_size = batch_size
        cfg = {
            "REDIS_CACHE_ENABLED": app.config.get("REDIS_CACHE_ENABLED", False),
            "REDIS_URL": app.config.get("REDIS_URL", "redis://localhost:6379/0"),
            "REDIS_HOST": app.config.get("REDIS_HOST", "localhost"),
            "REDIS_PORT": app.config.get("REDIS_PORT", 6379),
            "REDIS_DB": app.config.get("REDIS_DB", 0),
            "REDIS_PASSWORD": app.config.get("REDIS_PASSWORD"),
            "CACHE_KEY_PREFIX": app.config.get("CACHE_KEY_PREFIX", "nvd_cache:"),
        }
        self.cache = RedisCacheService(cfg)

    def _cache_set(self, key: str, value: Any) -> None:
        try:
            if getattr(self.cache, "enabled", False) and getattr(self.cache, "redis_client", None):
                self.cache.set(key, value, ttl=300, namespace="sync_status")
        except Exception:
            pass

    def _update_meta(self, updates: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        with self.app.app_context():
            try:
                for k, v in updates.items():
                    meta = db.session.query(SyncMetadata).filter_by(key=k).first()
                    if not meta:
                        meta = SyncMetadata(key=k, value=(str(v) if v is not None else None), last_modified=now)
                        db.session.add(meta)
                    else:
                        meta.value = str(v) if v is not None else meta.value
                        meta.last_modified = now
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        for k in (
            "nvd_sync_progress_current",
            "nvd_sync_progress_total",
            "nvd_sync_progress_status",
            "nvd_sync_progress_last_cve",
            "nvd_sync_progress_saving",
            "nvd_sync_progress_saving_start",
        ):
            if k in updates:
                self._cache_set(k, updates[k])

    async def sync_nvd(
        self,
        full: bool = False,
        max_pages: Optional[int] = None,
        use_parallel: bool = True,
    ) -> int:
        with self.app.app_context():
            vs = VulnerabilityService(db.session)
            config = {
                "NVD_API_BASE": self.app.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                "NVD_API_KEY": self.app.config.get("NVD_API_KEY"),
                "NVD_PAGE_SIZE": self.app.config.get("NVD_PAGE_SIZE", 2000),
                "NVD_REQUEST_TIMEOUT": self.app.config.get("NVD_REQUEST_TIMEOUT", 30),
                "NVD_USER_AGENT": self.app.config.get("NVD_USER_AGENT", "OpenMonitor Enhanced NVD Fetcher"),
                "BATCH_SIZE": self.batch_size or self.app.config.get("NVD_BATCH_SIZE", 1000),
                "DB_BATCH_SIZE": self.app.config.get("DB_BATCH_SIZE", 1000),
                "FULL_SYNC_DEFAULT_PUB_START_DAYS": 120,
                "NVD_MAX_WINDOW_DAYS": 120,
            }
            if use_parallel and _HAS_PARALLEL and _ParallelNVDService is not None:
                service = _ParallelNVDService(config=config, max_concurrent_requests=self.max_workers)
                metrics = await service.parallel_sync(full_sync=full, vulnerability_service=vs)
                try:
                    self._update_meta({"nvd_sync_progress_status": "idle"})
                    if full and int(getattr(metrics, "total_cves_saved", 0) or 0) > 0:
                        m = db.session.query(SyncMetadata).filter_by(key="nvd_first_sync_completed").first()
                        if not m:
                            m = SyncMetadata(key="nvd_first_sync_completed", value="true", last_modified=datetime.now(timezone.utc))
                            db.session.add(m)
                        else:
                            m.value = "true"
                            m.last_modified = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                return int(getattr(metrics, "total_cves_saved", 0) or 0)
            else:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    from app.jobs.nvd_fetcher import NVDFetcher
                    fetcher2 = NVDFetcher(session, config)
                    saved = await fetcher2.update(vs, full=full)
                try:
                    self._update_meta({"nvd_sync_progress_status": "idle"})
                    if full and int(saved or 0) > 0:
                        m = db.session.query(SyncMetadata).filter_by(key="nvd_first_sync_completed").first()
                        if not m:
                            m = SyncMetadata(key="nvd_first_sync_completed", value="true", last_modified=datetime.now(timezone.utc))
                            db.session.add(m)
                        else:
                            m.value = "true"
                            m.last_modified = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                return int(saved or 0)

    def get_performance_stats(self) -> Dict[str, Any]:
        return {
            "requests": getattr(getattr(self, "cache", None), "stats", None) and getattr(self.cache.stats, "total_operations", 0),
        }

    def cleanup(self) -> None:
        return None


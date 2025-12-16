#!/usr/bin/env python3
"""
Script principal de inicialização do Open-Monitor.
Gerencia inicialização do banco de dados, verificações de saúde e sincronização automática.
"""

import os
from dotenv import load_dotenv
import sys
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, Type, Dict, Any, List
from datetime import datetime

# Ajustar sys.path para execução direta do script
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
import secrets
from app.extensions import init_extensions, db
load_dotenv(override=True)
from app.settings.base import BaseConfig
from app.settings.development import DevelopmentConfig
from app.settings import config_map
from app.utils.enhanced_logging import get_app_logger, setup_logging
from app.utils.terminal_feedback import terminal_feedback, timed_operation
from app.utils.visual_indicators import status_indicator
from app.jobs.nvd_fetcher import NVDFetcher
from app.services.vulnerability_service import VulnerabilityService
from app.models.sync_metadata import SyncMetadata
from app.models.user import User

_nvd_scheduler_started = False
_analytics_scheduler_started = False

def _acquire_scheduler_lock(app: Flask, name: str) -> bool:
    try:
        from app.services.redis_cache_service import RedisCacheService
        cfg = {
            'REDIS_CACHE_ENABLED': app.config.get('REDIS_CACHE_ENABLED', False),
            'REDIS_URL': app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
            'REDIS_HOST': app.config.get('REDIS_HOST', 'localhost'),
            'REDIS_PORT': app.config.get('REDIS_PORT', 6379),
            'REDIS_DB': app.config.get('REDIS_DB', 0),
            'REDIS_PASSWORD': app.config.get('REDIS_PASSWORD'),
            'CACHE_KEY_PREFIX': app.config.get('CACHE_KEY_PREFIX', 'nvd_cache:')
        }
        rc = RedisCacheService(cfg)
        if getattr(rc, 'enabled', False) and getattr(rc, 'redis_client', None):
            k = rc._generate_cache_key(f'scheduler:{name}:lock', 'scheduler')
            v = str(os.getpid()).encode('utf-8')
            return bool(rc.redis_client.set(k, v, nx=True, ex=600))
    except Exception:
        pass
    return True

def create_app(env_name: Optional[str] = None, config_class=None) -> Flask:
    """
    Factory para criar a aplicação Flask.
    """
    try:
        app = Flask(__name__)
        
        # Configuração
        selected_config: Type[BaseConfig]
        if config_class is None:
            env = (env_name or os.getenv('FLASK_ENV', 'development') or 'development').strip().lower()
            selected_config = config_map.get(env, DevelopmentConfig if env == 'development' else BaseConfig)  # type: ignore
        else:
            if isinstance(config_class, str):
                selected_config = config_map.get(config_class.strip().lower(), BaseConfig)  # type: ignore
            else:
                selected_config = config_class  # type: ignore

        app.config.from_object(selected_config)
        try:
            for k, default in [
                ('NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                ('NVD_API_KEY', None),
                ('NVD_CACHE_DIR', 'cache'),
                ('NVD_USER_AGENT', 'Open-Monitor NVD Fetcher'),
                ('NVD_RATE_LIMIT', (2, 1)),
            ]:
                v = app.config.get(k)
                if (v is None) or isinstance(v, property):
                    ev = os.getenv(k)
                    app.config[k] = ev if ev is not None else default
            for k, cast, default in [
                ('NVD_PAGE_SIZE', int, 2000),
                ('NVD_REQUEST_TIMEOUT', int, 30),
                ('DB_BATCH_SIZE', int, 500),
            ]:
                v = app.config.get(k)
                if (v is None) or isinstance(v, property):
                    app.config[k] = default
                else:
                    try:
                        app.config[k] = cast(v)
                    except Exception:
                        ev = os.getenv(k)
                        app.config[k] = cast(ev) if ev is not None else default
        except Exception:
            pass
        
        # Validar configurações críticas
        required_configs = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
        for config_key in required_configs:
            if not app.config.get(config_key):
                raise ValueError(f"Configuração obrigatória '{config_key}' não encontrada")
        
        # Inicializar extensões
        init_extensions(app)
        from flask import g
        @app.before_request
        def _set_csp_nonce():
            try:
                g.csp_nonce = secrets.token_urlsafe(16)
            except Exception:
                pass
        @app.context_processor
        def inject_nonce():
            try:
                val = getattr(g, 'csp_nonce', None)
                return {'nonce': val, 'csp_nonce': val}
            except Exception:
                return {'nonce': None, 'csp_nonce': None}
        try:
            from app.csp import setup_csp
            setup_csp(app)
        except Exception:
            pass
        try:
            with app.app_context():
                from app.models.user import User
                cnt = db.session.query(User).filter(
                    (User.is_active == True) &
                    (User.password_hash.isnot(None)) &
                    (db.func.length(User.password_hash) > 0)
                ).count()
                has_admin = db.session.query(User).filter(User.is_admin == True).count() > 0
                from app.models.sync_metadata import SyncMetadata
                meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                if (cnt > 0) or has_admin:
                    if meta:
                        try:
                            meta.value = 'false'
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                    else:
                        try:
                            meta = SyncMetadata(key='require_root_setup', value='false')
                            db.session.add(meta)
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
        except Exception:
            pass
        
        # Registrar blueprints
        try:
            from app.controllers.main_controller import main_bp
            from app.controllers.asset_controller import asset_bp
            from app.controllers.api_controller import api_v1_bp
            from app.controllers.analytics_controller import analytics_api_bp
            from app.controllers.chat_controller import chat_bp
            from app.controllers.vulnerability_controller import (
                vuln_ui_bp, vuln_api_bp, vuln_api_legacy_bp
            )
            from app.controllers.report_controller import report_bp
            from app.controllers.monitoring_controller import monitoring_bp
            from app.controllers.product_controller import product_api_bp
            from app.controllers.newsletter_admin_controller import newsletter_admin_bp
            from app.controllers.auth_controller import auth_bp
            
            app.register_blueprint(main_bp)
            app.register_blueprint(asset_bp)
            app.register_blueprint(api_v1_bp)
            app.register_blueprint(analytics_api_bp)
            app.register_blueprint(chat_bp)
            app.register_blueprint(vuln_ui_bp)
            app.register_blueprint(vuln_api_bp)
            app.register_blueprint(vuln_api_legacy_bp)
            app.register_blueprint(report_bp)
            app.register_blueprint(monitoring_bp)
            app.register_blueprint(product_api_bp)
            app.register_blueprint(newsletter_admin_bp)
            app.register_blueprint(auth_bp)
        except Exception as e:
            logger = get_app_logger()
            logger.warning(f"Falha ao registrar alguns blueprints: {e}")

        # Aplicar isenção de CSRF às APIs
        try:
            from app.extensions.csrf import exempt_api_blueprints
            exempt_api_blueprints(app)
        except Exception:
            pass
        try:
            from sqlalchemy import text
            from sqlalchemy import inspect
            with app.app_context():
                insp = inspect(db.engine)
                cols = {c['name'] for c in insp.get_columns('users')}
                dialect = db.engine.name
                if dialect == 'postgresql':
                    needed = {
                        'tacacs_enabled': 'ALTER TABLE users ADD COLUMN tacacs_enabled BOOLEAN DEFAULT FALSE NOT NULL',
                        'tacacs_username': 'ALTER TABLE users ADD COLUMN tacacs_username VARCHAR(255)',
                        'tacacs_secret': 'ALTER TABLE users ADD COLUMN tacacs_secret VARCHAR(255)',
                        'tacacs_server': 'ALTER TABLE users ADD COLUMN tacacs_server VARCHAR(255)',
                        'tacacs_port': 'ALTER TABLE users ADD COLUMN tacacs_port INTEGER DEFAULT 49 NOT NULL',
                        'tacacs_timeout': 'ALTER TABLE users ADD COLUMN tacacs_timeout INTEGER DEFAULT 5 NOT NULL',
                        'root_user_id': 'ALTER TABLE users ADD COLUMN root_user_id INTEGER',
                        'approved_by_user_id': 'ALTER TABLE users ADD COLUMN approved_by_user_id INTEGER',
                        'approved_at': 'ALTER TABLE users ADD COLUMN approved_at TIMESTAMP',
                        'trial_expires_at': 'ALTER TABLE users ADD COLUMN trial_expires_at TIMESTAMP'
                    }
                else:
                    needed = {
                        'tacacs_enabled': 'ALTER TABLE users ADD COLUMN tacacs_enabled BOOLEAN DEFAULT 0 NOT NULL',
                        'tacacs_username': 'ALTER TABLE users ADD COLUMN tacacs_username VARCHAR(255)',
                        'tacacs_secret': 'ALTER TABLE users ADD COLUMN tacacs_secret VARCHAR(255)',
                        'tacacs_server': 'ALTER TABLE users ADD COLUMN tacacs_server VARCHAR(255)',
                        'tacacs_port': 'ALTER TABLE users ADD COLUMN tacacs_port INTEGER DEFAULT 49 NOT NULL',
                        'tacacs_timeout': 'ALTER TABLE users ADD COLUMN tacacs_timeout INTEGER DEFAULT 5 NOT NULL',
                        'root_user_id': 'ALTER TABLE users ADD COLUMN root_user_id INTEGER',
                        'approved_by_user_id': 'ALTER TABLE users ADD COLUMN approved_by_user_id INTEGER',
                        'approved_at': 'ALTER TABLE users ADD COLUMN approved_at DATETIME',
                        'trial_expires_at': 'ALTER TABLE users ADD COLUMN trial_expires_at DATETIME'
                    }
                for name, ddl in needed.items():
                    if name not in cols:
                        try:
                            db.session.execute(text(ddl))
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                try:
                    from app.models.user import User
                    root = db.session.query(User).filter(User.is_admin == True).order_by(User.id.asc()).first()
                    if root:
                        db.session.execute(text('UPDATE users SET root_user_id=:rid WHERE root_user_id IS NULL'), {'rid': int(root.id)})
                        db.session.commit()
                except Exception:
                    db.session.rollback()
                try:
                    from app.models.user import User
                    cnt = db.session.query(User).filter(
                        (User.is_active == True) &
                        (User.password_hash.isnot(None)) &
                        (db.func.length(User.password_hash) > 0)
                    ).count()
                except Exception:
                    cnt = 0
                if cnt == 0:
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                        if not meta:
                            meta = SyncMetadata(key='require_root_setup', value='true')
                            db.session.add(meta)
                        else:
                            meta.value = 'true'
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            
                from app.models.sync_metadata import SyncMetadata
                sentinel = db.session.query(SyncMetadata).filter_by(key='first_run_reset_done').first()
                if sentinel is None:
                    try:
                        db.session.execute(text('DELETE FROM assets'))
                    except Exception:
                        pass
                    try:
                        db.session.execute(text('DELETE FROM asset_products'))
                    except Exception:
                        pass
                    try:
                        db.session.execute(text('DELETE FROM asset_vulnerabilities'))
                    except Exception:
                        pass
                    try:
                        dialect = db.engine.name
                        if dialect == 'postgresql':
                            db.session.execute(text('UPDATE users SET is_active=FALSE, email_confirmed=FALSE'))
                            db.session.execute(text('UPDATE users SET password_hash=NULL'))
                            db.session.execute(text('UPDATE users SET tacacs_enabled=FALSE, tacacs_username=NULL, tacacs_secret=NULL, tacacs_server=NULL, tacacs_port=49, tacacs_timeout=5'))
                        else:
                            db.session.execute(text('UPDATE users SET is_active=0, email_confirmed=0'))
                            db.session.execute(text('UPDATE users SET password_hash=NULL'))
                            db.session.execute(text('UPDATE users SET tacacs_enabled=0, tacacs_username=NULL, tacacs_secret=NULL, tacacs_server=NULL, tacacs_port=49, tacacs_timeout=5'))
                    except Exception:
                        pass
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    try:
                        meta = SyncMetadata(key='first_run_reset_done', value='1')
                        db.session.add(meta)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
        except Exception:
            pass
        
        def _datetimeformat(value, fmt='%d/%m/%Y'):
            try:
                if hasattr(value, 'strftime'):
                    return value.strftime(fmt)
                if isinstance(value, (int, float)):
                    return datetime.fromtimestamp(value).strftime(fmt)
                if isinstance(value, str):
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except Exception:
                        return value
                    return dt.strftime(fmt)
            except Exception:
                return value
        app.jinja_env.filters['datetimeformat'] = _datetimeformat
        
        def _markdown(value):
            try:
                import markdown as _md
                if not isinstance(value, str):
                    return ''
                return _md.markdown(value, extensions=['extra', 'sane_lists', 'fenced_code', 'toc'])
            except Exception:
                return value or ''
        app.jinja_env.filters['markdown'] = _markdown

        

        @app.before_request
        def _first_user_guard():
            from flask import request as _req
            from flask_login import current_user
            total_cnt = 0
            active_cnt = 0
            require_setup = True
            first_sync_done = False
            scheduled = False
            try:
                from app.models.user import User
                total_cnt = db.session.query(User).count()
                active_cnt = db.session.query(User).filter(
                    (User.is_active == True) &
                    (User.password_hash.isnot(None)) &
                    (db.func.length(User.password_hash) > 0)
                ).count()
                from app.models.sync_metadata import SyncMetadata
                meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                try:
                    require_setup = (meta and (str(meta.value or '').strip().lower() not in ('false','0','no')))
                except Exception:
                    require_setup = True
                has_admin = False
                try:
                    has_admin = db.session.query(User).filter(User.is_admin == True).count() > 0
                except Exception:
                    has_admin = False
                if (total_cnt > 0) or has_admin:
                    require_setup = False
                    try:
                        if meta:
                            meta.value = 'false'
                        else:
                            meta = SyncMetadata(key='require_root_setup', value='false')
                            db.session.add(meta)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                try:
                    first_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
                    first_val = (first_meta.value or '').strip().lower() if first_meta and first_meta.value else ''
                    first_sync_done = (first_val in ('1','true','yes'))
                except Exception:
                    first_sync_done = False
                try:
                    sched_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_scheduled').first()
                    scheduled = bool(sched_meta and (str(sched_meta.value or '').strip() in ('1','true','yes')))
                except Exception:
                    scheduled = False
            except Exception:
                total_cnt = 0
                active_cnt = 0
                require_setup = True
                first_sync_done = False
                scheduled = False
            p = getattr(_req, 'path', '')
            try:
                from app.models.sync_metadata import SyncMetadata
                _sm = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                _sv = str((_sm.value if _sm and _sm.value is not None else '')).strip().lower()
                _in_progress = _sv in ('processing','saving')
            except Exception:
                _in_progress = False
            if not first_sync_done:
                try:
                    from app.models.sync_metadata import SyncMetadata
                    sched_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_scheduled').first()
                    status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                    current_status = str((status_meta.value if status_meta and status_meta.value is not None else '')).strip().lower()
                    in_progress = current_status in ('processing','saving')
                    if not status_meta:
                        status_meta = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                        db.session.add(status_meta)
                    else:
                        status_meta.value = (current_status or 'idle') if in_progress else ('idle' if (active_cnt == 0 or require_setup) else (current_status or 'idle'))
                    current_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                    if not current_meta:
                        current_meta = SyncMetadata(key='nvd_sync_progress_current', value='0')
                        db.session.add(current_meta)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                if (active_cnt > 0) and (not require_setup):
                    # Sinalizar progresso somente quando thread de sync for iniciada
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                        if sm_status:
                            sm_status.value = 'processing'
                        sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                        if sm_current:
                            sm_current.value = '0'
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    try:
                        from sqlalchemy import inspect
                        insp = inspect(db.engine)
                        tables = insp.get_table_names()
                        if 'vulnerabilities' not in tables:
                            db.create_all()
                            try:
                                db.create_all(bind_key='public')
                            except Exception:
                                pass
                    except Exception:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                    def _run():
                        try:
                            with app.app_context():
                                import asyncio
                                try:
                                    from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
                                    app_obj = app
                                    fetcher = EnhancedNVDFetcher(app=app_obj, max_workers=10, enable_cache=True)
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    try:
                                        loop.run_until_complete(fetcher.sync_nvd(full=(not scheduled), max_pages=None, use_parallel=False))
                                    finally:
                                        loop.close()
                                    return
                                except Exception as imp_err:
                                    try:
                                        app.logger.error(f"NVD sync thread failed: {imp_err}")
                                    except Exception:
                                        pass
                                    # Fallback: usar fetcher original sequencial
                                    try:
                                        from app.jobs.nvd_fetcher import NVDFetcher
                                        from app.services.vulnerability_service import VulnerabilityService
                                        from app.extensions import db as _db
                                        import aiohttp
                                        app_obj = app
                                        vs = VulnerabilityService(_db.session)
                                        cfg = {
                                            "NVD_API_BASE": app_obj.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                                            "NVD_API_KEY": app_obj.config.get("NVD_API_KEY"),
                                            "NVD_PAGE_SIZE": app_obj.config.get("NVD_PAGE_SIZE", 2000),
                                            "NVD_REQUEST_TIMEOUT": app_obj.config.get("NVD_REQUEST_TIMEOUT", 30),
                                            "NVD_USER_AGENT": app_obj.config.get("NVD_USER_AGENT", "Open-Monitor NVD Fetcher"),
                                            "NVD_MAX_WINDOW_DAYS": app_obj.config.get("NVD_MAX_WINDOW_DAYS", 120),
                                            "NVD_RATE_LIMIT": app_obj.config.get("NVD_RATE_LIMIT", (2, 1)),
                                        }
                                        async def _run_seq():
                                            async with aiohttp.ClientSession() as session:
                                                fetcher2 = NVDFetcher(session, cfg)
                                                return await fetcher2.update(vs, full=(not scheduled))
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            loop.run_until_complete(_run_seq())
                                        finally:
                                            loop.close()
                                        return
                                    except Exception as fb_err:
                                        try:
                                            app.logger.error(f"NVD sequential fallback failed: {fb_err}")
                                        except Exception:
                                            pass
                        except Exception as e:
                            try:
                                app.logger.error(f"NVD sync thread failed: {e}")
                            except Exception:
                                pass
                            try:
                                from datetime import datetime, timezone
                                from app.models.sync_metadata import SyncMetadata
                                sm = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                                now = datetime.now(timezone.utc)
                                if sm:
                                    sm.value = 'idle'
                                    sm.last_modified = now
                                db.session.commit()
                            except Exception:
                                try:
                                    db.session.rollback()
                                except Exception:
                                    pass
                    import threading
                    threading.Thread(target=_run, daemon=True).start()
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        sched_meta2 = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_scheduled').first()
                        if not sched_meta2:
                            sched_meta2 = SyncMetadata(key='nvd_first_sync_scheduled', value='1')
                            db.session.add(sched_meta2)
                        else:
                            sched_meta2.value = '1'
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            if not first_sync_done:
                allowed = (
                    p.startswith('/auth/init-root') or
                    p.startswith('/auth/login') or
                    p.startswith('/loading') or
                    p.startswith('/static/') or
                    p.startswith('/api/') or
                    p.startswith('/auth/check-availability') or
                    p.startswith('/auth/confirm-email')
                )
                if not allowed:
                    from flask import redirect
                    if ((active_cnt > 0) and (not require_setup)) or (total_cnt > 0):
                        if getattr(current_user, 'is_authenticated', False):
                            return redirect('/loading')
                        else:
                            return redirect('/auth/login')
                    else:
                        return redirect('/auth/init-root')
            elif _in_progress:
                pass  # Após primeira sincronização concluída, permitir navegação e exibir progresso na UI
            elif require_setup:
                allowed = (
                    p.startswith('/auth/init-root') or
                    p.startswith('/static/') or
                    p.startswith('/api/') or
                    p.startswith('/auth/check-availability') or
                    p.startswith('/auth/confirm-email')
                )
                if not allowed:
                    from flask import redirect
                    return redirect('/auth/init-root')

        @app.before_request
        def _trial_access_guard():
            from flask_login import current_user
            from flask import request as _req
            try:
                if getattr(current_user, 'is_authenticated', False):
                    # Usuário não aprovado: permitir acesso por 30 dias
                    if not getattr(current_user, 'is_active', False):
                        from datetime import datetime, timezone
                        exp = getattr(current_user, 'trial_expires_at', None)
                        now = datetime.now(timezone.utc)
                        trial_ok = (exp is not None and now <= (exp if getattr(exp, 'tzinfo', None) else exp.replace(tzinfo=timezone.utc)))
                        if not trial_ok:
                            p = getattr(_req, 'path', '')
                            allowed = (
                                p == '/' or
                                p.startswith('/newsletter') or
                                p.startswith('/static/') or
                                p.startswith('/auth/') or
                                p.startswith('/api/')
                            )
                            if not allowed:
                                from flask import redirect, flash, url_for
                                flash('Sua conta aguarda aprovação. Acesso completo expirado. Navegue pela página pública.', 'warning')
                                return redirect(url_for('main.index'))
            except Exception:
                pass

        @app.after_request
        def _set_cache_headers(response):
            from flask import request as _req
            p = getattr(_req, 'path', '')
            try:
                if p.startswith('/api/'):
                    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                    response.headers['Pragma'] = 'no-cache'
                    response.headers.pop('ETag', None)
                elif p.startswith('/static/'):
                    response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
                else:
                    response.headers['Cache-Control'] = 'no-cache, must-revalidate'
            except Exception:
                pass
            return response

        
        
        @app.context_processor
        def inject_global_template_vars():
            try:
                from flask import session, current_app
                from datetime import datetime as _dt
                ui_settings = {
                    'theme': (session.get('settings') or {}).get('general', {}).get('theme', 'auto'),
                    'language': (session.get('settings') or {}).get('general', {}).get('language', current_app.config.get('HTML_LANG', 'pt-BR')),
                }
                return {
                    'ui_settings': ui_settings,
                    'app_name': current_app.config.get('APP_NAME', 'Open Monitor'),
                    'current_year': _dt.now().year,
                    'OPENAI_STREAMING': bool(current_app.config.get('OPENAI_STREAMING', False)),
                }
            except Exception:
                return {}
        
        try:
            bootstrap_on_startup(app)
        except Exception:
            pass
        try:
            setup_nvd_scheduler(app)
        except Exception:
            pass
        try:
            setup_analytics_cache_scheduler(app)
        except Exception:
            pass
        
        return app
    except Exception as e:
        logger = get_app_logger()
        logger.error(f"Erro ao criar aplicação Flask: {e}")
        raise

def initialize_database(app: Flask) -> bool:
    """
    Inicializa o banco de dados se necessário.
    """
    app_logger = get_app_logger()
    
    try:
        with app.app_context():
            # Verificar conexão com o banco
            try:
                db.engine.connect()
                app_logger.info("✅ Conexão com banco de dados estabelecida")
            except Exception as conn_error:
                app_logger.error(f"❌ Falha na conexão com banco de dados: {conn_error}")
                return False
            
            # Importar todos os modelos para garantir que estejam registrados
            try:
                import app.models as models
                app_logger.info("📦 Modelos importados com sucesso")
            except Exception as import_error:
                app_logger.error(f"❌ Erro ao importar modelos: {import_error}")
                return False
            
            # Verificar se as tabelas existem
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            disable_create_all = (os.getenv('DISABLE_CREATE_ALL', '').lower() in ('1', 'true', 'yes'))
            if not tables and not disable_create_all:
                app_logger.info("🗄️ Criando tabelas do banco de dados...")
                try:
                    db.create_all()
                    try:
                        db.create_all(bind_key='public')
                        app_logger.info("✅ Tabelas do bind 'public' criadas")
                    except Exception as _bind_err:
                        app_logger.warning(f"⚠️ Falha ao criar tabelas do bind 'public': {_bind_err}")
                    app_logger.info("✅ Comando create_all() executado")
                except Exception as create_error:
                    try:
                        inspector = inspect(db.engine)
                        new_tables = inspector.get_table_names()
                    except Exception:
                        new_tables = []
                    if new_tables:
                        app_logger.info(f"ℹ️ create_all informou erro, porém {len(new_tables)} tabelas foram detectadas/provisionadas. Prosseguindo.")
                    else:
                        app_logger.error(f"❌ Erro durante create_all(): {create_error}")
                        return False
                
                # Verificar se as tabelas foram criadas
                # Criar um novo inspector após create_all()
                inspector = inspect(db.engine)
                new_tables = inspector.get_table_names()
                if new_tables:
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                        sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                        if not sm_status:
                            sm_status = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                            db.session.add(sm_status)
                        if not sm_current:
                            sm_current = SyncMetadata(key='nvd_sync_progress_current', value='0')
                            db.session.add(sm_current)
                        first_done = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
                        if not first_done:
                            first_done = SyncMetadata(key='nvd_first_sync_completed', value='false')
                            db.session.add(first_done)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    app_logger.success(f"✅ {len(new_tables)} tabelas provisionadas/detectadas com sucesso")
                    return True
                else:
                    app_logger.error("❌ Falha ao criar tabelas do banco de dados")
                    return False
            elif not tables and disable_create_all:
                app_logger.info("🗄️ Banco vazio detectado e create_all desativado — aplicando migrações Alembic para provisionamento inicial")
                try:
                    from alembic import command as alembic_command
                    from alembic.config import Config as AlembicConfig
                    cfg = AlembicConfig()
                    cfg.set_main_option('script_location', str(Path(__file__).parent / 'migrations'))
                    with db.engine.begin() as connection:
                        cfg.attributes['connection'] = connection
                        alembic_command.upgrade(cfg, 'initial_schema_full_postgres')
                    app_logger.success("✅ Migrações iniciais aplicadas (core/public)")
                    # Revalidar criação de tabelas
                    inspector = inspect(db.engine)
                    new_tables = inspector.get_table_names()
                    app_logger.info(f"📊 Tabelas detectadas após migrações: {len(new_tables)}")
                    if not new_tables:
                        app_logger.warning("⚠️ Migrações não criaram tabelas — aplicando fallback create_all() apenas para provisionamento inicial")
                        try:
                            db.create_all()
                            try:
                                db.create_all(bind_key='public')
                                app_logger.info("✅ Tabelas do bind 'public' criadas (fallback)")
                            except Exception as _bind_err:
                                app_logger.warning(f"⚠️ Falha ao criar tabelas do bind 'public' (fallback): {_bind_err}")
                            inspector = inspect(db.engine)
                            new_tables = inspector.get_table_names()
                            app_logger.success(f"✅ Fallback create_all() criou {len(new_tables)} tabelas")
                        except Exception as fallback_err:
                            try:
                                inspector = inspect(db.engine)
                                new_tables = inspector.get_table_names()
                            except Exception:
                                new_tables = []
                            if new_tables:
                                app_logger.info(f"ℹ️ Fallback create_all() reportou erro, porém {len(new_tables)} tabelas foram detectadas/provisionadas. Prosseguindo.")
                            else:
                                app_logger.error(f"❌ Fallback create_all() falhou: {fallback_err}")
                                return False
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                        sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                        if not sm_status:
                            sm_status = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                            db.session.add(sm_status)
                        if not sm_current:
                            sm_current = SyncMetadata(key='nvd_sync_progress_current', value='0')
                            db.session.add(sm_current)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    return True
                except Exception as mig_err:
                    app_logger.error(f"❌ Falha ao aplicar migrações iniciais: {mig_err}")
                    return False
            else:
                app_logger.info(f"✅ Banco de dados já existe com {len(tables)} tabelas")
                # Garantir também criação para bind 'public'
                if not disable_create_all:
                    try:
                        db.create_all(bind_key='public')
                        app_logger.info("✅ Verificação/criação de tabelas do bind 'public' concluída")
                    except Exception as _bind_err:
                        app_logger.warning(f"⚠️ Falha ao verificar/criar tabelas do bind 'public': {_bind_err}")
                # Criar root se não houver usuário ativo
                try:
                    from app.models.user import User
                    cnt_active = db.session.query(User).filter(
                        (User.is_active == True) &
                        (User.password_hash.isnot(None)) &
                        (db.func.length(User.password_hash) > 0)
                    ).count()
                except Exception:
                    cnt_active = 0
                if cnt_active == 0:
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                        if not meta:
                            meta = SyncMetadata(key='require_root_setup', value='true')
                            db.session.add(meta)
                            db.session.commit()
                    except Exception:
                        db.session.rollback()
                try:
                    from app.models.sync_metadata import SyncMetadata
                    sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                    sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                    if not sm_status:
                        sm_status = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                        db.session.add(sm_status)
                    if not sm_current:
                        sm_current = SyncMetadata(key='nvd_sync_progress_current', value='0')
                        db.session.add(sm_current)
                    try:
                        from sqlalchemy import func
                        from app.models.vulnerability import Vulnerability
                        total_vulns = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
                        first_done = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
                        val = 'true' if total_vulns > 0 else 'false'
                        if first_done:
                            first_done.value = val
                        else:
                            first_done = SyncMetadata(key='nvd_first_sync_completed', value=val)
                            db.session.add(first_done)
                    except Exception:
                        pass
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return True
                
    except Exception as e:
        app_logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False



def bootstrap_on_startup(app: Flask) -> None:
    app_logger = get_app_logger()
    auto_bootstrap = (os.getenv('AUTO_BOOTSTRAP_ON_STARTUP', 'true').lower() in ('1','true','yes'))
    if not auto_bootstrap:
        return
    def _run():
        try:
            with app.app_context():
                # 1) Marcar que root setup é necessário caso não exista usuário ativo
                try:
                    has_active = db.session.query(User).filter((User.is_active == True) & (User.password_hash.isnot(None))).count() > 0
                except Exception:
                    has_active = False
                try:
                    meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                    val = 'false' if has_active else 'true'
                    if meta:
                        meta.value = val
                    else:
                        meta = SyncMetadata(key='require_root_setup', value=val)
                        db.session.add(meta)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                from sqlalchemy import inspect
                insp = inspect(db.engine)
                tables = insp.get_table_names()
                if not tables and auto_bootstrap:
                    backend = str(getattr(getattr(db, 'engine', None), 'url', ''))
                    try:
                        driver = str(getattr(getattr(db, 'engine', None), 'url', None).drivername)
                    except Exception:
                        driver = ''
                    if driver.startswith('postgresql'):
                        try:
                            from alembic import command as alembic_command
                            from alembic.config import Config as AlembicConfig
                            cfg = AlembicConfig()
                            cfg.set_main_option('script_location', str(Path(__file__).parent / 'migrations'))
                            with db.engine.begin() as connection:
                                cfg.attributes['connection'] = connection
                                alembic_command.upgrade(cfg, 'initial_schema_full_postgres')
                            app_logger.success("✅ Provisionamento inicial via Alembic concluído")
                        except Exception as e:
                            app_logger.error(f"❌ Erro no provisionamento inicial: {e}")
                            try:
                                db.create_all()
                                try:
                                    db.create_all(bind_key='public')
                                    app_logger.info("✅ Tabelas do bind 'public' criadas (fallback)")
                                except Exception:
                                    pass
                                app_logger.success("✅ Fallback create_all() concluído")
                                try:
                                    from app.models.sync_metadata import SyncMetadata
                                    sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                                    sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                                    if not sm_status:
                                        sm_status = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                                        db.session.add(sm_status)
                                    if not sm_current:
                                        sm_current = SyncMetadata(key='nvd_sync_progress_current', value='0')
                                        db.session.add(sm_current)
                                    db.session.commit()
                                except Exception:
                                    db.session.rollback()
                            except Exception as fallback_err:
                                app_logger.error(f"❌ Fallback create_all() falhou: {fallback_err}")
                    else:
                        try:
                            db.create_all()
                            try:
                                db.create_all(bind_key='public')
                                app_logger.info("✅ Tabelas do bind 'public' criadas (fallback)")
                            except Exception:
                                pass
                            app_logger.success("✅ Fallback create_all() concluído")
                            try:
                                from app.models.sync_metadata import SyncMetadata
                                sm_status = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                                sm_current = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                                if not sm_status:
                                    sm_status = SyncMetadata(key='nvd_sync_progress_status', value='idle')
                                    db.session.add(sm_status)
                                if not sm_current:
                                    sm_current = SyncMetadata(key='nvd_sync_progress_current', value='0')
                                    db.session.add(sm_current)
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                        except Exception as fallback_err:
                            app_logger.error(f"❌ Fallback create_all() falhou: {fallback_err}")
                # Sincronização NVD não é disparada aqui; guard e scheduler cuidam do fluxo
        except Exception as e:
            app_logger.error(f"❌ Erro no bootstrap de inicialização: {e}")
    threading.Thread(target=_run, daemon=True).start()

def setup_nvd_scheduler(app: Flask) -> None:
    """
    Configura scheduler para sincronização automática do NVD.
    Durante a primeira inicialização (antes da sincronização completa), executa a cada 10 minutos.
    Após conclusão inicial, executa incrementalmente a cada 1 hora.
    """
    app_logger = get_app_logger()
    global _nvd_scheduler_started
    import os
    if str(os.getenv('OM_DISABLE_SYNC_THREADS','')).strip().lower() == 'true':
        return
    if _nvd_scheduler_started:
        app_logger.info("⏰ Scheduler de sincronização NVD já iniciado")
        return
    if not _acquire_scheduler_lock(app, 'nvd'):
        return
    
    def run_adaptive_sync():
        """Executa sincronização com intervalo adaptativo, com tentativa imediata ao iniciar."""
        first_cycle = True
        while True:
            try:
                interval_seconds = 3600
                run_full = False
                with app.app_context():
                    try:
                        from app.models.sync_metadata import SyncMetadata
                        try:
                            from app.models.user import User
                            active_cnt = db.session.query(User).filter(
                                (User.is_active == True) &
                                (User.password_hash.isnot(None)) &
                                (db.func.length(User.password_hash) > 0)
                            ).count()
                        except Exception:
                            active_cnt = 0
                        require_setup = True
                        try:
                            meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
                            if meta:
                                v = str(meta.value or '').strip().lower()
                                require_setup = v not in ('false', '0', 'no')
                            else:
                                require_setup = True
                        except Exception:
                            require_setup = True
                        if require_setup or active_cnt == 0:
                            app_logger.info("⏳ Aguardando criação do usuário root antes da sincronização NVD")
                            interval_seconds = 600
                            run_full = False
                        else:
                            first_done = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
                            if not first_done or (str(first_done.value or '').strip().lower() not in ('1', 'true', 'yes')):
                                interval_seconds = 600
                                run_full = True
                            else:
                                interval_seconds = 3600
                                run_full = False
                    except Exception:
                        interval_seconds = 600
                        run_full = True
                # Na primeira execução, não aguardar: iniciar imediatamente
                if not first_cycle:
                    time.sleep(interval_seconds)
                else:
                    first_cycle = False
                app_logger.info(f"🔄 Iniciando sincronização NVD ({'completa' if run_full else 'incremental'})...")
                with app.app_context():
                    try:
                        try:
                            from app.models.user import User
                            active_cnt = db.session.query(User).filter(
                                (User.is_active == True) &
                                (User.password_hash.isnot(None)) &
                                (db.func.length(User.password_hash) > 0)
                            ).count()
                        except Exception:
                            active_cnt = 0
                        if active_cnt == 0:
                            app_logger.info("⏳ Sincronização NVD adiada: usuário root inexistente")
                            continue
                        try:
                            from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
                            from flask import current_app as _app
                            fetcher = EnhancedNVDFetcher(app=_app, max_workers=10, enable_cache=True)
                            result = asyncio.run(fetcher.sync_nvd(full=run_full, max_pages=None, use_parallel=(not run_full)))
                            app_logger.info(f"✅ Sincronização {'completa' if run_full else 'incremental'} concluída: {result} vulnerabilidades processadas")
                        except Exception:
                            import asyncio as aio
                            import aiohttp
                            from app.jobs.nvd_fetcher import NVDFetcher
                            from app.services.vulnerability_service import VulnerabilityService
                            vs = VulnerabilityService(db.session)
                            cfg = {
                                "NVD_API_BASE": app.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                                "NVD_API_KEY": app.config.get("NVD_API_KEY"),
                                "NVD_PAGE_SIZE": app.config.get("NVD_PAGE_SIZE", 2000),
                                "NVD_REQUEST_TIMEOUT": app.config.get("NVD_REQUEST_TIMEOUT", 30),
                                "NVD_USER_AGENT": app.config.get("NVD_USER_AGENT", "Open-Monitor NVD Fetcher"),
                                "NVD_MAX_WINDOW_DAYS": app.config.get("NVD_MAX_WINDOW_DAYS", 120),
                                "NVD_RATE_LIMIT": app.config.get("NVD_RATE_LIMIT", (2, 1)),
                            }
                            loop = aio.new_event_loop()
                            aio.set_event_loop(loop)
                            try:
                                async def _run_seq():
                                    async with aiohttp.ClientSession() as session:
                                        f2 = NVDFetcher(session, cfg)
                                        return await f2.update(vs, full=run_full)
                                result = loop.run_until_complete(_run_seq())
                                app_logger.info(f"✅ Sincronização {'completa' if run_full else 'incremental'} concluída: {result} vulnerabilidades processadas")
                            except Exception as seq_err:
                                app_logger.error(f"❌ Erro durante execução de sincronização NVD: {seq_err}")
                            finally:
                                loop.close()
                    except Exception as e:
                        app_logger.error(f"❌ Erro durante execução de sincronização NVD: {e}")
            except Exception as e:
                app_logger.error(f"❌ Erro durante sincronização adaptativa: {e}")
    # Iniciar thread do scheduler
    scheduler_thread = threading.Thread(target=run_adaptive_sync, daemon=True)
    scheduler_thread.start()
    _nvd_scheduler_started = True
    app_logger.info("⏰ Scheduler de sincronização NVD iniciado (10 min até concluir; depois 1h)")

def setup_news_scheduler(app: Flask) -> None:
    """
    Configura scheduler para atualização automática do feed de notícias a cada 1 hora.
    Pré-aquece o cache na inicialização e atualiza periodicamente usando atualização incremental
    do CyberNewsService com persistência via NewsCacheService.
    """
    app_logger = get_app_logger()
    if not _acquire_scheduler_lock(app, 'news'):
        return

    def run_hourly_news_refresh():
        """Executa atualização horária do feed de notícias em thread separada."""
        while True:
            try:
                with app.app_context():
                    try:
                        from app.services.cybernews_service import CyberNewsService
                        app_logger.info("📰 Atualizando feed de notícias (incremental, 2 páginas)...")
                        added = CyberNewsService.incremental_update(page_count=2, page_size=30)
                        app_logger.info(f"✅ Feed de notícias incremental: {added} novos itens persistidos")
                    except Exception as inner_e:
                        app_logger.error(f"❌ Erro ao atualizar feed de notícias: {inner_e}")

                # Aguardar 1 hora (3600 segundos) até próxima atualização
                time.sleep(3600)
            except Exception as e:
                app_logger.error(f"❌ Erro no scheduler de notícias: {e}")
                # Em caso de erro, aguarda 10 minutos antes de tentar novamente
                time.sleep(600)

    # Pré-aquecer o cache imediatamente uma vez, depois iniciar loop horário
    try:
        with app.app_context():
            from app.services.cybernews_service import CyberNewsService
            app_logger.info("📰 Pré-aquecendo feed de notícias (incremental, 2 páginas) na inicialização...")
            added = CyberNewsService.incremental_update(page_count=2, page_size=30)
            app_logger.info(f"✅ Pré-aquecimento incremental concluído: {added} novos itens persistidos")
    except Exception as e:
        app_logger.warning(f"⚠️ Falha ao pré-aquecer feed de notícias na inicialização: {e}")

    # Iniciar thread do scheduler de notícias
    news_thread = threading.Thread(target=run_hourly_news_refresh, daemon=True)
    news_thread.start()
    app_logger.info("⏰ Scheduler do feed de notícias iniciado (execução a cada 1 hora)")

def setup_news_json_cache(app: Flask) -> None:
    app_logger = get_app_logger()
    if not _acquire_scheduler_lock(app, 'news_json'):
        return

    def _parse_sources() -> Dict[str, Any]:
        try:
            raw = getattr(app.config, 'NEWS_FEED_SOURCES_JSON', None)
            if raw:
                import json as _json
                data = _json.loads(raw)
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {
            'rss_feeds': [
                {"url": "https://feeds.feedburner.com/TheHackersNews", "tag": "rss"},
                {"url": "https://krebsonsecurity.com/feed/", "tag": "rss"},
                {"url": "https://www.bleepingcomputer.com/feed/", "tag": "rss"},
                {"url": "https://www.darkreading.com/rss.xml", "tag": "rss"},
            ],
            'cybernews_categories': [
                "general",
                "security",
                "malware",
                "cyberAttack",
                "dataBreach",
                "vulnerability",
            ],
        }

    def _collect_and_save(limit: int = 10) -> str:
        sources = _parse_sources()
        items: List[Dict[str, Any]] = []
        try:
            from app.services.rss_feed_service import RSSFeedService
            rss_items = RSSFeedService.get_news_fast(limit=limit, feeds=sources.get('rss_feeds') or [])
        except Exception:
            rss_items = []
        try:
            from app.services.cybernews_service import CyberNewsService
            cy_items = CyberNewsService.get_news_fast(limit=limit, categories=sources.get('cybernews_categories') or [])
        except Exception:
            cy_items = []
        items.extend(rss_items)
        items.extend(cy_items)
        seen_links = set()
        seen_titles = set()
        deduped: List[Dict[str, Any]] = []
        for it in items:
            lk = it.get('link')
            tt = it.get('title')
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
            from app.services.news_cache_service import NewsCacheService
            srcs_meta: List[Dict[str, Any]] = []
            for rf in (sources.get('rss_feeds') or []):
                srcs_meta.append({'type': 'rss', 'url': rf.get('url'), 'tag': rf.get('tag')})
            for cat in (sources.get('cybernews_categories') or []):
                srcs_meta.append({'type': 'cybernews', 'category': cat})
            path = NewsCacheService.save_json_feed(deduped, srcs_meta)
            try:
                from app.models.sync_metadata import SyncMetadata
                sm = db.session.query(SyncMetadata).filter_by(key='news_feed_json_path').first()
                if not sm:
                    sm = SyncMetadata(key='news_feed_json_path', value=path)
                    db.session.add(sm)
                else:
                    sm.value = path
                db.session.commit()
            except Exception:
                db.session.rollback()
            return path
        except Exception:
            return ''

    try:
        with app.app_context():
            p = _collect_and_save(limit=10)
            if p:
                app_logger.info(f"📰 Feed JSON salvo: {p}")
            else:
                app_logger.warning("⚠️ Falha ao salvar feed JSON")
    except Exception as e:
        app_logger.warning(f"⚠️ Erro ao pré-aquecer feed JSON: {e}")

    def run_periodic_refresh():
        while True:
            try:
                minutes = int(getattr(app.config, 'NEWS_REFRESH_INTERVAL_MINUTES', 1440))
                seconds = max(60, minutes * 60)
                time.sleep(seconds)
                with app.app_context():
                    p = _collect_and_save(limit=10)
                    if p:
                        app_logger.info(f"✅ Feed JSON atualizado: {p}")
            except Exception as e:
                app_logger.error(f"❌ Erro no refresh do feed JSON: {e}")
                time.sleep(600)

    t = threading.Thread(target=run_periodic_refresh, daemon=True)
    t.start()
    app_logger.info("⏰ Scheduler do feed JSON iniciado")

def setup_analytics_cache_scheduler(app: Flask) -> None:
    """
    Configura um scheduler simples para pré-aquecer e atualizar periodicamente
    o cache dos endpoints de Analytics.
    """
    app_logger = get_app_logger()
    global _analytics_scheduler_started
    if _analytics_scheduler_started:
        app_logger.info("⏰ Scheduler de cache Analytics já iniciado")
        return
    if not _acquire_scheduler_lock(app, 'analytics'):
        return

    def prewarm_once():
        try:
            with app.app_context():
                app_logger.info("📊 Pré-aquecendo cache de Analytics (overview e top_products)...")
                client = app.test_client()
                # Pré-aquecer overview (todos vendors)
                client.get('/api/analytics/overview')
                # Pré-aquecer top_products página 1
                client.get('/api/analytics/details/top_products?page=1&per_page=10')
                app_logger.info("✅ Cache de Analytics pré-aquecido")
        except Exception as e:
            app_logger.warning(f"⚠️ Falha ao pré-aquecer cache de Analytics: {e}")

    def run_periodic_refresh():
        """Atualiza periodicamente o cache de Analytics em thread separada."""
        while True:
            try:
                with app.app_context():
                    client = app.test_client()
                    app_logger.info("📊 Atualizando cache de Analytics...")
                    client.get('/api/analytics/overview')
                    client.get('/api/analytics/details/top_products?page=1&per_page=10')
                    app_logger.info("✅ Cache de Analytics atualizado")
                # Intervalo configurável
                minutes = int(getattr(app.config, 'ANALYTICS_CACHE_REFRESH_INTERVAL_MINUTES', 15))
                time.sleep(max(60, minutes * 60))
            except Exception as e:
                app_logger.error(f"❌ Erro no scheduler de Analytics: {e}")
                time.sleep(600)

    # Pré-aquecer na inicialização
    prewarm_once()

    # Iniciar thread de atualização
    analytics_thread = threading.Thread(target=run_periodic_refresh, daemon=True)
    analytics_thread.start()
    _analytics_scheduler_started = True
    app_logger.info("⏰ Scheduler de cache Analytics iniciado (execução periódica)")

def main():
    """
    Função principal de inicialização com feedback aprimorado.
    """
    # Configurar logging
    setup_logging("INFO", "logs/openmonitor.log")
    app_logger = get_app_logger()
    
    # Iniciar sistema de indicadores visuais
    status_indicator.start_display()
    
    # Usar sistema de feedback aprimorado
    terminal_feedback.info("🚀 Iniciando Open-Monitor")
    terminal_feedback.info(f"⏰ Horário de inicialização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Criar aplicação Flask com feedback
        with timed_operation("Configuração da aplicação Flask"):
            app = create_app()
        
        # Inicializar banco de dados com feedback visual
        with timed_operation("Inicialização do banco de dados"):
            if not initialize_database(app):
                terminal_feedback.error("❌ Falha na inicialização do banco de dados", 
                                      suggestion="Verifique a configuração do banco e permissões")
                status_indicator.stop_display()
                return False
        
        # Pré-sincronizar primeiras notícias antes da NVD
        with timed_operation("Pré-sincronização de notícias (Top 10)"):
            # Gera e persiste feed JSON com as 10 notícias iniciais
            setup_news_json_cache(app)
            # Pré-aquecer store incremental para categorias padrão
            setup_news_scheduler(app)

        # Configurar scheduler para sincronização automática
        with timed_operation("Configuração de sincronização automática"):
            setup_nvd_scheduler(app)
            setup_analytics_cache_scheduler(app)
        
        # Finalizar com sucesso
        terminal_feedback.success("✅ Open-Monitor inicializado com sucesso!")
        terminal_feedback.info("🌐 Para iniciar o servidor web, execute: flask run -p 4443", 
                             {"url": "http://localhost:4443", "command": "flask run -p 4443"})
        terminal_feedback.info("🔄 Sincronização automática NVD configurada para executar a cada 1 hora; notícias atualizadas periodicamente")
        
        # Parar indicadores visuais
        time.sleep(2)  # Dar tempo para ver as mensagens finais
        status_indicator.stop_display()
        
        return True
        
    except Exception as e:
        # Usar sistema de erro aprimorado
        terminal_feedback.error("❌ Erro durante inicialização", 
                              context={"error_type": type(e).__name__, "error_message": str(e)},
                              suggestion="Verifique as configurações e dependências")
        
        # Parar indicadores visuais em caso de erro
        status_indicator.stop_display()
        
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 Inicialização concluída com sucesso!")
        print("💡 Execute 'flask run' para iniciar o servidor")
        sys.exit(0)
    else:
        print("\n❌ Inicialização falhou!")
        sys.exit(1)

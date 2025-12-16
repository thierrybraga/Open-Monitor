#!/usr/bin/env python3
import sys
import os
import subprocess
import time
import json
import uuid
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def _check_python_version():
    v = sys.version_info
    return not (v.major < 3 or (v.major == 3 and v.minor < 11))

def _check_requirements():
    try:
        import flask
        import sqlalchemy
        return True
    except Exception:
        return False

def _docker_available():
    try:
        subprocess.run(['docker', '--version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'compose', 'version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def _start_compose_stack():
    compose_file = str(Path(__file__).parent / 'docker-compose.yml')
    env = os.environ.copy()
    secret = os.getenv('SECRET_KEY') or str(uuid.uuid4())
    envfile = None
    inst_env = str(Path(__file__).parent / 'instance' / 'docker.env')
    if os.path.exists(inst_env):
        envfile = inst_env
    else:
        import tempfile
        fd, envfile = tempfile.mkstemp(prefix='openmonitor-', suffix='.env')
        os.close(fd)
        env_core_pw = env.get('POSTGRES_CORE_PASSWORD', 'Passw0rdCore')
        env_public_pw = env.get('POSTGRES_PUBLIC_PASSWORD', 'Passw0rdPublic')
        with open(envfile, 'w', encoding='utf-8') as f:
            f.write(f"SECRET_KEY={secret}\n")
            f.write(f"POSTGRES_CORE_PASSWORD={env_core_pw}\n")
            f.write(f"POSTGRES_PUBLIC_PASSWORD={env_public_pw}\n")
    try:
        subprocess.run(['docker','compose','-f', compose_file, '--env-file', envfile, 'up','-d','--build'], check=True, env=env)
    except subprocess.CalledProcessError:
        return False
    return True

def _compile_app():
    try:
        import subprocess as sp
        res = sp.run([sys.executable, '-m', 'compileall', '-q', 'app'], check=True)
        return res.returncode == 0
    except Exception:
        return False

def _pre_start_cleanup():
    try:
        root = Path(__file__).parent
        targets = [
            root / 'logs',
            root / 'cache',
            root / 'instance' / 'cache',
            root / 'instance' / 'tmp',
            root / 'app' / 'static' / '.cache',
            root / '.pytest_cache'
        ]
        for t in targets:
            try:
                if t.exists():
                    if t.is_dir():
                        for p in t.iterdir():
                            try:
                                if p.is_dir(): shutil.rmtree(p, ignore_errors=True)
                                else: p.unlink(missing_ok=True)
                            except Exception:
                                pass
                    else:
                        t.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

def _configure_dev_cache_controls(app):
    try:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        @app.after_request
        def _no_store(resp):
            try:
                resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                resp.headers['Pragma'] = 'no-cache'
                resp.headers['Expires'] = '0'
            except Exception:
                pass
            return resp
    except Exception:
        pass

def _flush_server_caches(app):
    try:
        from app.services.redis_cache_service import RedisCacheService
        cfg_nvd = {
            'REDIS_CACHE_ENABLED': app.config.get('REDIS_CACHE_ENABLED', False),
            'REDIS_URL': app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
            'REDIS_HOST': app.config.get('REDIS_HOST', 'localhost'),
            'REDIS_PORT': app.config.get('REDIS_PORT', 6379),
            'REDIS_DB': app.config.get('REDIS_DB', 0),
            'REDIS_PASSWORD': app.config.get('REDIS_PASSWORD'),
            'CACHE_KEY_PREFIX': 'nvd_cache:'
        }
        cfg_an = dict(cfg_nvd)
        cfg_an['CACHE_KEY_PREFIX'] = 'analytics_cache:'
        for cfg in (cfg_nvd, cfg_an):
            try:
                rc = RedisCacheService(cfg)
                if getattr(rc, 'enabled', False):
                    rc.clear_all()
            except Exception:
                pass
    except Exception:
        pass

def _start_dev_sqlite():
    os.environ['FLASK_ENV'] = 'development'
    _pre_start_cleanup()
    from app import create_app
    from app.main_startup import initialize_database
    app = create_app('development')
    with app.app_context():
        ok = initialize_database(app)
        if not ok:
            print("❌ Falha na inicialização do banco de dados")
            sys.exit(1)
    _compile_app()
    port = int(os.getenv('PORT', os.getenv('FLASK_RUN_PORT', '4443')))
    try:
        with app.app_context():
            _flush_server_caches(app)
        _configure_dev_cache_controls(app)
        auto_sync = os.getenv('START_NVD_SYNC_ON_STARTUP', 'true').lower() in ('1','true','yes')
        if auto_sync:
            import threading, urllib.request
            def _auto():
                base = f"http://localhost:{port}"
                deadline = time.time() + 600  # até 10 min aguardando root e disparo
                printed_init_hint = False
                while time.time() < deadline:
                    status = None
                    try:
                        raw = urllib.request.urlopen(f"{base}/api/v1/system/bootstrap", timeout=8).read().decode('utf-8')
                        status = json.loads(raw)
                    except Exception:
                        time.sleep(3)
                        continue
                    try:
                        if isinstance(status, dict):
                            has_active = bool(status.get('has_active_user'))
                            require_root = bool(status.get('require_root_setup'))
                            first_done = bool(status.get('first_sync_completed'))
                            in_progress = bool(status.get('sync_in_progress'))
                            if not has_active or require_root:
                                if not printed_init_hint:
                                    print(f"➡️ Abra http://localhost:{port}/auth/init-root para criar o usuário root")
                                    printed_init_hint = True
                                time.sleep(5)
                                continue
                            if first_done:
                                print("✅ Primeira sincronização já concluída")
                                break
                            if in_progress:
                                # Apenas acompanhar loading; não disparar novamente
                                print(f"ℹ️ Sincronização em andamento. Acompanhe em http://localhost:{port}/loading")
                                break
                            full = os.getenv('NVD_SYNC_FULL', 'false').lower() in ('1','true','yes')
                            mp = os.getenv('NVD_SYNC_MAX_PAGES')
                            payload = {'full': full}
                            if mp and str(mp).isdigit():
                                payload['max_pages'] = int(mp)
                            req = urllib.request.Request(
                                f"{base}/api/v1/sync/trigger",
                                data=json.dumps(payload).encode('utf-8'),
                                headers={'Content-Type': 'application/json'},
                                method='POST'
                            )
                            try:
                                urllib.request.urlopen(req, timeout=30)
                                print(f"➡️ Sincronização disparada. Acompanhe em http://localhost:{port}/loading")
                                break
                            except Exception:
                                time.sleep(5)
                                continue
                    except Exception:
                        time.sleep(5)
                        continue
            threading.Thread(target=_auto, daemon=True).start()
    except Exception:
        pass
    print("🌐 Executando em modo desenvolvimento (SQLite)")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def _start_dev_postgres_compose():
    if not _docker_available():
        print("❌ Docker não disponível")
        sys.exit(1)
    ok = _start_compose_stack()
    if not ok:
        print("❌ Falha ao subir Docker Compose")
        sys.exit(1)
    print("✅ Stack Docker iniciada. Acesse http://localhost:4443/")

def _start_prod_local():
    if os.name == 'nt':
        print("ℹ️ Em Windows, use Docker Compose para produção")
        _start_dev_postgres_compose()
        return
    try:
        env = os.environ.copy()
        env.setdefault('FLASK_APP', 'app.app:create_app')
        env.setdefault('FLASK_ENV', 'production')
        if not env.get('DATABASE_URL'):
            root = Path(__file__).parent
            core_db = root / 'instance' / 'om_prod_core.sqlite'
            pub_db = root / 'instance' / 'om_prod_public.sqlite'
            env['DATABASE_URL'] = f"sqlite:///{core_db}"
            env['PUBLIC_DATABASE_URL'] = f"sqlite:///{pub_db}"
        subprocess.run([sys.executable, '-m', 'compileall', '-q', 'app'], check=True)
        subprocess.run(['flask','db','upgrade'], check=True, env=env)
        from app import create_app
        from app.main_startup import initialize_database
        app = create_app('production')
        with app.app_context():
            initialize_database(app)
        subprocess.run(['gunicorn','--bind',f"0.0.0.0:{os.getenv('PORT','4443')}",'--workers',os.getenv('WEB_CONCURRENCY','3'),'--threads',os.getenv('GUNICORN_THREADS','4'),'wsgi:application'], check=True)
    except Exception as e:
        print(f"❌ Erro ao iniciar produção local: {e}")
        sys.exit(1)

def _deploy_cloud_run():
    try:
        subprocess.run(['gcloud','--version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print("ℹ️ gcloud não encontrado. Execute manualmente:")
        print("gcloud builds submit --tag gcr.io/SEU_PROJETO/openmonitor")
        print("gcloud run deploy openmonitor --image gcr.io/SEU_PROJETO/openmonitor --platform managed --region us-central1 --allow-unauthenticated")
        return
    image = os.getenv('GCR_IMAGE','gcr.io/SEU_PROJETO/openmonitor')
    region = os.getenv('GCR_REGION','us-central1')
    service = os.getenv('GCR_SERVICE','openmonitor')
    try:
        subprocess.run(['gcloud','builds','submit','--tag',image], check=True)
        subprocess.run(['gcloud','run','deploy',service,'--image',image,'--platform','managed','--region',region,'--allow-unauthenticated'], check=True)
        print("✅ Deploy realizado")
    except Exception as e:
        print(f"❌ Erro no deploy Cloud Run: {e}")

def _print_menu():
    print("\nOpen-Monitor")
    print("1) Dev SQLite")
    print("2) Dev Postgres + Docker")
    print("3) Produção local")
    print("4) Deploy Cloud Run")
    print("5) Sair")
    print("6) Deploy Heroku (instruções)")

def _main():
    if not _check_python_version():
        print("❌ Python 3.11+ requerido")
        sys.exit(1)
    _check_requirements()
    choice = os.getenv('OM_START_MODE')
    if not choice:
        _print_menu()
        try:
            choice = input('> ').strip()
        except Exception:
            choice = '1'
    if choice == '1':
        _start_dev_sqlite()
    elif choice == '2':
        _start_dev_postgres_compose()
    elif choice == '3':
        _start_prod_local()
    elif choice == '4':
        _deploy_cloud_run()
    elif choice == '6':
        print("Use Procfile, runtime.txt e Heroku Container Registry.")
        print("1) heroku create <app>")
        print("2) heroku addons:create heroku-postgresql")
        print("3) heroku addons:create heroku-redis")
        print("4) heroku container:login")
        print("5) heroku container:push web -a <app>")
        print("6) heroku container:release web -a <app>")
        print("7) heroku config:set SECRET_KEY=... PUBLIC_MODE=true SESSION_COOKIE_SECURE=true")
    else:
        print("Saindo")

if __name__ == '__main__':
    try:
        _main()
    except KeyboardInterrupt:
        print("\n🛑 Interrompido")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)

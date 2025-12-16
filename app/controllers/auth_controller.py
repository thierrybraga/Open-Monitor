# project/controllers/auth_controller.py

import logging # Importar logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user # Importações CORRETAS do Flask-Login
from sqlalchemy.exc import IntegrityError, SQLAlchemyError # Importar SQLAlchemyError
from urllib.parse import urlparse # Já importado

# Importação da instância db do pacote extensions
from app.extensions import db
# Importação do modelo User
from app.models.user import User
# Importação dos formulários
from app.forms.auth_form import LoginForm, RegisterForm, RootInitForm
from app.extensions import login_manager
from app.utils.security import (
    rate_limiter, get_client_ip, log_security_event, 
    require_rate_limit, sanitize_input, record_login_start,
    record_successful_login
)
from app.utils.auth_errors import AuthErrorHandler

logger = logging.getLogger(__name__) # Adicionado logger

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# Função removida - agora usando AuthErrorHandler.flash_form_errors()

# Utilitário local: verificar se Flask-Login está disponível (não inicializado em PUBLIC_MODE)
def _is_login_available() -> bool:
    try:
        lm = getattr(current_app, 'login_manager', None)
        return lm is not None
    except Exception:
        return False

@auth_bp.route('/login', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=5, window_minutes=15)
def login() -> str: # Adicionado type hinting (retorna string - HTML renderizado ou URL de redirecionamento)
    """Rota de login de usuário."""
    # Evitar acesso a current_user quando Flask-Login não está inicializado (PUBLIC_MODE)
    force = request.args.get('force', '').lower()
    if _is_login_available():
        # Se o usuário já estiver autenticado, redirecionar para a página principal,
        # a menos que o acesso seja forçado com ?force=true (útil para depuração/alternar contas)
        if getattr(current_user, 'is_authenticated', False) and force != 'true':
            return redirect(url_for('main.index'))
    else:
        # Em modo público, apenas renderizar a página sem tentar autenticação
        # e informar ao usuário que login está desabilitado.
        form = LoginForm()
        flash('Login desabilitado no modo público.', 'info')
        try:
            from app.models.sync_metadata import SyncMetadata
            first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
            status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
            first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
            status_val = str(status_meta.value or '').strip().lower() if status_meta and status_meta.value is not None else ''
            sync_in_progress = (first_done_val not in ('1','true','yes')) or (status_val in ('processing','saving'))
        except Exception:
            sync_in_progress = False
        return render_template('auth/login.html', form=form, sync_in_progress=sync_in_progress)

    form = LoginForm()

    # Processar submissão do formulário (POST)
    if form.validate_on_submit():
        client_ip = get_client_ip()
        username_or_email = sanitize_input(form.username.data.strip().lower())
        
        # Registrar início da tentativa de login para tracking de duração
        record_login_start()
        
        # Registrar tentativa de login
        rate_limiter.record_attempt(client_ip)
        
        # Buscar usuário pelo nome de usuário ou email
        logger.debug(f"Login attempt for: {username_or_email}")
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()
        logger.debug(f"User found: {bool(user)}")

        # Verificar usuário e senha
        pwd_ok = False
        if user:
            try:
                pwd_ok = user.check_password(form.password.data)
            except Exception:
                pwd_ok = False
        logger.debug(f"Password match: {pwd_ok}")
        if user and pwd_ok:
            # Login bem-sucedido (removida verificação de conta ativa)
            rate_limiter.clear_attempts(client_ip)  # Limpar tentativas após sucesso
            login_user(user, remember=form.remember_me.data)
            
            # Registrar informações do login bem-sucedido
            record_successful_login(user.id, user.username)
            
            AuthErrorHandler.handle_success('login', user=user)
            try:
                from app.models.sync_metadata import SyncMetadata
                first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
                first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
                if first_done_val not in ('1','true','yes'):
                    return redirect(url_for('main.loading'))
            except Exception:
                pass
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc != '' and urlparse(next_page).netloc != urlparse(request.host_url).netloc:
                 next_page = url_for('main.index')
            elif not next_page:
                 next_page = url_for('main.index')
            return redirect(next_page)

        # Credenciais inválidas
        AuthErrorHandler.handle_login_error('invalid_credentials', user=user, username=form.username.data)

    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         AuthErrorHandler.flash_form_errors(form)

    try:
        from app.models.sync_metadata import SyncMetadata
        first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
        status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
        first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
        status_val = str(status_meta.value or '').strip().lower() if status_meta and status_meta.value is not None else ''
        sync_in_progress = (first_done_val not in ('1','true','yes')) or (status_val in ('processing','saving'))
    except Exception:
        sync_in_progress = False
    return render_template('auth/login.html', form=form, sync_in_progress=sync_in_progress)


@auth_bp.route('/logout', methods=['POST']) # A rota logout DEVE ser POST por segurança
def logout() -> str: # Adicionado type hinting
    """Rota de logout de usuário."""
    # Evitar acesso a current_user/logout_user quando Flask-Login não está disponível
    if _is_login_available():
        user_id = current_user.id if getattr(current_user, 'is_authenticated', False) else None
        username = current_user.username if getattr(current_user, 'is_authenticated', False) else None
        # Flask-Login logout_user() lida com a remoção da sessão
        try:
            logout_user()
        except Exception:
            pass
        AuthErrorHandler.handle_success('logout', user_id=user_id, username=username)
    else:
        flash('Logout indisponível em modo público.', 'info')
    
    # Redirecionar para a página principal ou login
    return redirect(url_for('main.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=3, window_minutes=10)
def register() -> str: # Adicionado type hinting
    """Rota de registro de novo usuário."""
    # Evitar acesso a current_user quando Flask-Login não está inicializado (PUBLIC_MODE)
    if _is_login_available():
        # Se o usuário já estiver autenticado, redirecionar para a página principal
        if getattr(current_user, 'is_authenticated', False):
            return redirect(url_for('main.index'))

    form = RegisterForm()

    # Processar submissão do formulário (POST)
    if form.validate_on_submit():
        # Criar novo objeto User
        try:
            # Sanitizar dados de entrada
            username = sanitize_input(form.username.data, 50)
            email = sanitize_input(form.email.data, 255)
            first_name = sanitize_input(form.first_name.data, 50) if form.first_name.data else None
            last_name = sanitize_input(form.last_name.data, 50) if form.last_name.data else None
            phone = sanitize_input(form.phone.data, 20) if form.phone.data else None
            
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone
            )
            # A validação de senha deve ocorrer no formulário ou no modelo
            user.set_password(form.password.data) # Define a senha usando o método do modelo
            
            first_user = (db.session.query(User).count() == 0)
            if first_user:
                return redirect(url_for('auth.init_root'))
            else:
                user.is_active = False
                confirmation_token = user.generate_confirmation_token()
                try:
                    from datetime import datetime, timedelta, timezone
                    user.trial_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                except Exception:
                    user.trial_expires_at = None

            # Salvar usuário no banco de dados
            db.session.add(user)
            try:
                root = db.session.query(User).filter_by(is_admin=True).first()
            except Exception:
                root = None
            if root:
                try:
                    user.root_user_id = root.id
                except Exception:
                    pass
            db.session.commit()
            
            if not first_user:
                try:
                    from app.services.email_service import EmailService
                    email_service = EmailService()
                    confirmation_url = url_for('auth.confirm_email', token=confirmation_token, _external=True)
                    if email_service.send_email_confirmation(user.email, user.username, confirmation_url):
                        flash('Registro realizado com sucesso! Verifique seu email para ativar sua conta.', 'success')
                    else:
                        flash('Conta criada, mas houve um problema ao enviar o email de confirmação. Entre em contato com o suporte.', 'warning')
                except Exception as e:
                    logger.error(f"Erro ao enviar email de confirmação: {e}")
                    flash('Conta criada, mas houve um problema ao enviar o email de confirmação. Entre em contato com o suporte.', 'warning')
                return redirect(url_for('main.index'))
            else:
                return redirect(url_for('auth.init_root'))

        except Exception as e:
            # Usar o tratamento centralizado de erros
            AuthErrorHandler.handle_register_error(e, form.username.data, db.session)


    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         AuthErrorHandler.flash_form_errors(form)


    return render_template('auth/register.html', form=form)


@auth_bp.route('/init-root', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=3, window_minutes=10)
def init_root() -> str:
    if (
        db.session.query(User).filter((User.is_active == True) & (User.password_hash.isnot(None))).count() > 0
        or db.session.query(User).filter(User.is_admin == True).count() > 0
    ):
        return redirect(url_for('main.index'))
    form = RootInitForm()
    if form.validate_on_submit():
        try:
            try:
                from sqlalchemy import inspect, text
                insp = inspect(db.engine)
                cols = {c['name'] for c in insp.get_columns('users')}
                if 'root_user_id' not in cols:
                    try:
                        db.session.execute(text('ALTER TABLE users ADD COLUMN root_user_id INTEGER'))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            except Exception:
                pass
            username = sanitize_input(form.username.data, 50)
            email = sanitize_input(form.email.data, 255)
            first_name = sanitize_input(form.first_name.data, 50)
            last_name = sanitize_input(form.last_name.data, 50)
            phone = sanitize_input(form.phone.data, 20) if form.phone.data else None
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone
            )
            user.set_password(form.password.data)
            user.is_active = True
            user.email_confirmed = True
            user.email_confirmation_token = None
            user.email_confirmation_sent_at = None
            user.is_admin = True
            if form.tacacs_enabled.data:
                user.tacacs_enabled = True
                user.tacacs_username = sanitize_input(form.tacacs_username.data or '') or None
                user.tacacs_secret = sanitize_input(form.tacacs_secret.data or '') or None
                user.tacacs_server = sanitize_input(form.tacacs_server.data or '') or None
                try:
                    user.tacacs_port = int((form.tacacs_port.data or '49').strip())
                except Exception:
                    user.tacacs_port = 49
                try:
                    user.tacacs_timeout = int((form.tacacs_timeout.data or '5').strip())
                except Exception:
                    user.tacacs_timeout = 5
            db.session.add(user)
            db.session.commit()
            try:
                user.root_user_id = user.id
                db.session.commit()
            except Exception:
                pass
            try:
                from app.models.sync_metadata import SyncMetadata
                from sqlalchemy import text
                from flask import current_app
                entries = [
                    ('system:root_user_id', str(user.id)),
                    ('system:root_username', user.username or ''),
                    ('system:root_email', user.email or ''),
                    ('system:default_vendor_scope', 'all')
                ]
                if getattr(user, 'tacacs_enabled', False):
                    entries.extend([
                        ('system:tacacs_enabled', '1'),
                        ('system:tacacs_username', user.tacacs_username or ''),
                        ('system:tacacs_secret', user.tacacs_secret or ''),
                        ('system:tacacs_server', user.tacacs_server or ''),
                        ('system:tacacs_port', str(user.tacacs_port)),
                        ('system:tacacs_timeout', str(user.tacacs_timeout)),
                    ])
                entries.append(('require_root_setup', 'false'))
                try:
                    core_user = user.username or 'root'
                    core_pass = form.password.data
                    pub_user = core_user
                    pub_pass = core_pass
                    entries.extend([
                        ('system:db_core_user', core_user),
                        ('system:db_core_password', core_pass),
                        ('system:db_public_user', pub_user),
                        ('system:db_public_password', pub_pass)
                    ])
                    try:
                        db.session.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{core_user}') THEN CREATE ROLE {core_user} LOGIN PASSWORD '{core_pass}'; END IF; END $$;"))
                    except Exception:
                        pass
                    try:
                        core_db = current_app.config.get('POSTGRES_CORE_DB', 'openmonitor_core') or 'openmonitor_core'
                        db.session.execute(text(f"GRANT ALL PRIVILEGES ON DATABASE \"{core_db}\" TO {core_user};"))
                    except Exception:
                        pass
                    try:
                        db.session.execute(text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {core_user};"))
                        db.session.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {core_user};"))
                    except Exception:
                        pass
                    try:
                        pub_engine = db.get_engine(current_app, bind='public')
                        with pub_engine.connect() as conn:
                            conn.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{pub_user}') THEN CREATE ROLE {pub_user} LOGIN PASSWORD '{pub_pass}'; END IF; END $$;"))
                            pub_db = current_app.config.get('POSTGRES_PUBLIC_DB', 'openmonitor_public') or 'openmonitor_public'
                            conn.execute(text(f"GRANT ALL PRIVILEGES ON DATABASE \"{pub_db}\" TO {pub_user};"))
                            conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {pub_user};"))
                            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {pub_user};"))
                    except Exception:
                        pass
                except Exception:
                    pass
                for k, v in entries:
                    sm = db.session.query(SyncMetadata).filter_by(key=k).first()
                    if sm:
                        sm.value = v
                    else:
                        sm = SyncMetadata(key=k, value=v)
                        db.session.add(sm)
                db.session.commit()
            except Exception:
                db.session.rollback()
            try:
                login_user(user, remember=False)
            except Exception:
                pass
            try:
                from app.models.sync_metadata import SyncMetadata
                status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                status_val = (status_meta.value or '').strip().lower() if status_meta and status_meta.value else ''
                if status_val not in ('processing','saving'):
                    if not status_meta:
                        status_meta = SyncMetadata(key='nvd_sync_progress_status', value='processing')
                        db.session.add(status_meta)
                    else:
                        status_meta.value = 'processing'
                    current_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                    if not current_meta:
                        current_meta = SyncMetadata(key='nvd_sync_progress_current', value='0')
                        db.session.add(current_meta)
                    else:
                        current_meta.value = '0'
                    sched_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_scheduled').first()
                    if not sched_meta:
                        sched_meta = SyncMetadata(key='nvd_first_sync_scheduled', value='1')
                        db.session.add(sched_meta)
                    else:
                        sched_meta.value = '1'
                    db.session.commit()

                    import threading, asyncio
                    from flask import current_app
                    from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
                    app_obj = current_app._get_current_object()
                    def _run_sync():
                        try:
                            import os
                            workers_raw = os.getenv('OM_SYNC_WORKERS','10')
                            try:
                                max_workers = int(workers_raw)
                            except Exception:
                                max_workers = 10
                            fetcher = EnhancedNVDFetcher(app=app_obj, max_workers=max_workers, enable_cache=True)
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                mode = str(os.getenv('OM_SYNC_MODE','pipeline')).strip().lower()
                                loop.run_until_complete(fetcher.sync_nvd(full=True, max_pages=None, use_parallel=(mode != 'sequential')))
                            finally:
                                loop.close()
                        except Exception:
                            try:
                                sm = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                                if sm:
                                    sm.value = 'idle'
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                    threading.Thread(target=_run_sync, daemon=True).start()
            except Exception:
                pass
            try:
                inst = current_app.instance_path
                os.makedirs(inst, exist_ok=True)
                env_path = os.path.join(inst, 'docker.env')
                core_host = os.getenv('POSTGRES_CORE_HOST', 'postgres_core')
                core_db = os.getenv('POSTGRES_CORE_DB', 'openmonitor_core')
                pub_host = os.getenv('POSTGRES_PUBLIC_HOST', 'postgres_public')
                pub_db = os.getenv('POSTGRES_PUBLIC_DB', 'openmonitor_public')
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(f"POSTGRES_CORE_USER={user.username}\n")
                    f.write(f"POSTGRES_CORE_PASSWORD={form.password.data}\n")
                    f.write(f"POSTGRES_CORE_HOST={core_host}\n")
                    f.write(f"POSTGRES_CORE_DB={core_db}\n")
                    f.write(f"POSTGRES_PUBLIC_USER={user.username}\n")
                    f.write(f"POSTGRES_PUBLIC_PASSWORD={form.password.data}\n")
                    f.write(f"POSTGRES_PUBLIC_HOST={pub_host}\n")
                    f.write(f"POSTGRES_PUBLIC_DB={pub_db}\n")
            except Exception:
                pass
            flash('Usuário root criado e ativado.', 'success')
            return redirect(url_for('main.loading'))
        except Exception as e:
            AuthErrorHandler.handle_register_error(e, form.username.data, db.session)
    elif request.method == 'POST':
        AuthErrorHandler.flash_form_errors(form)
    return render_template('auth/init_root.html', form=form)


@auth_bp.route('/check-availability', methods=['POST'])
@require_rate_limit(max_attempts=20, window_minutes=5)
def check_availability():
    """API para verificar disponibilidade de username e email em tempo real."""
    from flask import jsonify
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados inválidos'}), 400
    
    field_type = data.get('type')  # 'username' ou 'email'
    value = data.get('value', '').strip()
    
    if not field_type or not value:
        return jsonify({'error': 'Tipo e valor são obrigatórios'}), 400
    
    # Sanitizar entrada
    value = sanitize_input(value)
    
    try:
        if field_type == 'username':
            # Verificar se username já existe
            existing_user = User.query.filter_by(username=value.lower()).first()
            available = existing_user is None
            message = 'Nome de usuário disponível' if available else 'Nome de usuário já está em uso'
            
        elif field_type == 'email':
            # Verificar se email já existe
            existing_user = User.query.filter_by(email=value.lower()).first()
            available = existing_user is None
            message = 'E-mail disponível' if available else 'E-mail já está cadastrado'
            
        else:
            error_response, status_code = AuthErrorHandler.handle_api_error('invalid_request')
            return jsonify(error_response), status_code
        
        return jsonify({
            'available': available,
            'message': message
        })
        
    except Exception as e:
        error_response, status_code = AuthErrorHandler.handle_api_error(
            'availability_check', field_type=field_type, exception=e
        )
        return jsonify(error_response), status_code


@auth_bp.route('/confirm-email/<token>')
def confirm_email(token):
    """Rota para confirmação de email."""
    try:
        # Buscar usuário pelo token
        user = User.query.filter_by(email_confirmation_token=token).first()
        
        if not user:
            flash('Token de confirmação inválido ou expirado.', 'error')
            return redirect(url_for('main.index'))
        
        # Verificar se o email já foi confirmado
        if user.email_confirmed:
            flash('Email já foi confirmado anteriormente.', 'info')
            return redirect(url_for('main.index'))
        
        # Confirmar email
        if user.confirm_email(token):
            db.session.commit()
            log_security_event(
                'email_confirmed',
                user_id=user.id,
                details={'email': user.email}
            )
            flash('Email confirmado com sucesso! Aguarde aprovação do administrador.', 'success')
        else:
            flash('Token de confirmação expirado. Solicite um novo email de confirmação.', 'error')
        
        return redirect(url_for('main.index'))
        
    except Exception as e:
        logger.error(f"Erro na confirmação de email: {e}")
        flash('Erro interno. Tente novamente mais tarde.', 'error')
        return redirect(url_for('main.index'))


@auth_bp.route('/resend-confirmation', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=3, window_minutes=15)
def resend_confirmation():
    """Rota para reenviar email de confirmação."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Email é obrigatório.', 'error')
            return render_template('auth/resend_confirmation.html')
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if not user:
                # Por segurança, não revelar se o email existe ou não
                flash('Se o email estiver cadastrado, você receberá um novo link de confirmação.', 'info')
                return render_template('auth/resend_confirmation.html')
            
            if user.email_confirmed:
                flash('Este email já foi confirmado.', 'info')
                return redirect(url_for('main.index'))
            
            # Gerar novo token
            confirmation_token = user.generate_confirmation_token()
            db.session.commit()
            
            # Enviar novo email
            try:
                from app.services.email_service import EmailService
                email_service = EmailService()
                confirmation_url = url_for('auth.confirm_email', token=confirmation_token, _external=True)
                
                if email_service.send_email_confirmation(user.email, user.username, confirmation_url):
                    flash('Novo email de confirmação enviado! Verifique sua caixa de entrada.', 'success')
                else:
                    flash('Erro ao enviar email. Tente novamente mais tarde.', 'error')
            except Exception as e:
                logger.error(f"Erro ao reenviar email de confirmação: {e}")
                flash('Erro ao enviar email. Tente novamente mais tarde.', 'error')
            
            return redirect(url_for('main.index'))
            
        except Exception as e:
            logger.error(f"Erro ao reenviar confirmação: {e}")
            flash('Erro interno. Tente novamente mais tarde.', 'error')
    
    return render_template('auth/resend_confirmation.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=3, window_minutes=15)
def forgot_password():
    """Rota para solicitar recuperação de senha."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Email é obrigatório.', 'error')
            return render_template('auth/forgot_password.html')
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if user and user.is_active:
                # Gerar token de recuperação
                reset_token = user.generate_password_reset_token()
                db.session.commit()
                
                # Enviar email de recuperação
                try:
                    from app.services.email_service import EmailService
                    email_service = EmailService()
                    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
                    
                    if email_service.send_password_reset(user.email, user.username, reset_url):
                        log_security_event(
                            'password_reset_requested',
                            user_id=user.id,
                            details={'email': user.email}
                        )
                    else:
                        logger.error(f"Falha ao enviar email de recuperação para {user.email}")
                except Exception as e:
                    logger.error(f"Erro ao enviar email de recuperação: {e}")
            
            # Por segurança, sempre mostrar a mesma mensagem
            flash('Se o email estiver cadastrado e ativo, você receberá um link para redefinir sua senha.', 'info')
            return redirect(url_for('main.index'))
            
        except Exception as e:
            logger.error(f"Erro na solicitação de recuperação de senha: {e}")
            flash('Erro interno. Tente novamente mais tarde.', 'error')
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Rota para redefinir senha usando token."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    try:
        # Buscar usuário pelo token
        user = User.query.filter_by(password_reset_token=token).first()
        
        if not user:
            flash('Token de recuperação inválido ou expirado.', 'error')
            return redirect(url_for('auth.forgot_password'))
        
        # Verificar se o token não expirou
        if user.is_password_reset_token_expired():
            flash('Token de recuperação expirado. Solicite um novo link.', 'error')
            return redirect(url_for('auth.forgot_password'))
        
        if request.method == 'POST':
            new_password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not new_password or not confirm_password:
                flash('Todos os campos são obrigatórios.', 'error')
                return render_template('auth/reset_password.html', token=token)
            
            if new_password != confirm_password:
                flash('As senhas não coincidem.', 'error')
                return render_template('auth/reset_password.html', token=token)
            
            if len(new_password) < 8:
                flash('A senha deve ter pelo menos 8 caracteres.', 'error')
                return render_template('auth/reset_password.html', token=token)
            
            # Redefinir senha
            if user.reset_password(token, new_password):
                db.session.commit()
                
                log_security_event(
                    'password_reset_completed',
                    user_id=user.id,
                    details={'email': user.email}
                )
                
                flash('Senha redefinida com sucesso! Você pode fazer login agora.', 'success')
                return redirect(url_for('main.index'))
            else:
                flash('Erro ao redefinir senha. Token pode ter expirado.', 'error')
        return redirect(url_for('auth.forgot_password'))

        return render_template('auth/reset_password.html', token=token)
        
    except Exception as e:
        logger.error(f"Erro na redefinição de senha: {e}")
        flash('Erro interno. Tente novamente mais tarde.', 'error')
        return redirect(url_for('auth.forgot_password'))


@auth_bp.route('/pending-users')
@login_required
def pending_users():
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('main.index'))
    users = db.session.query(User).filter((User.is_active == False)).order_by(User.created_at.asc()).all()
    return render_template('auth/pending_users.html', users=users)


@auth_bp.route('/approve-user/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id: int):
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('main.index'))
    try:
        user = db.session.query(User).get(user_id)
        if user and not user.is_active:
            from datetime import datetime, timezone
            user.is_active = True
            try:
                user.approved_by_user_id = int(current_user.id)
            except Exception:
                user.approved_by_user_id = None
            try:
                user.approved_at = datetime.now(timezone.utc)
            except Exception:
                user.approved_at = None
            try:
                from app.extensions.middleware import audit_log
                audit_log('approve_user', 'user', str(user.id), {'approved_by': int(current_user.id)})
            except Exception:
                pass
            db.session.commit()
            flash('Usuário aprovado com sucesso.', 'success')
        else:
            flash('Usuário inválido ou já aprovado.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Erro ao aprovar usuário.', 'error')
    return redirect(url_for('auth.pending_users'))

@auth_bp.route('/approved-users', methods=['GET'])
@login_required
def approved_users():
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('main.index'))
    try:
        approver_id = request.args.get('approver_id', '').strip()
        approver = None
        if approver_id.isdigit():
            approver = int(approver_id)
        else:
            try:
                root = db.session.query(User).filter(User.is_admin == True).order_by(User.id.asc()).first()
                approver = int(root.id) if root else None
            except Exception:
                approver = None
        q = db.session.query(User).filter(User.is_active == True)
        if approver:
            q = q.filter(User.approved_by_user_id == approver)
        rows = q.order_by(User.approved_at.desc().nullslast(), User.created_at.desc()).all()
        payload = [
            {
                'id': int(u.id),
                'username': u.username,
                'email': u.email,
                'approved_by_user_id': int(u.approved_by_user_id) if u.approved_by_user_id else None,
                'approved_at': (u.approved_at.isoformat() if u.approved_at else None),
                'root_user_id': int(u.root_user_id) if u.root_user_id else None,
            }
            for u in rows
        ]
        from flask import jsonify
        return jsonify({'success': True, 'users': payload}), 200
    except Exception as e:
        from flask import jsonify
        logger.error(f"Erro ao listar usuários aprovados: {e}")
        return jsonify({'success': False, 'error': 'Erro interno'}), 500

# project/controllers/auth_controller.py

import logging # Importar logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user # Importações CORRETAS do Flask-Login
from sqlalchemy.exc import IntegrityError, SQLAlchemyError # Importar SQLAlchemyError
from urllib.parse import urlparse # Já importado

# Importação da instância db do pacote extensions
from extensions import db
# Importação do modelo User
from models.user import User
# Importação dos formulários
from forms.auth_form import LoginForm, RegisterForm
from extensions import login_manager
from utils.security import (
    rate_limiter, get_client_ip, log_security_event, 
    require_rate_limit, sanitize_input
)
logger = logging.getLogger(__name__) # Adicionado logger

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def flash_form_errors(form: Any) -> None: # Adicionado type hinting
    """Flasha todos os erros do formulário de maneira padronizada e loga."""
    for field, errors in form.errors.items():
        for error in errors:
            # Usar .get() para acessar o label com segurança
            field_label = getattr(form, field, None)
            label_text = field_label.label.text if field_label and field_label.label else field
            flash(f"{label_text}: {error}", 'danger')
            logger.warning(f"Form error on field '{field}': {error}") # Log mais detalhado

@auth_bp.route('/login', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=5, window_minutes=15)
def login() -> str: # Adicionado type hinting (retorna string - HTML renderizado ou URL de redirecionamento)
    """Rota de login de usuário."""
    # Se o usuário já estiver autenticado, redirecionar para a página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    # Processar submissão do formulário (POST)
    if form.validate_on_submit():
        client_ip = get_client_ip()
        username_or_email = sanitize_input(form.username.data.strip().lower())
        
        # Registrar tentativa de login
        rate_limiter.record_attempt(client_ip)
        
        # Buscar usuário pelo nome de usuário ou email
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()

        # Verificar usuário e senha
        if user and user.check_password(form.password.data):
            # Verificar se a conta está ativa
            if not user.is_active:
                log_security_event('login_failed', user_id=user.id, username=user.username, 
                                 details={'reason': 'account_inactive'})
                flash('Sua conta está desativada. Entre em contato com o administrador.', 'danger')
                return render_template('auth/login.html', form=form)
            
            # Login bem-sucedido
            rate_limiter.clear_attempts(client_ip)  # Limpar tentativas após sucesso
            login_user(user, remember=form.remember_me.data)
            
            log_security_event('login_success', user_id=user.id, username=user.username)

            # Redirecionar para a próxima página se houver, caso contrário, para o index
            next_page = request.args.get('next')
            # Validar next_page para evitar Open Redirect: garantir que o host seja o mesmo
            # ou que a URL seja relativa. urlparse retorna netloc (rede location)
            # Se netloc existe E é diferente do host da requisição, é externo.
            if next_page and urlparse(next_page).netloc != '' and urlparse(next_page).netloc != urlparse(request.host_url).netloc:
                 logger.warning(f"Detected external redirect attempt: {next_page}. Redirecting to index.")
                 next_page = url_for('main.index')
            elif not next_page: # Se não há next_page, ir para index
                 next_page = url_for('main.index')

            logger.info(f"User {user.username} logged in successfully.")
            flash(f"Bem-vindo, {user.username}!", 'success') # Mensagem de boas-vindas
            return redirect(next_page)

        # Credenciais inválidas
        username_for_log = user.username if user else username_or_email
        user_id_for_log = user.id if user else None
        
        log_security_event('login_failed', user_id=user_id_for_log, username=username_for_log,
                         details={'reason': 'invalid_credentials'})
        flash('Usuário ou senha inválidos.', 'danger')
        logger.warning(f"Login failed for username: {form.username.data}")

    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         flash_form_errors(form)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout', methods=['POST']) # A rota logout DEVE ser POST por segurança
@login_required # Garante que apenas usuários logados podem acessar esta rota
def logout() -> str: # Adicionado type hinting
    """Rota de logout de usuário."""
    user_id = current_user.id if current_user.is_authenticated else None
    username = current_user.username if current_user.is_authenticated else None
    
    # Flask-Login logout_user() lida com a remoção da sessão
    logout_user()
    log_security_event('logout', user_id=user_id, username=username)
    flash('Logout realizado com sucesso.', 'success')
    logger.info("User logged out.")
    # Redirecionar para a página principal ou login
    return redirect(url_for('main.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@require_rate_limit(max_attempts=3, window_minutes=10)
def register() -> str: # Adicionado type hinting
    """Rota de registro de novo usuário."""
    # Se o usuário já estiver autenticado, redirecionar para a página principal
    if current_user.is_authenticated:
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

            # Salvar usuário no banco de dados
            with db.session.begin(): # Usar begin() para gerenciamento automático da transação
                db.session.add(user)

            log_security_event('register_success', user_id=user.id, username=user.username)
            flash('Cadastro realizado com sucesso. Faça login.', 'success')
            logger.info(f"New user registered: {user.username}.")
            return redirect(url_for('auth.login'))

        except IntegrityError:
            # Tratar caso de nome de usuário ou e-mail duplicado
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            log_security_event('register_failed', username=form.username.data,
                             details={'reason': 'duplicate_user_or_email'})
            flash('Nome de usuário ou e-mail já existem.', 'warning')
            logger.warning(f"Registration failed for username: {form.username.data} (IntegrityError).")

        except ValueError as ve:
            # Tratar erros de validação do modelo (ex: senha fraca, e-mail inválido)
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            log_security_event('register_failed', username=form.username.data,
                             details={'reason': 'validation_error', 'error': str(ve)})
            flash(f"Erro de validação: {ve}", 'danger')
            logger.warning(f"Registration validation error for {form.username.data}: {ve}")

        except SQLAlchemyError as e:
            # Tratar outros erros inesperados do banco de dados
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            log_security_event('register_failed', username=form.username.data,
                             details={'reason': 'database_error'})
            logger.error(f"DB error during registration for user {form.username.data}: {e}", exc_info=True)
            flash('Erro interno do banco de dados durante o registro. Tente novamente.', 'danger')

        except Exception as e:
            # Tratar outros erros inesperados
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            log_security_event('register_failed', username=form.username.data,
                             details={'reason': 'unexpected_error'})
            logger.error(f"An unexpected error occurred during registration for user {form.username.data}: {str(e)}", exc_info=True)
            flash('Erro interno inesperado durante o registro. Tente novamente.', 'danger')


    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         flash_form_errors(form)


    return render_template('auth/register.html', form=form)
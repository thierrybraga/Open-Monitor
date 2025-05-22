# project/controllers/auth_controller.py

import logging # Importar logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user # Importações CORRETAS do Flask-Login
from sqlalchemy.exc import IntegrityError, SQLAlchemyError # Importar SQLAlchemyError
from urllib.parse import urlparse # Já importado

# Importação CORRETA da instância db do pacote extensions
from ..extensions import db
# Importação CORRETA do modelo User (Assumindo que está em project/models)
from ..models.user import User
# Importação CORRETA dos formulários (Assumindo que estão em project/forms)
from ..forms.auth_form import LoginForm, RegisterForm
from ..extensions import login_manager # Se precisar da instância
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
def login() -> str: # Adicionado type hinting (retorna string - HTML renderizado ou URL de redirecionamento)
    """Rota de login de usuário."""
    # Se o usuário já estiver autenticado, redirecionar para a página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    # Processar submissão do formulário (POST)
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        # Verificar usuário e senha
        if user and user.check_password(form.password.data):
            # Fazer login do usuário usando Flask-Login
            login_user(user, remember=form.remember_me.data)

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
    # Flask-Login logout_user() lida com a remoção da sessão
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    logger.info("User logged out.")
    # Redirecionar para a página principal ou login
    return redirect(url_for('main.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
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
            user = User(username=form.username.data, email=form.email.data)
            # A validação de senha deve ocorrer no formulário ou no modelo
            user.set_password(form.password.data) # Define a senha usando o método do modelo

            # Salvar usuário no banco de dados
            with db.session.begin(): # Usar begin() para gerenciamento automático da transação
                db.session.add(user)

            flash('Cadastro realizado com sucesso. Faça login.', 'success')
            logger.info(f"New user registered: {user.username}.")
            return redirect(url_for('auth.login'))

        except IntegrityError:
            # Tratar caso de nome de usuário ou e-mail duplicado
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            flash('Nome de usuário ou e-mail já existem.', 'warning')
            logger.warning(f"Registration failed for username: {form.username.data} (IntegrityError).")

        except ValueError as ve:
            # Tratar erros de validação do modelo (ex: senha fraca, e-mail inválido)
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            flash(f"Erro de validação: {ve}", 'danger')
            logger.warning(f"Registration validation error for {form.username.data}: {ve}")

        except SQLAlchemyError as e:
            # Tratar outros erros inesperados do banco de dados
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            logger.error(f"DB error during registration for user {form.username.data}: {e}", exc_info=True)
            flash('Erro interno do banco de dados durante o registro. Tente novamente.', 'danger')

        except Exception as e:
            # Tratar outros erros inesperados
            # O rollback é feito automaticamente pelo with db.session.begin() em caso de exceção
            logger.error(f"An unexpected error occurred during registration for user {form.username.data}: {str(e)}", exc_info=True)
            flash('Erro interno inesperado durante o registro. Tente novamente.', 'danger')


    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         flash_form_errors(form)


    return render_template('auth/register.html', form=form)
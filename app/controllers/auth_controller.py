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
from app.forms.auth_form import LoginForm, RegisterForm
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
        
        # Registrar início da tentativa de login para tracking de duração
        record_login_start()
        
        # Registrar tentativa de login
        rate_limiter.record_attempt(client_ip)
        
        # Buscar usuário pelo nome de usuário ou email
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()

        # Verificar usuário e senha
        if user and user.check_password(form.password.data):
            # Login bem-sucedido (removida verificação de conta ativa)
            rate_limiter.clear_attempts(client_ip)  # Limpar tentativas após sucesso
            login_user(user, remember=form.remember_me.data)
            
            # Registrar informações do login bem-sucedido
            record_successful_login(user.id, user.username)
            
            AuthErrorHandler.handle_success('login', user=user)

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

            return redirect(next_page)

        # Credenciais inválidas
        AuthErrorHandler.handle_login_error('invalid_credentials', user=user, username=form.username.data)

    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         AuthErrorHandler.flash_form_errors(form)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout', methods=['POST']) # A rota logout DEVE ser POST por segurança
def logout() -> str: # Adicionado type hinting
    """Rota de logout de usuário."""
    user_id = current_user.id if current_user.is_authenticated else None
    username = current_user.username if current_user.is_authenticated else None
    
    # Flask-Login logout_user() lida com a remoção da sessão
    logout_user()
    AuthErrorHandler.handle_success('logout', user_id=user_id, username=username)
    
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
            
            # Definir usuário como inativo até confirmação do email
            user.is_active = False
            
            # Gerar token de confirmação
            confirmation_token = user.generate_confirmation_token()

            # Salvar usuário no banco de dados
            db.session.add(user)
            db.session.commit()
            
            # Enviar email de confirmação
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

        except Exception as e:
            # Usar o tratamento centralizado de erros
            AuthErrorHandler.handle_register_error(e, form.username.data, db.session)


    # Se GET request ou validação falhou em POST
    elif request.method == 'POST': # Flashar erros apenas em POST quando validação falha
         AuthErrorHandler.flash_form_errors(form)


    return render_template('auth/register.html', form=form)


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
            user.is_active = True  # Ativar conta após confirmação
            db.session.commit()
            
            log_security_event(
                'email_confirmed',
                user_id=user.id,
                details={'email': user.email}
            )
            
            flash('Email confirmado com sucesso! Sua conta está ativa.', 'success')
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

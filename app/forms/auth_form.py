# forms/auth_form.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, Regexp, ValidationError, Optional
)
from app.models.user import User
from app.utils.security import validate_password_strength
import re

class LoginForm(FlaskForm):
    username = StringField(
        'Usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
        ],
        render_kw={"placeholder": "Digite seu nome de usuário", "autocomplete": "username", "aria-describedby": "username-help", "autocapitalize": "none", "spellcheck": "false", "inputmode": "email", "minlength": 3, "maxlength": 50}
    )
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter pelo menos 8 caracteres.")
        ],
        render_kw={"placeholder": "Digite sua senha", "autocomplete": "current-password", "aria-describedby": "password-help", "minlength": 8, "maxlength": 128, "inputmode": "text"}
    )
    remember_me = BooleanField('Lembrar-me por 30 dias', render_kw={"aria-describedby": "remember-help"})
    submit = SubmitField('Entrar')





class RegisterForm(FlaskForm):
    username = StringField(
        'Nome de usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
            Regexp(
                r'^[A-Za-z0-9_]+$',
                message="Somente letras, números e underscore são permitidos."
            )
        ],
        render_kw={"placeholder": "Digite seu nome de usuário", "autocomplete": "username"}
    )
    
    first_name = StringField(
        'Nome',
        validators=[
            DataRequired(message="O nome é obrigatório."),
            Length(2, 50, message="Nome deve ter entre 2 e 50 caracteres."),
            Regexp(
                r'^[A-Za-zÀ-ÿ\s]+$',
                message="Nome deve conter apenas letras e espaços."
            )
        ],
        render_kw={"placeholder": "Digite seu nome", "autocomplete": "given-name"}
    )
    
    last_name = StringField(
        'Sobrenome',
        validators=[
            DataRequired(message="O sobrenome é obrigatório."),
            Length(2, 50, message="Sobrenome deve ter entre 2 e 50 caracteres."),
            Regexp(
                r'^[A-Za-zÀ-ÿ\s]+$',
                message="Sobrenome deve conter apenas letras e espaços."
            )
        ],
        render_kw={"placeholder": "Digite seu sobrenome", "autocomplete": "family-name"}
    )
    
    email = StringField(
        'E-mail',
        validators=[
            DataRequired(message="O e-mail é obrigatório."),
            Email(message="Formato de e-mail inválido."),
            Length(max=255, message="E-mail muito longo.")
        ],
        render_kw={"placeholder": "Digite seu e-mail", "autocomplete": "email"}
    )
    
    phone = StringField(
        'Telefone',
        validators=[
            Optional()
        ],
        render_kw={"placeholder": "(11) 99999-9999", "autocomplete": "tel"}
    )
    
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter entre 8 e 128 caracteres.")
        ],
        render_kw={"placeholder": "Digite uma senha forte", "autocomplete": "new-password"}
    )
    
    confirm_password = PasswordField(
        'Confirme a senha',
        validators=[
            DataRequired(message="Precisa confirmar a senha."),
            EqualTo('password', message="As senhas devem coincidir.")
        ],
        render_kw={"placeholder": "Confirme sua senha", "autocomplete": "new-password"}
    )
    
    terms_accepted = BooleanField(
        'Aceito os termos de uso e política de privacidade',
        validators=[
            DataRequired(message="Você deve aceitar os termos de uso.")
        ]
    )
    
    submit = SubmitField('Criar Conta')
    
    def validate_username(self, username):
        """Valida se o nome de usuário já existe."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nome de usuário já está em uso. Escolha outro.')
    
    def validate_email(self, email):
        """Valida se o e-mail já existe."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Este e-mail já está cadastrado. Faça login ou use outro e-mail.')
    
    def validate_password(self, password):
        """Valida a força da senha usando validação robusta."""
        result = validate_password_strength(password.data)
        if not result['is_valid']:
            # Usar a primeira mensagem de feedback como erro principal
            error_msg = result['feedback'][0] if result['feedback'] else "Senha não atende aos critérios de segurança."
            raise ValidationError(error_msg)
    
    def validate_phone(self, phone):
        """Valida o formato do telefone brasileiro."""
        if not phone.data:
            return  # Campo opcional
        
        # Remove todos os caracteres não numéricos
        phone_digits = re.sub(r'\D', '', phone.data)
        
        # Validação para telefones brasileiros
        if len(phone_digits) < 10 or len(phone_digits) > 11:
            raise ValidationError('Telefone deve ter 10 ou 11 dígitos (incluindo DDD).')
        
        # Validar DDD (códigos de área válidos no Brasil: 11-99)
        if len(phone_digits) >= 2:
            ddd = int(phone_digits[:2])
            if ddd < 11 or ddd > 99:
                raise ValidationError('DDD inválido. Use um código de área válido (11-99).')
        
        # Para celulares (11 dígitos), o terceiro dígito deve ser 9
        if len(phone_digits) == 11:
            if phone_digits[2] != '9':
                raise ValidationError('Para celulares, o terceiro dígito deve ser 9.')
        
        # Para telefones fixos (10 dígitos), o terceiro dígito deve ser 2-5
        elif len(phone_digits) == 10:
            third_digit = int(phone_digits[2])
            if third_digit < 2 or third_digit > 5:
                raise ValidationError('Para telefones fixos, o terceiro dígito deve ser entre 2 e 5.')
        
        # Validar se não são todos os dígitos iguais
        if len(set(phone_digits)) == 1:
            raise ValidationError('Número de telefone inválido.')


class RootInitForm(FlaskForm):
    username = StringField(
        'Nome de usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
            Regexp(r'^[A-Za-z0-9_]+$', message="Somente letras, números e underscore são permitidos.")
        ],
        render_kw={"placeholder": "Digite o usuário root", "autocomplete": "username"}
    )
    first_name = StringField(
        'Nome',
        validators=[
            DataRequired(message="O nome é obrigatório."),
            Length(2, 50, message="Nome deve ter entre 2 e 50 caracteres."),
            Regexp(r'^[A-Za-zÀ-ÿ\s]+$', message="Nome deve conter apenas letras e espaços.")
        ],
        render_kw={"placeholder": "Digite seu nome", "autocomplete": "given-name"}
    )
    last_name = StringField(
        'Sobrenome',
        validators=[
            DataRequired(message="O sobrenome é obrigatório."),
            Length(2, 50, message="Sobrenome deve ter entre 2 e 50 caracteres."),
            Regexp(r'^[A-Za-zÀ-ÿ\s]+$', message="Sobrenome deve conter apenas letras e espaços.")
        ],
        render_kw={"placeholder": "Digite seu sobrenome", "autocomplete": "family-name"}
    )
    email = StringField(
        'E-mail',
        validators=[
            DataRequired(message="O e-mail é obrigatório."),
            Email(message="Formato de e-mail inválido."),
            Length(max=255, message="E-mail muito longo.")
        ],
        render_kw={"placeholder": "Digite seu e-mail", "autocomplete": "email"}
    )
    phone = StringField(
        'Telefone',
        validators=[Optional()],
        render_kw={"placeholder": "(11) 99999-9999", "autocomplete": "tel"}
    )
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter entre 8 e 128 caracteres.")
        ],
        render_kw={"placeholder": "Defina a senha do usuário root", "autocomplete": "new-password"}
    )
    tacacs_enabled = BooleanField('Habilitar TACACS', default=False)
    tacacs_username = StringField('Usuário TACACS', validators=[Optional()])
    tacacs_secret = StringField('Segredo TACACS', validators=[Optional()])
    tacacs_server = StringField('Servidor TACACS', validators=[Optional()])
    tacacs_port = StringField('Porta TACACS', validators=[Optional()])
    tacacs_timeout = StringField('Timeout TACACS', validators=[Optional()])
    terms_accepted = BooleanField('Aceito os termos de uso e política de privacidade', default=True)
    submit = SubmitField('Criar Usuário Root')
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nome de usuário já está em uso. Escolha outro.')
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Este e-mail já está cadastrado.')

    def validate_phone(self, phone):
        raw = (phone.data or '').strip()
        if not raw:
            return
        digits = ''.join([c for c in raw if c.isdigit()])
        if not digits:
            return
        invalid_patterns = {'1234567890', '0987654321', '1111111111', '0000000000'}
        base = digits[-10:] if len(digits) >= 10 else digits
        if digits in invalid_patterns or base in invalid_patterns:
            raise ValidationError('Número de telefone inválido.')

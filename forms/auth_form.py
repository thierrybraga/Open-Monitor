# forms/auth_form.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, Regexp, ValidationError, Optional
)
from models.user import User
import re

class LoginForm(FlaskForm):
    username = StringField(
        'Usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
        ],
        render_kw={"placeholder": "Digite seu nome de usuário", "autocomplete": "username"}
    )
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter pelo menos 8 caracteres.")
        ],
        render_kw={"placeholder": "Digite sua senha", "autocomplete": "current-password"}
    )
    remember_me = BooleanField('Lembrar-me por 30 dias')
    submit = SubmitField('Entrar')


def validate_password_strength(password):
    """Valida a força da senha com critérios específicos."""
    if len(password) < 8:
        raise ValidationError("A senha deve ter pelo menos 8 caracteres.")
    
    if not re.search(r'[a-z]', password):
        raise ValidationError("A senha deve conter pelo menos uma letra minúscula.")
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError("A senha deve conter pelo menos uma letra maiúscula.")
    
    if not re.search(r'\d', password):
        raise ValidationError("A senha deve conter pelo menos um número.")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError("A senha deve conter pelo menos um caractere especial.")
    
    # Verificar sequências comuns
    common_sequences = ['123456', 'abcdef', 'qwerty', 'password']
    password_lower = password.lower()
    for seq in common_sequences:
        if seq in password_lower:
            raise ValidationError("A senha não pode conter sequências comuns.")


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
            Optional(),
            Length(10, 15, message="Telefone deve ter entre 10 e 15 dígitos."),
            Regexp(
                r'^[\d\s\(\)\+\-]+$',
                message="Formato de telefone inválido."
            )
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
        """Valida a força da senha."""
        validate_password_strength(password.data)

# forms/auth_form.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, Regexp
)

class LoginForm(FlaskForm):
    username = StringField(
        'Usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
        ]
    )
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter pelo menos 8 caracteres.")
        ]
    )
    remember_me = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')


class RegisterForm(FlaskForm):
    username = StringField(
        'Usuário',
        validators=[
            DataRequired(message="O nome de usuário é obrigatório."),
            Length(3, 50, message="Usuário deve ter entre 3 e 50 caracteres."),
            Regexp(
                r'^[A-Za-z0-9_]+$',
                message="Somente letras, números e underscore são permitidos."
            )
        ]
    )
    email = StringField(
        'E-mail',
        validators=[
            DataRequired(message="O e-mail é obrigatório."),
            Email(message="Formato de e-mail inválido."),
            Length(max=255, message="E-mail muito longo.")
        ]
    )
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória."),
            Length(8, 128, message="A senha deve ter pelo menos 8 caracteres.")
        ]
    )
    confirm_password = PasswordField(
        'Confirme a senha',
        validators=[
            DataRequired(message="Precisa confirmar a senha."),
            EqualTo('password', message="As senhas devem coincidir.")
        ]
    )
    submit = SubmitField('Registrar')

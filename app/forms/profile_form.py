# forms/profile_form.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired, Length, Email, Optional, EqualTo, Regexp, ValidationError
)
from wtforms.widgets import TextArea
import re


class ProfileForm(FlaskForm):
    """Formulário para edição de perfil do usuário."""
    
    # Campos básicos do perfil
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
        render_kw={
            'placeholder': 'Digite seu nome',
            'class': 'form-control'
        }
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
        render_kw={
            'placeholder': 'Digite seu sobrenome',
            'class': 'form-control'
        }
    )
    
    email = StringField(
        'E-mail',
        validators=[
            DataRequired(message="O e-mail é obrigatório."),
            Email(message="Formato de e-mail inválido."),
            Length(max=255, message="E-mail muito longo.")
        ],
        render_kw={
            'placeholder': 'exemplo@dominio.com',
            'class': 'form-control',
            'autocomplete': 'email'
        }
    )
    
    phone = StringField(
        'Telefone',
        validators=[
            Optional()
        ],
        render_kw={
            'placeholder': '(11) 99999-9999',
            'class': 'form-control'
        }
    )
    
    address = TextAreaField(
        'Endereço',
        validators=[
            Optional(),
            Length(max=500, message="Endereço muito longo.")
        ],
        widget=TextArea(),
        render_kw={
            'placeholder': 'Digite seu endereço completo',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    bio = TextAreaField(
        'Biografia',
        validators=[
            Optional(),
            Length(max=1000, message="Biografia muito longa.")
        ],
        widget=TextArea(),
        render_kw={
            'placeholder': 'Conte um pouco sobre você...',
            'class': 'form-control',
            'rows': 4
        }
    )
    
    # Campo para upload de foto de perfil
    profile_picture = FileField(
        'Foto de Perfil',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Apenas imagens são permitidas!')
        ]
    )
    
    submit = SubmitField(
        'Salvar Alterações',
        render_kw={'class': 'btn btn-primary'}
    )
    
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
        
        # Validar padrões conhecidos inválidos
        invalid_patterns = ['1234567890', '0987654321', '1111111111', '0000000000']
        if phone_digits in invalid_patterns or phone_digits[-10:] in invalid_patterns:
            raise ValidationError('Número de telefone inválido.')


class ChangePasswordForm(FlaskForm):
    """Formulário para alteração de senha."""
    
    current_password = PasswordField(
        'Senha Atual',
        validators=[
            DataRequired(message="A senha atual é obrigatória.")
        ],
        render_kw={
            'placeholder': 'Digite sua senha atual',
            'class': 'form-control'
        }
    )
    
    new_password = PasswordField(
        'Nova Senha',
        validators=[
            DataRequired(message="A nova senha é obrigatória."),
            Length(8, 128, message="A senha deve ter pelo menos 8 caracteres."),
            Regexp(
                r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
                message="A senha deve conter pelo menos: 1 letra minúscula, 1 maiúscula, 1 número e 1 caractere especial."
            )
        ],
        render_kw={
            'placeholder': 'Digite sua nova senha',
            'class': 'form-control'
        }
    )
    
    confirm_password = PasswordField(
        'Confirmar Nova Senha',
        validators=[
            DataRequired(message="Precisa confirmar a nova senha."),
            EqualTo('new_password', message="As senhas devem coincidir.")
        ],
        render_kw={
            'placeholder': 'Confirme sua nova senha',
            'class': 'form-control'
        }
    )
    
    submit = SubmitField(
        'Alterar Senha',
        render_kw={'class': 'btn btn-primary'}
    )


class DeleteAccountForm(FlaskForm):
    """Formulário para exclusão de conta."""
    
    password = PasswordField(
        'Senha',
        validators=[
            DataRequired(message="A senha é obrigatória para excluir a conta.")
        ],
        render_kw={
            'placeholder': 'Digite sua senha para confirmar',
            'class': 'form-control'
        }
    )
    
    confirmation = StringField(
        'Confirmação',
        validators=[
            DataRequired(message="Digite 'EXCLUIR' para confirmar."),
            EqualTo('confirmation', message="Digite exatamente 'EXCLUIR' para confirmar.")
        ],
        render_kw={
            'placeholder': 'Digite EXCLUIR para confirmar',
            'class': 'form-control'
        }
    )
    
    submit = SubmitField(
        'Excluir Conta',
        render_kw={'class': 'btn btn-danger'}
    )

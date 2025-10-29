# forms/asset_form.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from wtforms.fields import SelectField
import ipaddress

class AssetForm(FlaskForm):
    """
    Formulário para criar/editar um Asset.
    - name: nome amigável do ativo
    - ip_address: endereço IPv4 do ativo
    - status: situação do ativo
    - owner_id: proprietário responsável
    """

    name = StringField(
        'Nome',
        validators=[
            DataRequired(message="O nome é obrigatório."),
            Length(max=100, message="Máximo 100 caracteres.")
        ]
    )

    ip_address = StringField(
        'Endereço IP',
        validators=[
            DataRequired(message="O endereço IP é obrigatório.")
        ]
    )

    status = SelectField(
        'Status',
        validators=[DataRequired(message="Selecione o status do ativo.")],
        choices=[
            ('active', 'Ativo'),
            ('maintenance', 'Em manutenção'),
            ('inactive', 'Inativo')
        ],
        default='active'
    )

    owner_id = SelectField(
        'Proprietário',
        validators=[Optional()],
        coerce=int,
        choices=[],
        render_kw={'class': 'form-select'}
    )

    vendor_name = StringField(
        'Fornecedor',
        validators=[Optional(), Length(max=255, message="Máximo 255 caracteres.")]
    )

    vendor_id = HiddenField(
        'Fornecedor ID',
        validators=[Optional()]
    )

    submit = SubmitField('Salvar')

    def validate_ip_address(self, field):
        """Validação robusta de IPv4 usando o módulo ipaddress."""
        try:
            ip_obj = ipaddress.ip_address(field.data)
            if ip_obj.version != 4:
                raise ValidationError("Informe um IPv4 válido.")
        except ValueError:
            raise ValidationError("Informe um IPv4 válido (ex: 192.168.0.1).")

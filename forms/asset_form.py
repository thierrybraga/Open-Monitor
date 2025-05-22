# forms/asset_form.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp

class AssetForm(FlaskForm):
    """
    Formulário para criar/editar um Asset.
    - name: nome amigável do ativo
    - ip_address: endereço IPv4 do ativo
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
            DataRequired(message="O endereço IP é obrigatório."),
            Regexp(
                r'^(\d{1,3}\.){3}\d{1,3}$',
                message="Informe um IPv4 válido (ex: 192.168.0.1)."
            )
        ]
    )

    submit = SubmitField('Salvar')

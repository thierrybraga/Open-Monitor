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
        ],
        filters=[lambda x: x.strip() if isinstance(x, str) else x]
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

    asset_type = StringField(
        'Tipo do Ativo',
        validators=[Optional(), Length(max=100, message="Máximo 100 caracteres.")],
        description="Categoria do ativo (ex.: Servidor, Switch, Firewall)"
    )

    owner_id = SelectField(
        'Proprietário',
        validators=[Optional()],
        coerce=int,
        choices=[],
        render_kw={'class': 'form-select'}
    )

    vendor_name = SelectField(
        'Fornecedor',
        validators=[Optional()],
        choices=[
            ('fortinet', 'Fortinet'),
            ('cisco', 'Cisco')
        ],
        render_kw={'class': 'form-select'}
    )

    vendor_id = HiddenField(
        'Fornecedor ID',
        validators=[Optional()]
    )

    # Produto vinculado ao fornecedor selecionado
    product_name = StringField(
        'Produto',
        validators=[Optional(), Length(max=255, message="Máximo 255 caracteres.")]
    )
    product_id = HiddenField(
        'Produto ID',
        validators=[Optional()]
    )

    # Metadados para correlação de CVE
    model_name = StringField(
        'Modelo',
        validators=[Optional(), Length(max=255, message="Máximo 255 caracteres.")]
    )
    operating_system = StringField(
        'Sistema Operacional',
        validators=[Optional(), Length(max=255, message="Máximo 255 caracteres.")]
    )
    installed_version = StringField(
        'Versão Instalada',
        validators=[Optional(), Length(max=100, message="Máximo 100 caracteres.")]
    )

    submit = SubmitField('Salvar')

    def validate_ip_address(self, field):
        """Validação robusta de IPv4/IPv6 com sanitização."""
        value = (field.data or '').strip()
        try:
            ip_obj = ipaddress.ip_address(value)
            # Aceitar IPv4 e IPv6 e normalizar representação
            if ip_obj.version not in (4, 6):
                raise ValidationError("Informe um IP válido.")
            # Normaliza o valor para a forma canônica (remove zeros à esquerda/compressão adequada)
            field.data = str(ip_obj)
        except ValueError:
            raise ValidationError("Informe um IP válido (IPv4 ou IPv6).")

# forms/api_form.py

"""
Formulário para validar parâmetros de query em endpoints de API
(cves, vulnerabilities, assets) usando Flask-WTF para CSRF e validação de tipos.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, SubmitField
from wtforms.validators import Optional, NumberRange

from ..models.enums import severity_levels

class APIQueryForm(FlaskForm):
    """
    Valida parâmetros de paginação e filtros comuns para API endpoints:
      - page: número da página (>= 1)
      - per_page: itens por página (entre 1 e 100)
      - severity: nível de severidade (LOW, MEDIUM, HIGH, CRITICAL)
      - vendor: nome do fornecedor (string)
    """
    page = IntegerField(
        label='Página',
        default=1,
        validators=[
            Optional(),
            NumberRange(min=1, message="Página deve ser maior ou igual a 1")
        ]
    )
    per_page = IntegerField(
        label='Itens por página',
        default=20,
        validators=[
            Optional(),
            NumberRange(min=1, max=100, message="Itens por página deve ser entre 1 e 100")
        ]
    )
    severity = SelectField(
        label='Severidade',
        choices=[('', 'Todas')] + [(level, level) for level in severity_levels.enums],
        validators=[Optional()]
    )
    vendor = StringField(
        label='Fornecedor',
        validators=[Optional()]
    )
    submit = SubmitField('Aplicar')

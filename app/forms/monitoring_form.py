# forms/monitoring_form.py

import json
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

class MonitoringRuleForm(FlaskForm):
    """
    Formulário para criar/editar uma regra de monitoramento.
    Campos:
      - name: nome descritivo da regra
      - parameters: configuração da regra em JSON
    """
    name = StringField(
        'Nome da Regra',
        validators=[
            DataRequired(message="O nome da regra é obrigatório."),
            Length(max=100, message="Máximo 100 caracteres.")
        ]
    )
    parameters = TextAreaField(
        'Parâmetros (JSON)',
        validators=[DataRequired(message="Parâmetros são obrigatórios.")]
    )
    submit = SubmitField('Salvar')

    def validate_parameters(self, field):
        """Valida que o conteúdo de parameters seja um JSON válido."""
        try:
            json.loads(field.data or '')
        except ValueError:
            raise ValidationError('Parâmetros devem ser um JSON válido.')

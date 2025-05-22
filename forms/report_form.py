# forms/report_form.py

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField
from wtforms.validators import Optional, ValidationError
from ..models.enums import severity_levels

class ReportFilterForm(FlaskForm):
    """
    Formulário para filtrar e gerar relatórios.
    Campos:
      - start_date: data inicial do período
      - end_date:   data final do período
      - severity:   nível de severidade (LOW, MEDIUM, HIGH, CRITICAL)
      - vendor:     nome do fornecedor para filtrar
    """

    start_date = DateField(
        'Data Inicial',
        format='%Y-%m-%d',
        validators=[Optional()],
        render_kw={"placeholder": "YYYY-MM-DD"}
    )
    end_date = DateField(
        'Data Final',
        format='%Y-%m-%d',
        validators=[Optional()],
        render_kw={"placeholder": "YYYY-MM-DD"}
    )
    severity = SelectField(
        'Severidade',
        choices=[('', 'Todas')] + [(lvl, lvl) for lvl in severity_levels.enums],
        validators=[Optional()]
    )
    vendor = StringField(
        'Fornecedor',
        validators=[Optional()],
        render_kw={"placeholder": "ex: Microsoft"}
    )
    submit = SubmitField('Gerar Relatório')

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError('Data Final deve ser igual ou posterior à Data Inicial.')

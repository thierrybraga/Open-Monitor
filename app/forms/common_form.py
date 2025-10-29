from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, DateField
from wtforms.validators import Optional, NumberRange, DataRequired, Email

class SearchForm(FlaskForm):
    q = StringField('Buscar', validators=[Optional()])
    submit = SubmitField('Buscar')

class NewsletterForm(FlaskForm):
    email = StringField('E‑mail', validators=[DataRequired(message='Informe um e‑mail'), Email(message='E‑mail inválido')])
    submit = SubmitField('Inscrever')

class PaginationForm(FlaskForm):
    page = IntegerField('Página', default=1, validators=[NumberRange(min=1, message='A página deve ser ≥ 1')])
    per_page = IntegerField('Por página', default=20, validators=[NumberRange(min=1, max=100, message='Itens por página entre 1 e 100')])
    submit = SubmitField('Ir')

class FilterForm(FlaskForm):
    severity = SelectField(
        'Severidade',
        choices=[('', 'Todas'), ('LOW', 'Baixa'), ('MEDIUM', 'Média'), ('HIGH', 'Alta'), ('CRITICAL', 'Crítica')],
        validators=[Optional()]
    )
    vendor = StringField('Vendor', validators=[Optional()])
    start_date = DateField('Data Início', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('Data Fim', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Filtrar')

class DeleteForm(FlaskForm):
    """Formulário simples para confirmação de exclusão."""
    submit = SubmitField('Excluir')
    # Exemplo de campo oculto para passar o ID do item a ser excluído:
    # item_id = HiddenField(validators=[DataRequired()])

from marshmallow import Schema, fields, validate


class MonitoringRuleSchema(Schema):
    """
    Schema para serialização e validação de regras de monitoramento.
    """
    id = fields.Int(dump_only=True)
    user_id = fields.Int(
        required=True,
        validate=validate.Range(min=1, error="ID de usuário inválido.")
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255, error="O nome deve ter entre 1 e 255 caracteres.")
    )
    filter_params = fields.Dict(
        required=True,
        error_messages={"required": "Os parâmetros de filtro são obrigatórios."}
    )
    is_active = fields.Bool(
        required=True,
        error_messages={"required": "O status ativo é obrigatório."}
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

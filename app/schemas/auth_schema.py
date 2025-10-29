from marshmallow import Schema, fields, validate


class AuthRegisterSchema(Schema):
    """
    Schema para validação de dados de registro de usuário.
    """
    email = fields.Email(
        required=True,
        validate=validate.Length(max=255),
        error_messages={"required": "O campo de e-mail é obrigatório."}
    )
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, error="A senha deve ter pelo menos 8 caracteres."),
        error_messages={"required": "O campo de senha é obrigatório."}
    )
    confirm_password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8),
        error_messages={"required": "Confirmação de senha é obrigatória."}
    )

    def validate(self, data, **kwargs):
        if data.get('password') != data.get('confirm_password'):
            raise validate.ValidationError({
                'confirm_password': ['As senhas não coincidem.']
            })
        return data


class AuthLoginSchema(Schema):
    """
    Schema para validação de dados de login de usuário.
    """
    email = fields.Email(
        required=True,
        error_messages={"required": "O campo de e-mail é obrigatório."}
    )
    password = fields.Str(
        required=True,
        load_only=True,
        error_messages={"required": "O campo de senha é obrigatório."}
    )


class AuthResponseSchema(Schema):
    """
    Schema para resposta após autenticação bem-sucedida.
    """
    id = fields.Int(dump_only=True)
    email = fields.Email(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

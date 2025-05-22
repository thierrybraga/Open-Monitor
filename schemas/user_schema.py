from marshmallow import Schema, fields, validate, ValidationError, validates

class UserSchema(Schema):
    """
    Schema para serialização de dados de usuário.
    """
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    is_active = fields.Boolean()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class UserCreateSchema(Schema):
    """
    Schema para validação de criação de usuário.
    """
    email = fields.Email(
        required=True,
        validate=validate.Length(max=255)
    )
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, error="A senha deve ter pelo menos 8 caracteres.")
    )

    @staticmethod
    def validate_password(password):
        if not any(char.isdigit() for char in password) or not any(char.isalpha() for char in password):
            raise ValidationError("A senha deve conter letras e números.")

    @validates('password')
    def _check_password(self, value):
        self.validate_password(value)

class UserLoginSchema(Schema):
    """
    Schema para validação de login de usuário.
    """
    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        load_only=True
    )

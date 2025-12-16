from marshmallow import Schema, fields


class SyncMetadataSchema(Schema):
    """
    Schema para serialização de metadados de sincronização (SyncMetadata).
    """
    key = fields.Str(dump_only=True)
    value = fields.Str()


class ApiCallLogSchema(Schema):
    """
    Schema para serialização de logs de chamadas à API (ApiCallLog).
    """
    id = fields.Int(dump_only=True)
    endpoint = fields.Str(required=True)
    status_code = fields.Int(required=True)
    response_time = fields.Float(required=True)
    timestamp = fields.DateTime(dump_only=True)
    # Campos de relacionamento com SyncMetadata não existem no modelo atual

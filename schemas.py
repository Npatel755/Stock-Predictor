from marshmallow import Schema, fields
class TickerSchema(Schema):
    ticker = fields.Str(required = True)
    latest_date = fields.Str(dump_only=True)
    prediction = fields.Str(dump_only = True)
    prediction_value = fields.Int(dump_only = True)
    probability_up = fields.Float(dump_only = True)

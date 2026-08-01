from database import db

class StockModel(db.Model):
    __tablename__ = 'stock_data'

    id = db.Column(db.Integer, primary_key=True)
    Volume = db.Column(db.Float, nullable=False)
    VWAP = db.Column(db.Float, nullable=False)
    Open = db.Column(db.Float, nullable=False)
    Close = db.Column(db.Float, nullable=False)
    High = db.Column(db.Float, nullable=False)
    Low = db.Column(db.Float, nullable=False)
    Timestamp = db.Column(db.DateTime, nullable=False)
    Trades = db.Column(db.Integer, nullable=False)
    SMA20 = db.Column(db.Float, nullable=False)
    SMA50 = db.Column(db.Float, nullable=False)
    EMA12 = db.Column(db.Float, nullable=False)
    EMA26 = db.Column(db.Float, nullable=False)
    RSI = db.Column(db.Float, nullable=False)
    MACD = db.Column(db.Float, nullable=False)
    Signal = db.Column(db.Float, nullable=False)
    Histogram = db.Column(db.Float, nullable=False)
    Daily_Return = db.Column(db.Float, nullable=False)
    High_Low_Percent = db.Column(db.Float, nullable=False)
    Open_Close_Percent = db.Column(db.Float, nullable=False)
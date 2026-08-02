from database import db


class StockModel(db.Model):
    __tablename__ = "stock_data"

    __table_args__ = (
        db.UniqueConstraint(
            "ticker",
            "Timestamp",
            name="uq_stock_ticker_timestamp"
        ),
    )

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Original market data
    Volume = db.Column(db.Float, nullable=False)
    VWAP = db.Column(db.Float, nullable=False)
    Open = db.Column(db.Float, nullable=False)
    Close = db.Column(db.Float, nullable=False)
    High = db.Column(db.Float, nullable=False)
    Low = db.Column(db.Float, nullable=False)
    Timestamp = db.Column(db.DateTime, nullable=False)
    Trades = db.Column(db.Integer, nullable=False)

    # Time features
    DayOfWeek = db.Column(db.Integer, nullable=False)
    Month = db.Column(db.Integer, nullable=False)
    Quarter = db.Column(db.Integer, nullable=False)

    # Simple moving averages
    SMA20 = db.Column(db.Float, nullable=False)
    SMA50 = db.Column(db.Float, nullable=False)
    SMA100 = db.Column(db.Float, nullable=False)

    # Exponential moving averages
    EMA12 = db.Column(db.Float, nullable=False)
    EMA26 = db.Column(db.Float, nullable=False)
    EMA50 = db.Column(db.Float, nullable=False)
    EMA100 = db.Column(db.Float, nullable=False)

    # Volume features
    VolumeSMA20 = db.Column(db.Float, nullable=False)
    VolumeRatio = db.Column(db.Float, nullable=False)

    # RSI
    RSI = db.Column(db.Float, nullable=False)

    # MACD
    MACD = db.Column(db.Float, nullable=False)
    Signal = db.Column(db.Float, nullable=False)
    Histogram = db.Column(db.Float, nullable=False)

    # Returns
    Daily_Return = db.Column(db.Float, nullable=False)
    Return5 = db.Column(db.Float, nullable=False)
    Return10 = db.Column(db.Float, nullable=False)
    Return20 = db.Column(db.Float, nullable=False)

    # Daily price relationships
    High_Low_Percent = db.Column(db.Float, nullable=False)
    Open_Close_Percent = db.Column(db.Float, nullable=False)
    GapPct = db.Column(db.Float, nullable=False)

    # Bollinger Bands
    BBMiddle = db.Column(db.Float, nullable=False)
    BBStd = db.Column(db.Float, nullable=False)
    BBUpper = db.Column(db.Float, nullable=False)
    BBLower = db.Column(db.Float, nullable=False)
    BBWidth = db.Column(db.Float, nullable=False)
    BBPercentB = db.Column(db.Float, nullable=False)

    # Average True Range
    TrueRange = db.Column(db.Float, nullable=False)
    ATR14 = db.Column(db.Float, nullable=False)
    ATRPct = db.Column(db.Float, nullable=False)

    # On-Balance Volume
    OBV = db.Column(db.Float, nullable=False)
    OBVChange = db.Column(db.Float, nullable=False)

    # Stochastic Oscillator
    StochasticK = db.Column(db.Float, nullable=False)
    StochasticD = db.Column(db.Float, nullable=False)

    # Other momentum indicators
    WilliamsR = db.Column(db.Float, nullable=False)
    ROC10 = db.Column(db.Float, nullable=False)
    Momentum10 = db.Column(db.Float, nullable=False)

    # Lagged close features
    CloseLag1 = db.Column(db.Float, nullable=False)
    CloseLag2 = db.Column(db.Float, nullable=False)
    CloseLag5 = db.Column(db.Float, nullable=False)

    # Lagged return features
    ReturnLag1 = db.Column(db.Float, nullable=False)
    ReturnLag2 = db.Column(db.Float, nullable=False)
    ReturnLag5 = db.Column(db.Float, nullable=False)

    # Lagged indicator features
    RSILag1 = db.Column(db.Float, nullable=False)
    MACDLag1 = db.Column(db.Float, nullable=False)
    VolumeLag1 = db.Column(db.Float, nullable=False)

    # Rolling averages
    RollingMean5 = db.Column(db.Float, nullable=False)
    RollingMean10 = db.Column(db.Float, nullable=False)
    RollingMean20 = db.Column(db.Float, nullable=False)

    # Rolling volatility
    Volatility5 = db.Column(db.Float, nullable=False)
    Volatility10 = db.Column(db.Float, nullable=False)
    Volatility20 = db.Column(db.Float, nullable=False)

    # Rolling highs and lows
    RollingHigh20 = db.Column(db.Float, nullable=False)
    RollingLow20 = db.Column(db.Float, nullable=False)

    # Distance from recent high and low
    DistanceFromHigh20 = db.Column(db.Float, nullable=False)
    DistanceFromLow20 = db.Column(db.Float, nullable=False)

    # Relative price features
    CloseToSMA20 = db.Column(db.Float, nullable=False)
    CloseToSMA50 = db.Column(db.Float, nullable=False)

    SMA20ToSMA50 = db.Column(db.Float, nullable=False)
    EMA12ToEMA26 = db.Column(db.Float, nullable=False)

    DistanceFromSMA20 = db.Column(db.Float, nullable=False)
    DistanceFromSMA50 = db.Column(db.Float, nullable=False)

    # Stock symbol
    ticker = db.Column(db.String(80), nullable=False)
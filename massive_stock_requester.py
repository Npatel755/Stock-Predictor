import requests
import pandas as pd
import numpy as np
import datetime
from dotenv import load_dotenv
import os
from datetime import datetime
from database import db
from models.stockmodel import StockModel
from sqlalchemy.dialects.postgresql import insert
def grab_data(ticker):
    today = datetime.today()
    today = today.date()
    #Grab data from massive using api key
    load_dotenv()
    MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
    url = (f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2000-01-01/{today}')
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 5000,
        "apiKey": MASSIVE_API_KEY
    }
    response = requests.get(url,params=params)
    data = response.json()

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        print(f"{ticker} returned invalid JSON")
        return

    if response.status_code != 200:
        print(f"{ticker} failed: {response.status_code}")
        print(data)
        return

    if "results" not in data:
        print(f"{ticker} missing results:")
        print(data)
        return

    if len(data["results"]) == 0:
        print(f"{ticker} has no price data")
        return

    #turn the results into a dataframe
    stock_dataframe = pd.DataFrame(data['results'])
    stock_dataframe = stock_dataframe.rename(columns={
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
        "v": "Volume",
        "vw": "VWAP",
        "t": "Timestamp",
        "n": "Trades"
    })

    #feature engineer more columns for the ml model to use

    # adds a timestamp
    stock_dataframe['Timestamp'] = pd.to_datetime(stock_dataframe['Timestamp'], unit='ms')

    #Sort by date
    stock_dataframe = stock_dataframe.sort_values("Timestamp").reset_index(drop=True)

    #Add time features
    stock_dataframe["Timestamp"] = pd.to_datetime(stock_dataframe["Timestamp"])

    stock_dataframe["DayOfWeek"] = stock_dataframe["Timestamp"].dt.dayofweek
    stock_dataframe["Month"] = stock_dataframe["Timestamp"].dt.month
    stock_dataframe["Quarter"] = stock_dataframe["Timestamp"].dt.quarter

    #adds various moving averages
    stock_dataframe["SMA20"] = stock_dataframe["Close"].rolling(20).mean()
    stock_dataframe["SMA50"] = stock_dataframe["Close"].rolling(50).mean()
    stock_dataframe['SMA100'] = stock_dataframe["Close"].rolling(100).mean()

    stock_dataframe["EMA12"] = stock_dataframe["Close"].ewm(span=12, adjust=False).mean()
    stock_dataframe["EMA26"] = stock_dataframe["Close"].ewm(span=26, adjust=False).mean()
    stock_dataframe["EMA50"] = stock_dataframe["Close"].ewm(span=50, adjust=False).mean()
    stock_dataframe["EMA100"] = stock_dataframe["Close"].ewm(span=100, adjust=False).mean()

    #Add volume moving averages and ratios
    stock_dataframe['VolumeSMA20'] = stock_dataframe["Volume"].rolling(20).mean()
    stock_dataframe['VolumeRatio'] = (
        stock_dataframe['Volume']/stock_dataframe['VolumeSMA20']
    )

    #Add rsi
    ema12 = stock_dataframe["Close"].ewm(span=12, adjust=False).mean()
    ema26 = stock_dataframe["Close"].ewm(span=26, adjust=False).mean()

    delta = stock_dataframe["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    stock_dataframe["RSI"] = 100 - (100 / (1 + rs))

    #Add MACD, Signal, Histogram
    stock_dataframe['MACD'] = ema12 - ema26
    stock_dataframe['Signal'] = stock_dataframe['MACD'].ewm(span=9,adjust=False).mean()
    stock_dataframe['Histogram'] = stock_dataframe['MACD'] - stock_dataframe['Signal']

    #Add daily return
    stock_dataframe["Daily_Return"] = stock_dataframe['Close'].pct_change()
    stock_dataframe["Return5"] = stock_dataframe['Close'].pct_change(5)
    stock_dataframe["Return10"] = stock_dataframe['Close'].pct_change(10)
    stock_dataframe["Return20"] = stock_dataframe['Close'].pct_change(20)

    #Add high-low%
    stock_dataframe['High_Low_Percent'] = (
        (stock_dataframe["High"] - stock_dataframe["Low"])/ stock_dataframe['Low']
    )

    #Add open-close %
    stock_dataframe['Open_Close_Percent'] = (
        (stock_dataframe["Close"] - stock_dataframe["Open"])/ stock_dataframe['Open']
    )

    #Add gap percentage
    stock_dataframe['GapPct'] = (
        (stock_dataframe['Open'] - stock_dataframe['Close'].shift(1))/stock_dataframe['Close'].shift(1)
    )

    #Add Bollinger Bands
    stock_dataframe["BBMiddle"] = stock_dataframe["Close"].rolling(20).mean()
    stock_dataframe["BBStd"] = stock_dataframe["Close"].rolling(20).std()
    stock_dataframe["BBUpper"] = (
        stock_dataframe["BBMiddle"] +
        2 * stock_dataframe["BBStd"]
    )
    stock_dataframe["BBLower"] = (
        stock_dataframe["BBMiddle"] -
        2 * stock_dataframe["BBStd"]
    )
    stock_dataframe['BBWidth'] = (
        (stock_dataframe['BBUpper'] - stock_dataframe['BBLower']) / stock_dataframe['BBMiddle']
    )
    stock_dataframe['BBPercentB'] = (
        (stock_dataframe['Close'] - stock_dataframe['BBLower']) / (stock_dataframe['BBUpper'] - stock_dataframe["BBLower"])
    )

    #Add average True Range
    previous_close = stock_dataframe['Close'].shift(1)
    true_range = pd.concat(
        [
            stock_dataframe['High'] - stock_dataframe['Low'],
            (stock_dataframe['High'] - previous_close).abs(),
            (stock_dataframe['Low']- previous_close).abs()
        ],
        axis=1
    ).max(axis=1)
    stock_dataframe["TrueRange"] = true_range
    stock_dataframe['ATR14'] = true_range.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    #Normalized True range
    stock_dataframe['ATRPct'] = stock_dataframe['ATR14']/stock_dataframe['Close']

    #Add OBV
    previous_direction = np.sign(stock_dataframe['Close'].diff())
    stock_dataframe['OBV'] = (
        previous_direction.fillna(0).mul(stock_dataframe['Volume']).cumsum()
    )
    stock_dataframe['OBVChange'] = stock_dataframe['OBV'].pct_change()

    #Add Stochastic Oscilattor
    lowest_low_14 = stock_dataframe["Low"].rolling(14).min()
    highest_high_14 = stock_dataframe['High'].rolling(14).max()
    stock_dataframe['StochasticK'] = (
        (100 * (stock_dataframe['Close'] - lowest_low_14)) / (highest_high_14 - lowest_low_14)
    )
    stock_dataframe["StochasticD"] = stock_dataframe['StochasticK'].rolling(3).mean()

    #Add Williams %R
    stock_dataframe['WilliamsR'] = (
        (-100 * (highest_high_14 - stock_dataframe['Close']) / (highest_high_14 - lowest_low_14))
    )

    #Add Rate of Change
    stock_dataframe["ROC10"] = (
        (100 * (stock_dataframe["Close"] - stock_dataframe["Close"].shift(10))) / stock_dataframe['Close'].shift(10)
    )

    #Add Momentum
    stock_dataframe["Momentum10"] = stock_dataframe['Close'] - stock_dataframe['Close'].shift(10)

    #Add lagged features
    stock_dataframe["CloseLag1"] = stock_dataframe["Close"].shift(1)
    stock_dataframe["CloseLag2"] = stock_dataframe["Close"].shift(2)
    stock_dataframe["CloseLag5"] = stock_dataframe["Close"].shift(5)

    stock_dataframe["ReturnLag1"] = stock_dataframe["Daily_Return"].shift(1)
    stock_dataframe["ReturnLag2"] = stock_dataframe["Daily_Return"].shift(2)
    stock_dataframe["ReturnLag5"] = stock_dataframe["Daily_Return"].shift(5)

    stock_dataframe["RSILag1"] = stock_dataframe["RSI"].shift(1)
    stock_dataframe["MACDLag1"] = stock_dataframe["MACD"].shift(1)
    stock_dataframe["VolumeLag1"] = stock_dataframe["Volume"].shift(1)

    #Rolling statistics
    stock_dataframe["RollingMean5"] = stock_dataframe["Close"].rolling(5).mean()
    stock_dataframe["RollingMean10"] = stock_dataframe["Close"].rolling(10).mean()
    stock_dataframe["RollingMean20"] = stock_dataframe["Close"].rolling(20).mean()

    stock_dataframe["Volatility5"] = stock_dataframe["Daily_Return"].rolling(5).std()
    stock_dataframe["Volatility10"] = stock_dataframe["Daily_Return"].rolling(10).std()
    stock_dataframe["Volatility20"] = stock_dataframe["Daily_Return"].rolling(20).std()

    stock_dataframe["RollingHigh20"] = (
        stock_dataframe["High"].rolling(20).max()
    )
    stock_dataframe["RollingLow20"] = (
        stock_dataframe["Low"].rolling(20).min()
    )
    stock_dataframe["DistanceFromHigh20"] = (
        stock_dataframe["Close"] / stock_dataframe["RollingHigh20"] - 1
    )

    stock_dataframe["DistanceFromLow20"] = (
        stock_dataframe["Close"] / stock_dataframe["RollingLow20"] - 1
    )

    #Add Relative price features
    stock_dataframe["CloseToSMA20"] = stock_dataframe["Close"] / stock_dataframe["SMA20"]
    stock_dataframe["CloseToSMA50"] = stock_dataframe["Close"] / stock_dataframe["SMA50"]


    stock_dataframe["SMA20ToSMA50"] = stock_dataframe["SMA20"] / stock_dataframe["SMA50"]
    stock_dataframe["EMA12ToEMA26"] = stock_dataframe["EMA12"] / stock_dataframe["EMA26"]

    stock_dataframe["DistanceFromSMA20"] = (
        stock_dataframe["Close"] - stock_dataframe["SMA20"]
    ) / stock_dataframe["SMA20"]

    stock_dataframe["DistanceFromSMA50"] = (
        stock_dataframe["Close"] - stock_dataframe["SMA50"]
    ) / stock_dataframe["SMA50"]

    #Add ticker name
    stock_dataframe['ticker'] = ticker

    #Delete first 100 something values with null values
    stock_dataframe = stock_dataframe.replace([np.inf, -np.inf], np.nan)
    stock_dataframe.dropna(axis=0,inplace=True)
    stock_dataframe.reset_index(drop=True,inplace=True)

    #Add all information to the database
    print(stock_dataframe.columns.tolist())
    records = stock_dataframe.to_dict(orient="records")

    stmt = insert(StockModel).values(records)

    stmt = stmt.on_conflict_do_nothing(
        index_elements=["ticker", "Timestamp"]
    )

    result = db.session.execute(stmt)
    db.session.commit()
    print("Rows ready:", len(records))
    print("Rows inserted:", result.rowcount)
    print("Duplicates skipped:", len(records) - result.rowcount)

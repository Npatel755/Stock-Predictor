import requests
import pandas as pd
from dotenv import load_dotenv
import os
import datetime
from database import db
from models.stockmodel import StockModel
from app import app
from sqlalchemy.dialects.postgresql import insert

#Grab data from massive using api key
load_dotenv()
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
ticker = 'NVDA'
url = (f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2024-01-01/2024-12-31')
params = {
    "adjusted": "true",
    "sort": "asc",
    "limit": 5000,
    "apiKey": MASSIVE_API_KEY
}
response = requests.get(url,params=params)
data = response.json()

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

#adds various moving averages
stock_dataframe["SMA20"] = stock_dataframe["Close"].rolling(20).mean()
stock_dataframe["SMA50"] = stock_dataframe["Close"].rolling(50).mean()


stock_dataframe["EMA12"] = stock_dataframe["Close"].ewm(span=12, adjust=False).mean()
stock_dataframe["EMA26"] = stock_dataframe["Close"].ewm(span=26, adjust=False).mean()

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

#Add high-low%
stock_dataframe['High_Low_Percent'] = (
    (stock_dataframe["High"] - stock_dataframe["Low"])/ stock_dataframe['Low']
)

#Add open-close %
stock_dataframe['Open_Close_Percent'] = (
    (stock_dataframe["Close"] - stock_dataframe["Open"])/ stock_dataframe['Open']
)

#Add ticker name
stock_dataframe['ticker'] = ticker

#Delete first 40 something values with null values
stock_dataframe.dropna(axis=0,inplace=True)

#Add all information to the database
with app.app_context():

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

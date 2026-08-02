import numpy as np
import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import joblib
from massive_stock_requester import grab_data

tickers = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "BRK.B",
    "JPM", "V", "MA", "LLY", "XOM", "UNH", "COST", "WMT", "JNJ", "PG",
    "HD", "ABBV", "BAC", "KO", "PEP", "CRM", "ORCL", "AMD", "NFLX", "CVX",
    "MRK", "CSCO", "ADBE", "TMO", "MCD", "ACN", "ABT", "LIN", "WFC", "DHR",
    "IBM", "DIS", "INTU", "TXN", "QCOM", "AMGN", "CAT", "RTX", "GE", "NOW",
    "ISRG", "BKNG", "SPGI", "PGR", "LOW", "HON", "UNP", "GS", "BLK", "AXP",
    "PLTR", "UBER", "SHOP", "PANW", "CRWD", "SNOW", "MSTR", "COIN", "ARM", "SMCI",
    "MU", "ANET", "KLAC", "LRCX", "ADI", "MAR", "ADP", "VRTX", "GILD", "DE",
    "CMCSA", "INTC", "PYPL", "SBUX", "BA", "NKE", "MDT", "CVS", "MMM", "TGT",
    "F", "GM", "SOFI", "RIVN", "LCID", "HOOD", "ROKU", "DDOG", "NET", "ZS",

    # ETFs
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV",
    "XLI", "XLY", "XLP", "XLB", "XLU", "VNQ", "ARKK", "SMH", "SOXX", "IBIT"
]
for ticker in tickers:
    grab_data(ticker)
load_dotenv()

# Turn data from database into a dataframe


load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
df = pd.read_sql(f"""SELECT * FROM stock_data""", 
                engine)


#Add target for the supervised algorithm to learn from
df = df.sort_values(["ticker", "Timestamp"])

df["Target"] = (
    df.groupby("ticker")["Close"].shift(-1) > df["Close"]
).astype("Int64")

df = df.dropna(subset=["Target"])
df["Target"] = df["Target"].astype(int)
#Add numbers for tickers
df = pd.get_dummies(
    df,
    columns=["ticker"],
    prefix="ticker",
    dtype=int
)

#Split the data into training data and test data and add scaler
X = df.drop(['ticker','Target','Timestamp'],axis=1)
Y = df['Target']
X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=.3, shuffle=False)
feature_columns = X.columns.tolist()
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)
lgmodel = LogisticRegression()
lgmodel.fit(X_train, Y_train)
# predictions = lgmodel.predict(X_test)
# print(confusion_matrix(Y_test,predictions))
# print(classification_report(Y_test,predictions))
# joblib.dump(
#     {
#         "model": lgmodel,
#         "scaler": scaler,
#         "feature_columns": feature_columns
#     },
#     "logistic_model_bundle.pkl"
# )

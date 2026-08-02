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
from app import create_app
from database import db
import time

# tickers = [
#     "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "BRK.B",
#     "JPM", "V", "MA", "LLY", "XOM", "UNH", "COST", "WMT", "JNJ", "PG",
#     "HD", "ABBV", "BAC", "KO", "PEP", "CRM", "ORCL", "AMD", "NFLX", "CVX",
#     "MRK", "CSCO", "ADBE", "TMO", "MCD", "ACN", "ABT", "LIN", "WFC", "DHR",
#     "IBM", "DIS", "INTU", "TXN", "QCOM", "AMGN", "CAT", "RTX", "GE", "NOW",
#     "ISRG", "BKNG", "SPGI", "PGR", "LOW", "HON", "UNP", "GS", "BLK", "AXP",
#     "PLTR", "UBER", "SHOP", "PANW", "CRWD", "SNOW", "MSTR", "COIN", "ARM", "SMCI",
#     "MU", "ANET", "KLAC", "LRCX", "ADI", "MAR", "ADP", "VRTX", "GILD", "DE",
#     "CMCSA", "INTC", "PYPL", "SBUX", "BA", "NKE", "MDT", "CVS", "MMM", "TGT",
#     "F", "GM", "SOFI", "RIVN", "LCID", "HOOD", "ROKU", "DDOG", "NET", "ZS",

#     # ETFs
#     "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV",
#     "XLI", "XLY", "XLP", "XLB", "XLU", "VNQ", "ARKK", "SMH", "SOXX", "IBIT",

#     "PANW", "CRWD", "FTNT", "OKTA", "MDB", "ESTC", "DT", "TEAM", "HUBS", "WDAY",
#     "DDOG", "APP", "APPF", "DOCU", "TWLO", "CFLT", "S", "PATH", "ZI", "BILL",
#     "CELH", "DUOL", "ONON", "CAVA", "CMG", "YUM", "DPZ", "RSG", "WM", "FAST",
#     "ODFL", "NSC", "CPRT", "GWW", "ROK", "ETN", "PH", "EMR", "ITW", "PCAR",
#     "EOG", "MPC", "PSX", "OXY", "KMI", "OKE", "VLO", "HAL", "BKR", "DVN",
#     "AEP", "DUK", "SO", "D", "EXC", "NEE", "SRE", "PEG", "XEL", "WEC",
#     "PLD", "EQIX", "AMT", "CCI", "DLR", "PSA", "O", "SPG", "WELL", "VICI",
#     "BKNG", "EXPE", "RCL", "CCL", "NCLH", "MAR", "HLT", "LVS", "MGM", "WYNN",
#     "AIG", "CB", "PGR", "TRV", "ALL", "MET", "PRU", "AFL", "CME", "ICE",
#     "MNST", "KDP", "KHC", "GIS", "HSY", "MDLZ", "CL", "EL", "KMB", "SYY",

#         "ALGN", "ALB", "ALLE", "AOS", "APA", "APD", "ATO", "AVY", "AXON", "BALL",
#     "BEN", "BIO", "BRO", "CAG", "CAH", "CDNS", "CF", "CHD", "CHRW", "CHTR",
#     "CINF", "CLX", "CNC", "COF", "COO", "COR", "CPB", "CSGP", "CTAS", "CTRA",
#     "CTSH", "CTVA", "DAY", "DG", "DGX", "DOV", "DRI", "EBAY", "EFX", "EIX",
#     "ELV", "EMN", "ENPH", "EQR", "ERIE", "ESS", "EVRG", "EW", "EXPD", "FANG",
#     "FDX", "FE", "FICO", "FITB", "FMC", "FOX", "FOXA", "FSLR", "GEN", "GEN",
#     "GL", "GNRC", "HAS", "HBAN", "HCA", "HES", "HIG", "HOLX", "HRL", "HSIC",
#     "HST", "HSY", "HUM", "IDXX", "INCY", "IP", "IPG", "IQV", "IRM", "JBHT",
#     "JKHY", "JNPR", "K", "KEY", "KEYS", "KMX", "KR", "L", "LDOS", "LEN",
#     "LH", "LKQ", "LNT", "LULU", "LVS", "MAA", "MAS", "MKC", "MKTX", "MO",
#     "MOS", "MSCI", "MTB", "MTCH", "NDAQ", "NDSN", "NI", "NRG", "NTAP", "NTRS",
#     "NUE", "NVR", "OMC", "ON", "OTIS", "PARA", "PAYC", "PAYX", "PFG", "PKG",
#     "POOL", "PPG", "PTC", "PWR", "RJF", "ROL", "ROP", "RVTY", "SBAC", "SWKS",
#     "SYF", "TECH", "TER", "TFX", "TYL", "UAL", "UDR", "UHS", "VMC", "VRSK",
#     "VRSN", "WAB", "WAT", "WDC", "WHR", "WRB", "WY", "ZBH", "ZBRA"
# ]

# app = create_app()

# with app.app_context():
#     for ticker in tickers:
#         try:
#             print(f"Downloading {ticker}...")
#             grab_data(ticker)
#         except Exception as error:
#             print(f"{ticker} failed: {error}")

#         time.sleep(13)
# # Turn data from database into a dataframe


load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
df = pd.read_sql(f"""SELECT * FROM stock_data""", 
                engine)


# Sort each ticker chronologically
df = df.sort_values(["ticker", "Timestamp"]).reset_index(drop=True)

# Target: whether this ticker's next closing price is higher
next_close = df.groupby("ticker")["Close"].shift(-1)

df["Target"] = (next_close > df["Close"]).astype("Int64")

# Remove the final row for each ticker because it has no next-day close
df = df.dropna(subset=["Target"])
df["Target"] = df["Target"].astype(int)

# One-hot encode ticker symbols
df = pd.get_dummies(
    df,
    columns=["ticker"],
    prefix="ticker",
    dtype=int
)

# Sort globally by date for a chronological train/test split
df = df.sort_values("Timestamp").reset_index(drop=True)

split_index = int(len(df) * 0.7)

train_df = df.iloc[:split_index]
test_df = df.iloc[split_index:]

X_train = train_df.drop(columns=["Target", "Timestamp", "id"])
y_train = train_df["Target"]

X_test = test_df.drop(columns=["Target", "Timestamp", "id"])
y_test = test_df["Target"]

feature_columns = X_train.columns.tolist()

scaler = StandardScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

model = LogisticRegression(max_iter=1000)
model.fit(X_train_scaled, y_train)

predictions = model.predict(X_test_scaled)

print(confusion_matrix(y_test, predictions))
print(classification_report(y_test, predictions))
joblib.dump(
    {
        "model": model,
        "scaler": scaler,
        "feature_columns": feature_columns
    },
    "Generalized_Model.pkl"
)

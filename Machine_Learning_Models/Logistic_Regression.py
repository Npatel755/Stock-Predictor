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

load_dotenv()

# Turn data from database into a dataframe

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
df = pd.read_sql(f"""SELECT * FROM stock_data WHERE ticker = 'NVDA'""", 
                engine)

#Add target for the supervised algorithm to learn from
df['Target'] = (df['Close'].shift(-1) > df["Close"]).astype(int)
df.dropna(axis=0,inplace=True)

#Split the data into training data and test data and add scaler
X = df.drop(['ticker','Target','Timestamp'],axis=1)
Y = df['Target']
X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=.3)
feature_columns = X.columns.tolist()
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)
lgmodel = LogisticRegression()
lgmodel.fit(X_train, Y_train)
# predictions = lgmodel.predict(X_test)
# print(confusion_matrix(Y_test,predictions))
# print(classification_report(Y_test,predictions))
joblib.dump(
    {
        "model": lgmodel,
        "scaler": scaler,
        "feature_columns": feature_columns
    },
    "logistic_model_bundle.pkl"
)

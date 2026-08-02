import numpy as np
import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV

load_dotenv()

# Turn data from database into a dataframe
engine = create_engine(os.getenv('DATABASE_URL'))
df = pd.read_sql(f"""SELECT * FROM stock_data WHERE ticker = 'NVDA'""", 
                 engine)
#Add target for the supervised algorithm to learn from
df['Target'] = (df['Close'].shift(-1) > df["Close"]).astype(int)
df.dropna(axis=0,inplace=True)

#Split the data into training data and test data and scale the data
X = df.drop(['ticker','Target','Timestamp','id'],axis=1)
Y = df['Target']
X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=.3)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)
rfcmodel = RandomForestClassifier(max_depth = None, min_samples_leaf = 2, min_samples_split = 5, n_estimators = 100)

rfcmodel.fit(X_train, Y_train)
predictions = rfcmodel.predict(X_test)
print(confusion_matrix(Y_test,predictions))
print(classification_report(Y_test,predictions))
param_grid = {
    "n_estimators": [100, 200, 500],
    "max_depth": [None, 5, 10, 20],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf": [1, 2, 4]
}

grid = GridSearchCV(
    estimator=RandomForestClassifier(random_state=42),
    param_grid=param_grid,
    cv=5,
    scoring="accuracy",
    n_jobs=-1
)

grid.fit(X_train, Y_train)

print(grid.best_params_)
print(grid.best_score_)
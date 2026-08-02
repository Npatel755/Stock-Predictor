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
from xgboost import XGBClassifier
from sklearn.model_selection import GridSearchCV
from xgboost import XGBClassifier
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
)
import joblib

load_dotenv()

# Turn data from database into a dataframe
engine = create_engine(os.getenv('DATABASE_URL'))
df = pd.read_sql(f"""SELECT * FROM stock_data""", 
                 engine)
#Add target for the supervised algorithm to learn from
df['Target'] = (df['Close'].shift(-1) > df["Close"]).astype(int)
df.dropna(axis=0,inplace=True)

#Split the data into training data and test data and scale the data
X = df.drop(['ticker','Target','Timestamp','id'],axis=1)
Y = df['Target']
X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=.3)
scaler = StandardScaler()

feature_columns = X_train.columns.tolist()

X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)


model = XGBClassifier(colsample_bytree = 0.8, learning_rate = 0.05, max_depth = 7, n_estimators = 500, subsample = 1.0 )

model.fit(X_train, Y_train)

predictions = model.predict(X_test)

print(confusion_matrix(Y_test, predictions))
print(classification_report(Y_test, predictions))


# param_distributions = {
#     "n_estimators": [100, 200, 300, 500, 700],
#     "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.2],
#     "max_depth": [2, 3, 4, 5, 6, 8],
#     "min_child_weight": [1, 3, 5, 7, 10],
#     "subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
#     "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
#     "gamma": [0, 0.05, 0.1, 0.25, 0.5],
#     "reg_alpha": [0, 0.001, 0.01, 0.1, 1],
#     "reg_lambda": [0.5, 1, 2, 5, 10],
# }

# time_split = TimeSeriesSplit(n_splits=5)

# search = RandomizedSearchCV(
#     estimator=model,
#     param_distributions=param_distributions,
#     n_iter=50,
#     scoring="roc_auc",
#     cv=time_split,
#     verbose=2,
#     random_state=42,
#     n_jobs=-1,
#     refit=True
# )

# search.fit(X_train, Y_train)

# best_model = search.best_estimator_

# print("Best parameters:")
# print(search.best_params_)

# print("Best cross-validation ROC AUC:")
# print(search.best_score_)

joblib.dump(
    {
        "model": model,
        "scaler": scaler,
        "feature_columns": feature_columns
    },
    "xg_boost_bundle.pkl"
)

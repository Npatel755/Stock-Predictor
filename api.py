from schemas import TickerSchema
from flask_smorest import Blueprint
from flask.views import MethodView
import joblib
from database import db
from sqlalchemy import select
from models.stockmodel import StockModel
from app import app
import pandas as pd
from massive_stock_requester import grab_data

blp = Blueprint('Tickers',__name__,description="Get prediction on ticker")

model_bundle = joblib.load("stock_model.pkl")
model = model_bundle["model"]
scaler = model_bundle["scaler"]
feature_columns = model_bundle["feature_columns"]


@blp.route('Ticker/<string:ticker_symbol>')
class get_prediction(MethodView):
    

    @blp.arguments(TickerSchema)
    @blp.response(200,TickerSchema)
    def get_ticker_prediction(ticker_data):
        grab_data(ticker_data['ticker'])
        
        latest_row = db.session.execute(
                select(StockModel)
                .where(StockModel.ticker == ticker_data['ticker'])
                .order_by(StockModel.Timestamp.desc())
            ).scalar()
        if latest_row is None:
            abort(
                404,
                message=f"No stock data found for {ticker_data['ticker']}"
            )

        # Convert SQLAlchemy row into one-row DataFrame
        latest_features = pd.DataFrame(
            [
                {
                    column: getattr(latest_row, column)
                    for column in feature_columns
                }
            ],
            columns=feature_columns
        )

        # Use the existing fitted scaler
        latest_features_scaled = scaler.transform(latest_features)

        prediction = int(
            model.predict(latest_features_scaled)[0]
        )

        probability_up = float(
            model.predict_proba(latest_features_scaled)[0][1]
        )

        return {
            "ticker": ticker_data['ticker'],
            "latest_date": latest_row.Timestamp.isoformat(),
            "prediction": "UP" if prediction == 1 else "DOWN",
            "prediction_value": prediction,
            "probability_up": probability_up
        }


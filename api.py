from schemas import TickerSchema
from flask_smorest import Blueprint
from flask.views import MethodView
import joblib
from database import db
from sqlalchemy import select
from models.stockmodel import StockModel
import pandas as pd
from massive_stock_requester import grab_data
from flask_smorest import abort


blp = Blueprint('Tickers',__name__,description="Get prediction on ticker")

model_bundle = joblib.load("xg_boost_bundle.pkl")
model = model_bundle["model"]
scaler = model_bundle["scaler"]
feature_columns = model_bundle["feature_columns"]


@blp.route('/Ticker/<string:ticker_symbol>')
class GetPrediction(MethodView):
    


    @blp.response(200,TickerSchema)
    def get(self, ticker_symbol):

        grab_data(ticker_symbol)
        
        latest_row = db.session.execute(
                select(StockModel)
                .where(StockModel.ticker == ticker_symbol)
                .order_by(StockModel.Timestamp.desc())
            ).scalar()
        if latest_row is None:
            abort(
                404,
                message=f"No stock data found for {ticker_symbol}"
            )

        # Convert SQLAlchemy row into one-row DataFrame
        feature_data = {}

        for column in feature_columns:
            if column.startswith("ticker_"):
                expected_ticker = column.removeprefix("ticker_")
                feature_data[column] = int(
                    ticker_symbol == expected_ticker
                )
            else:
                feature_data[column] = getattr(latest_row, column)

        latest_features = pd.DataFrame(
            [feature_data],
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
            "ticker": ticker_symbol,
            "latest_date": latest_row.Timestamp.isoformat(),
            "prediction": "UP" if prediction == 1 else "DOWN",
            "prediction_value": prediction,
            "model_confidence": probability_up*100,
            "probability_up": probability_up
        }


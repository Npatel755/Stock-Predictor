# Stock Predictor API

A machine learning-powered stock prediction API that predicts whether a stock's price is likely to move **UP** or **DOWN** on the next trading day using technical indicators and gradient boosting.

---

## 🚀 Features

- Downloads historical stock market data
- Stores data in PostgreSQL
- Calculates technical indicators automatically
- Trains multiple machine learning models
  - Logistic Regression
  - Random Forest
  - XGBoost
- Hyperparameter tuning
- REST API built with Flask
- Dockerized for easy deployment
- Predicts any supported stock ticker through a simple API request

---

# Example Prediction

Request

```http
GET /Ticker/AAPL
```

Response

```json
{
  "ticker": "AAPL",
  "latest_date": "2026-07-31",
  "prediction": "UP",
  "prediction_value": 1,
  "probability_up": 0.822
}
```

---

# Machine Learning Pipeline

```
Historical Market Data
          │
          ▼
    Technical Indicators
          │
          ▼
      PostgreSQL
          │
          ▼
 Feature Engineering
          │
          ▼
   XGBoost Classifier
          │
          ▼
 Flask REST API
          │
          ▼
      JSON Response
```

---

# Technical Indicators

The model currently utilizes a variety of technical indicators including:

- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- MACD
- RSI
- Volume
- VWAP
- Daily Returns
- High-Low %
- Open-Close %
- Additional engineered features

More indicators can easily be added to improve performance.

---

# Tech Stack

| Category            | Technology     |
| ------------------- | -------------- |
| Language            | Python         |
| API                 | Flask          |
| Machine Learning    | Scikit-Learn   |
| Gradient Boosting   | XGBoost        |
| Database            | PostgreSQL     |
| ORM                 | SQLAlchemy     |
| Data Processing     | Pandas         |
| Numerical Computing | NumPy          |
| Containerization    | Docker         |
| Market Data         | Polygon.io API |

---

# Project Structure

```
Stock Predictor/
│
├── app.py
├── database.py
├── models/
├── routes/
├── schemas/
├── database_models/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── MachineLearning/
│   ├── LogisticRegression.py
│   ├── RandomForestClassifier.py
│   ├── xg_Boost.py
│   └── train_model.py
│
├── Data/
│   ├── download_data.py
│   ├── indicators.py
│   └── preprocessing.py
│
└── README.md
```

---

# Model Performance

Current best model:

| Model               | Accuracy |
| ------------------- | -------- |
| Logistic Regression | ~50%     |
| Random Forest       | ~57%     |
| **XGBoost**         | **~59%** |

The XGBoost model currently provides the strongest predictive performance.

---

# API Endpoints

## Predict Stock Direction

```http
GET /Ticker/<ticker>
```

Example

```http
GET /Ticker/NVDA
```

Returns

```json
{
  "ticker": "NVDA",
  "prediction": "UP",
  "prediction_value": 1,
  "probability_up": 0.81
}
```

---

# Environment Setup

This project requires a PostgreSQL database and a Polygon.io API key.

---

## 1. Clone the Repository

```bash
git clone https://github.com/yourusername/StockPredictor.git
cd StockPredictor
```

---

## 2. Create a `.env` File

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=postgresql://postgres:password@db:5432/stock_database
POLYGON_API_KEY=YOUR_POLYGON_API_KEY
```

If running the application **outside Docker**, your database URL will typically look like:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/stock_database
```

---

## 3. PostgreSQL Setup

### Option A (Recommended) – Docker

Start PostgreSQL with Docker Compose:

```bash
docker compose up --build
```

The application will automatically connect using the `DATABASE_URL` defined in your `.env` file.

---

### Option B – Local PostgreSQL Installation

1. Install PostgreSQL.
2. Create a new database.

Example:

```sql
CREATE DATABASE stock_database;
```

3. Update your `.env` file with your username, password, host, and database name.

Example:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/stock_database
```

---

## 4. Polygon.io API Key

Historical market data is provided by Polygon.io.

1. Create a free account at https://polygon.io/
2. Navigate to your Dashboard.
3. Copy your API Key.
4. Add it to your `.env` file.

Example:

```env
POLYGON_API_KEY=YOUR_API_KEY_HERE
```

---

## 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 6. Run Database Migrations

```bash
flask db upgrade
```

---

## 7. Start the Application

```bash
docker compose up
```

or locally

```bash
flask run
```

---

## Environment Variables

| Variable          | Description                                                |
| ----------------- | ---------------------------------------------------------- |
| `DATABASE_URL`    | PostgreSQL connection string                               |
| `POLYGON_API_KEY` | Polygon.io API key used to download historical market data |

---

## Example `.env`

```env
DATABASE_URL=postgresql://postgres:password@db:5432/stock_database
POLYGON_API_KEY=YOUR_POLYGON_API_KEY
```

# Future Improvements

- Feature importance visualization
- SHAP explanations
- Walk-forward validation
- Live market predictions
- Automated model retraining
- Web dashboard
- User authentication
- Prediction history
- Portfolio tracking
- Buy/Sell signal generation
- Confidence calibration
- Additional technical indicators
- News sentiment analysis
- LSTM and Transformer models

---

# Disclaimer

This project is intended for educational and research purposes only.

The predictions generated by this model should **not** be considered financial advice. Stock markets are inherently unpredictable, and no machine learning model can guarantee future performance.

---

# Author

**Nick Patel**

Machine Learning • Software Engineering • Data Engineering

Built using Python, Flask, PostgreSQL, Docker, and XGBoost.

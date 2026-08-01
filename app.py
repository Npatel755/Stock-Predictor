from flask_smorest import Api
from flask import Flask,jsonify

app = Flask(__name__)
api = Api(app)
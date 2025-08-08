from flask import Flask
from mongoengine import connect

def create_app():
    app = Flask(__name__)
    connect(
        host="mongodb+srv://cards:sEnrCeIyvA3oaQpw@cluster0.uwzsclh.mongodb.net/referral_system?retryWrites=true&w=majority"
    )
    return app


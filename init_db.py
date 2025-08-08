from db_config import create_app  # db is now MongoEngine()
from models import ReferDetails,ReferralData

app = create_app()

with app.app_context():
    # No need to call db.create_all() for MongoDB
    print("✅ MongoDB connected successfully. Collections will be created automatically on first insert.")

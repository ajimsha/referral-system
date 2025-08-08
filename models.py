from mongoengine import Document, StringField, DictField, BooleanField, IntField, DateTimeField
from datetime import datetime

class ReferralData(Document):
    app_package_name = StringField(required=True)
    referral_json = DictField()
    is_active = BooleanField(default=True)  # snake_case for consistency
    created_at = DateTimeField(default=datetime.utcnow)

class ReferDetails(Document):
    app_package_name = StringField(required=True)
    user_id = StringField()
    user_name = StringField()
    lang = StringField()
    code = StringField(required=True)
    redemptions = IntField(default=0) ## redeem count
    is_used = IntField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)

class RedeemDetails(Document):
    app_package_name = StringField(required=True)
    user_id = StringField()
    code = StringField(required=True)
    is_redeemed = IntField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)




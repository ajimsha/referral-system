from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from db_config import create_app
from functools import wraps
from models import ReferralData, ReferDetails,RedeemDetails
import requests
import json
import pytz
import random

app = create_app()
CORS(app, supports_credentials=True)

DEX_URL = "https://us-central1-riafy-public.cloudfunctions.net/genesis?otherFunctions=dexDirect&type=r10-apps-ftw"

VALID_API_KEYS = {
    "HJVV4XapPZVVfPSiQThYGZdAXkRLUWvRfpNE5ITMfbC3A4Q"
}
VALID_ADMIN_API_KEYS = {
    "qLCldUAONP1dLENspNVLtZn1H3X9FagUh2nj0RiNGGJcQCq"
}

IST = pytz.timezone("Asia/Kolkata")


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if provided_key not in VALID_API_KEYS:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if provided_key not in VALID_ADMIN_API_KEYS:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated



# ======================================================
# API 1 - Get referral JSON + Generate referral code
# ======================================================
@app.route("/api/referral-promote", methods=["POST"])
@require_api_key
def get_referral():
    lang = request.args.get("lang")  # still from query param

    data_json = request.get_json(force=True)  # get JSON body
    app_package_name = data_json.get("app_package_name")
    username = data_json.get("username")
    user_id = data_json.get("user_id")

    if not all([app_package_name, username, user_id]) or not lang:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # Check if referral data exists in ReferralData
    data = ReferralData.objects(app_package_name=app_package_name, isActive=True).first()
    if not data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404

    # Check if the user already has a referral code in ReferDetails
    existing_redeem = ReferDetails.objects(app_package_name=app_package_name, user_id=user_id).first()

    if existing_redeem:
        referral_code = existing_redeem.code
    else:
        referral_code = (username[:4] if len(username) >= 4 else username) + str(random.randint(1000, 9999))
        ReferDetails(
            app_package_name=app_package_name,
            user_id=user_id,
            user_name=username,
            code=referral_code
        ).save()

    referral_url = f"https://chatgpt.com/c/{referral_code}"

    return jsonify({
        "status": "success",
        "message": "Referral data fetched",
        "data": {
            "referral_json": data.referral_json,
            "referral_code": referral_code,
            "referral_url": referral_url
        }
    }), 200


# ======================================================
# API 2 - Referral referral-status
# ======================================================
@app.route("/api/referral-status", methods=["POST"])
@require_api_key
def referral_stats():
    lang = request.args.get("lang")  # still from query param

    data_json = request.get_json(force=True)  # get JSON body
    app_package_name = data_json.get("app_package_name")
    user_id = data_json.get("user_id")
    username = data_json.get("username")

    if not all([app_package_name, user_id, username]) or not lang:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
    
    # Get redemption count (last redeem for the user)
    last_redeem = ReferDetails.objects(app_package_name=app_package_name, user_id=user_id).order_by('-created_at').first()
    redemption_count = last_redeem.redemptions if last_redeem else 0

    # Get page2_referral_status JSON (only one per app)
    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    page2_referral_status = referral_data.page2_referral_status if referral_data else {}

    return jsonify({
        "status": "success",
        "message": "Referral stats fetched",
        "data": {
            "app_package_name": app_package_name,
            "user_id": user_id,
            "username": username,
            "redemption_count": redemption_count,
            "page2_referral_status": page2_referral_status
        }
    }), 200


# ======================================================
# API 3 - Share page JSON
# ======================================================
@app.route("/share/<code>", methods=["GET"])
def share_code(code):
    redeem = ReferDetails.objects(code=code).first()
    if not redeem:
        return jsonify({"status": "error", "message": "Invalid referral code"}), 404

    referral_data = ReferralData.objects(app_package_name=redeem.app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    page3_referralDownload = referral_data.page3_referralDownload if referral_data else {}

    return jsonify({
        "status": "success",
        "message": "Share data fetched",
        "data": {
            "page3_referralDownload": page3_referralDownload,
        }
    }), 200

# ======================================================
# API 4 - Redeem JSON
# ======================================================
@app.route("/api/referral-redeem", methods=["POST"])
@require_api_key
def redeem_json():
    lang = request.args.get("lang")  # still query param

    data_json = request.get_json(force=True)
    app_package_name = data_json.get("app_package_name")
    user_id = data_json.get("user_id")

    if not app_package_name:
        return jsonify({"status": "error", "message": "Missing app_package_name"}), 400

    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    page4_referralRedeem = referral_data.page4_referralRedeem if referral_data else {}

    return jsonify({
        "status": "success",
        "message": "Redeem data fetched",
        "data": {
            "page4_referralRedeem": page4_referralRedeem
        }
    }), 200


# ======================================================
# API 5 - Check Redeem Code
# ======================================================
@app.route("/api/checkredeem", methods=["POST"])
@require_api_key
def check_redeem():
    lang = request.args.get("lang")  # still query param

    data_json = request.get_json(force=True)
    app_package_name = data_json.get("app_package_name")
    code = data_json.get("code")
    user_id = data_json.get("user_id")

    if not all([app_package_name, code, user_id]):
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # 1. Check if referral code exists
    refer_doc = ReferDetails.objects(app_package_name=app_package_name, code=code).first()
    if not refer_doc:
        return jsonify({"status": "error", "valid": False, "message": "Invalid code"}), 404

    # 2. Check if the user has already redeemed
    existing_redeem = RedeemDetails.objects(app_package_name=app_package_name, user_id=user_id, code=code).first()
    if existing_redeem:
        return jsonify({"status": "error", "valid": False, "message": "You already redeemed this code"}), 400

    # 3. Create RedeemDetails record
    RedeemDetails(
        app_package_name=app_package_name,
        user_id=user_id,
        code=code,
        is_redeemed=1,
        created_at=datetime.utcnow()
    ).save()

    # 4. Increment redemptions count for code owner
    refer_doc.redemptions += 1
    if refer_doc.redemptions >= 5:
        refer_doc.is_completed = 1
    refer_doc.save()

    return jsonify({
        "status": "success",
        "valid": True,
        "message": "Code redeemed successfully"
    }), 200





@app.route("/api/savereferraldata", methods=["POST"])
@require_api_key
def create_referral_data():
    data = request.get_json(force=True)

    app_package_name = data.get("app_package_name")
    referral_json = data.get("referral_json", {})
    is_active = data.get("is_active", True)

    if not app_package_name:
        return jsonify({"status": "error", "message": "app_package_name is required"}), 400

    # Check if ReferralData for this app_package_name already exists
    existing = ReferralData.objects(app_package_name=app_package_name).first()
    if existing:
        return jsonify({"status": "error", "message": "ReferralData already exists for this app_package_name"}), 409

    referral_data = ReferralData(
        app_package_name=app_package_name,
        referral_json=referral_json,
        is_active=is_active,
        created_at=datetime.utcnow()
    )
    referral_data.save()

    return jsonify({
        "status": "success",
        "message": "ReferralData created successfully",
        "data": {
            "app_package_name": app_package_name,
            "referral_json": referral_json,
            "is_active": is_active,
            "created_at": referral_data.created_at.isoformat()
        }
    }), 201





def personalize_notification(notification_data, user_name):
    if not notification_data:
        return {}

    first_name = user_name.strip().split()[0] if user_name and user_name.strip() else None
    has_name = bool(first_name)

    message = (
        notification_data.get("personalised_message", "").replace("{{name}}", first_name)
        if has_name else
        notification_data.get("message", "")
    )

    title = (
        notification_data.get("personalised_notification_title", "").replace("{{name}}", first_name)
        if has_name else
        notification_data.get("notification_title", "")
    )

    return {
        "notification_title": title,
        "message": message,
        "language": notification_data.get("language"),
        "app_name": notification_data.get("app_name"),
        "scheduled_day": notification_data.get("scheduled_day"),
        "scheduled_time": notification_data.get("scheduled_time"),
        "status": notification_data.get("status")
    }


def create_cards_json(appName, recentUserAction,language):
   
    api_url=DEX_URL
    payload = {   
    "appname": "re-engage",
    "ogQuery": json.dumps({
        "appname": appName,
        "recent-user-actions": recentUserAction,
        "targetLanguage": language
    }, indent=4),
    "reply-mode": "json"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    

    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    

def create_notification_json(app_name, recent_user_actions, language,title,subtitle,dateandtime):
    """
    Sends a POST request to create a streak.

    Parameters:
        api_url (str): The endpoint to send the request to.
        streak_name (str): Name of the streak.
        streak_description (str): Description of the streak.
        token (str, optional): Bearer token for authentication. Defaults to None.

    Returns:
        dict: The JSON response from the API or error message.
    """
    api_url=DEX_URL
    payload = {
    "ask-dex":"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",    
    "appname": "acd",
    "ogQuery": json.dumps({
        "appname": app_name,
        "recent-user-actions": recent_user_actions,
        "targetLanguage": language,
        "title": title,
        "subtitle": subtitle,
        "datetime": dateandtime
    }, indent=4),
    "reply-mode": "json"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }



    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}




# -------------------
# Run the app
# -------------------


if __name__ == '__main__':
    app.run(port=4000, debug=True)
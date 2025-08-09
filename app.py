from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from db_config import create_app
from functools import wraps
from models import ReferralData, ReferDetails,RedeemDetails,App
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
    lang = request.args.get("lang") or "en"  # default to 'en' if missing

    data_json = request.get_json(force=True)  # get JSON body
    app_package_name = data_json.get("app_package_name")
    username = data_json.get("username")
    user_id = data_json.get("user_id")

    if not all([app_package_name, username, user_id]) or not lang:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # Check if referral data exists in ReferralData

    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    
    page1_referralPromote = {}
    if referral_data.referral_json:
        page1_referralPromote = referral_data.referral_json.get(lang, {}).get("page1_referralPromote", {})

    # Check if the user already has a referral code in ReferDetails
    existing_redeem = ReferDetails.objects(app_package_name=app_package_name, user_id=user_id).first()
    current_redemptions=0
    pending_redemptions=5
    if existing_redeem:
        referral_code = existing_redeem.code
        current_redemptions = existing_redeem.redemptions
        pending_redemptions = (5 - existing_redeem.redemptions)
        
    else:
        referral_code = (username[:4] if len(username) >= 4 else username) + str(random.randint(1000, 9999))
        ReferDetails(
            app_package_name=app_package_name,
            user_id=user_id,
            lang=lang,
            user_name=username,
            code=referral_code
        ).save()

    referral_url = f"https://chatgpt.com/c/{referral_code}"

    return jsonify({
        "status": "success",
        "message": "Referral data fetched",
        "data": {
            "page1_referralPromote": page1_referralPromote,
            "referral_code": referral_code,
            "referrer_name": username,
            "current_redemptions": current_redemptions,
            "pending_redemptions": pending_redemptions,
            "referral_url": referral_url
        }
    }), 200


# ======================================================
# API 2 - Referral referral-status
# ======================================================
@app.route("/api/referral-status", methods=["POST"])
@require_api_key
def referral_stats():
    lang = request.args.get("lang") or "en"  # default to 'en' if missing

    data_json = request.get_json(force=True)  # get JSON body
    app_package_name = data_json.get("app_package_name")
    user_id = data_json.get("user_id")
    username = data_json.get("username")

    if not all([app_package_name, user_id, username]) or not lang:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
    
    # Get redemption count (last redeem for the user)
    existing_redeem = ReferDetails.objects(app_package_name=app_package_name, user_id=user_id).order_by('-created_at').first()
    referral_code = existing_redeem.code
    current_redemptions = existing_redeem.redemptions if existing_redeem else 0
    pending_redemptions = (5 - existing_redeem.redemptions)


    # Get page2_referral_status JSON (only one per app)
    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
   
    page2_referralStatus = {}
    if referral_data.referral_json:
        page2_referralStatus = referral_data.referral_json.get(lang, {}).get("page2_referralStatus", {})

    return jsonify({
        "status": "success",
        "message": "Referral stats fetched",
        "data": {
            "app_package_name": app_package_name,
            "user_id": user_id,
            "referral_code": referral_code,
            "referrer_name": username,
            "current_redemptions": current_redemptions,
            "pending_redemptions": pending_redemptions,
            "target_redemptions": 5,
            "page2_referralStatus": page2_referralStatus
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

    lang = redeem.lang or "en"  # fetch lang from ReferDetails, default to 'en' if missing
    referral_code = redeem.code
    username = redeem.user_name
    app_package_name = redeem.app_package_name
    

    app_details = App.objects(app_package_name=app_package_name).first()
    if not app_details:
        return jsonify({"status": "error", "message": "Invalid App details"}), 404
    app_name = app_details.app_name
    play_store_link = app_details.play_store_link or ""
    app_store_link = app_details.app_store_link or ""


    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
   
    # Safely get page4_referralRedeem from referral_json for the language
    page3_referralDownload = {}
    if referral_data.referral_json:
        page3_referralDownload = referral_data.referral_json.get(lang, {}).get("page3_referralDownload", {})

    return jsonify({
        "status": "success",
        "message": "Share data fetched",
        "data": {
            "app_name": app_name,
            "referrer_name": username,
            "referral_code": referral_code,
            "play_store_link": play_store_link,
            "app_store_link": app_store_link,
            "page3_referralDownload": page3_referralDownload,
        }
    }), 200

# ======================================================
# API 4 - Redeem JSON
# ======================================================
@app.route("/api/referral-redeem", methods=["POST"])
@require_api_key
def redeem_json():
    lang = request.args.get("lang") or "en"  # default to 'en' if missing

    data_json = request.get_json(force=True)
    app_package_name = data_json.get("app_package_name")
    user_id = data_json.get("user_id")

    if not app_package_name:
        return jsonify({"status": "error", "message": "Missing app_package_name"}), 400

    referral_data = ReferralData.objects(app_package_name=app_package_name).first()
    if not referral_data:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    # Safely get page4_referralRedeem from referral_json for the language
    page4_referralRedeem = {}
    if referral_data.referral_json:
        page4_referralRedeem = referral_data.referral_json.get(lang, {}).get("page4_referralRedeem", {})

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
    lang = request.args.get("lang") or "en"  # default to 'en' if missing

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
            
        }
    }), 201





@app.route("/api/admin/savereferraldata", methods=["POST"])
@require_api_key
def create_or_update_admin_referral_data():
    data = request.get_json(force=True)

    app_package_name = data.get("app_package_name")
    referral_json = data.get("referral_json", {})
    is_active = data.get("is_active", True)

    if not app_package_name:
        return jsonify({"status": "error", "message": "app_package_name is required"}), 400

    # Check if ReferralData exists for this app_package_name
    existing = ReferralData.objects(app_package_name=app_package_name).first()

    if existing:
        # Update existing record
        existing.referral_json = referral_json
        existing.is_active = is_active
        existing.save()

        return jsonify({
            "status": "success",
            "message": "ReferralData updated successfully",
            "data": {
                "app_package_name": existing.app_package_name,
                "referral_json": existing.referral_json,
                "is_active": existing.is_active,
                "created_at": existing.created_at.isoformat()
            }
        }), 200

    # Create new record
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
            "app_package_name": referral_data.app_package_name,
            "referral_json": referral_data.referral_json,
            "is_active": referral_data.is_active,
            "created_at": referral_data.created_at.isoformat()
        }
    }), 201




@app.route("/api/admin/getreferraldata", methods=["GET"])
@require_api_key
def list_referral_data():
    app_package_name = request.args.get("app_package_name")

    if not app_package_name:
        return jsonify({"status": "error", "message": "app_package_name is required"}), 400

    # Fetch data for the given package name
    referral_list = ReferralData.objects(app_package_name=app_package_name).order_by("-created_at")

    if not referral_list:
        return jsonify({"status": "error", "message": "No referral data found"}), 404
    

    app_details = App.objects(app_package_name=app_package_name).first()
    if not app_details:
        return jsonify({"status": "error", "message": "Invalid App details"}), 404
    app_name = app_details.app_name
    app_description = app_details.description or ""
    

    # Prepare output
    data = []
    for item in referral_list:
        data.append({
            "app_package_name": item.app_package_name,
            "app_name": app_name,
            "add_description": app_description,
            "referral_json": item.referral_json
        })

    return jsonify({
        "status": "success",
        "data": data
    }), 200



@app.route("/api/admin/listapps", methods=["GET"])
@require_api_key
def list_apps():
    app_package_name = request.args.get("app_package_name")

    # Build query
    query = {}
    if app_package_name:
        query["app_package_name"] = app_package_name

    # Fetch apps
    apps = App.objects(**query).order_by("-created_at")

    if not apps:
        return jsonify({"status": "error", "message": "No apps found"}), 404

    # Prepare response data
    data = []
    for app_obj in apps:
        data.append({
            "app_package_name": app_obj.app_package_name,
            "app_name": app_obj.app_name,
            "description": app_obj.description,
            "app_store_link": app_obj.app_store_link,
            "play_store_link": app_obj.play_store_link,
            "created_at": app_obj.created_at.isoformat(),
            "updated_at": app_obj.updated_at.isoformat()
        })

    return jsonify({
        "status": "success",
        "data": data
    }), 200




@app.route("/api/admin/createapp", methods=["POST"])
@require_api_key
def create_app():
    data = request.get_json(force=True)

    app_package_name = data.get("app_package_name")
    app_name = data.get("app_name")
    app_description = data.get("description", "")
    play_store_link = data.get("play_store_link", "")
    app_store_link = data.get("app_store_link", "")
    language ="en"

    # Validate required fields
    if not all([app_package_name, app_name,app_description]) :
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # Check if app already exists
    existing = App.objects(app_package_name=app_package_name).first()
    if existing:
        return jsonify({"status": "error", "message": "App already exists with this app_package_name"}), 409

    referral_json=create_refferel_data(app_name, app_description, language)

    referral_data = ReferralData(
        app_package_name=app_package_name,
        referral_json=referral_json,
        created_at=datetime.utcnow()
    )
    referral_data.save()

    
    # Create and save app
    app_obj = App(
        app_package_name=app_package_name,
        app_name=app_name,
        description=app_description,
        app_store_link = app_store_link,
        play_store_link = play_store_link,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    app_obj.save()

    return jsonify({
        "status": "success",
        "message": "App created successfully",
        "data": {
            "app_package_name": app_package_name,
            "app_name": app_name,
            "description": app_description,
            "referral_json": referral_json,
            "created_at": app_obj.created_at.isoformat(),
            "updated_at": app_obj.updated_at.isoformat()
        }
    }), 201





@app.route("/api/admin/editapp", methods=["POST"])
@require_api_key
def edit_app():
    data = request.get_json(force=True)

    app_package_name = data.get("app_package_name")
    play_store_link = data.get("play_store_link")
    app_store_link = data.get("app_store_link")


    # Validate required field
    if not app_package_name:
        return jsonify({"status": "error", "message": "app_package_name is required"}), 400

    # Fetch existing app
    existing = App.objects(app_package_name=app_package_name).first()
    if not existing:
        return jsonify({"status": "error", "message": "App not found"}), 404

    # Update only provided fields
    
    if play_store_link is not None:
        existing.play_store_link = play_store_link
    if app_store_link is not None:
        existing.app_store_link = app_store_link


    existing.updated_at = datetime.utcnow()
    existing.save()

    return jsonify({"status": "success", "message": "App updated successfully"}), 200




def create_refferel_data(app_name, app_description, language):

    referral_promote_json = create_referral_promote_json(app_name, app_description, language)
    referral_status_json = create_referral_status_json(app_name, app_description, language)
    referral_download_json = create_referral_download_json(app_name, app_description, language)
    referral_redeem_json = create_referral_redeem_json(app_name, app_description, language)
    notifications= {
                        "redeemer": [],
                        "referrer": [
                            {
                                "body": "Someone just joined using your code. 4 more and you’ll unlock a month of Premium!",
                                "cta": "Check your progress",
                                "id": "referral_progress_4_left",
                                "title": "🔥 First win!"
                            },
                            {
                                "body": "Another friend joined! Just 3 more redemptions to score your free Premium month.",
                                "cta": "See who’s next",
                                "id": "referral_progress_3_left",
                                "title": "🚀 You’re gaining momentum"
                            },
                            {
                                "body": "You’ve got 3 redemptions now. Only 2 more to go for your Premium reward!",
                                "cta": "View your status",
                                "id": "referral_progress_2_left",
                                "title": "⚡ Almost halfway to the finish"
                            },
                            {
                                "body": "4 out of 5 done. Just 1 more friend and you’ve got your free month of Premium.",
                                "cta": "Push for the last one",
                                "id": "referral_progress_1_left",
                                "title": "🏁 One step away!"
                            },
                            {
                                "body": "Congratulations! You’ve unlocked 1 month of free Premium through referrals.",
                                "cta": "Redeem now",
                                "id": "referral_reward_unlocked",
                                "title": "🎉 You did it!"
                            }
                        ]
                    }
    return {
        language: {
            "notifications": notifications,
            "page1_referralPromote": referral_promote_json["data"],
            "page2_referralStatus": referral_status_json["data"],
            "page3_referralDownload":referral_download_json["data"],
            "page4_referralRedeem": referral_redeem_json["data"]
        }
    }



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



    

def create_referral_promote_json(app_name, app_description, language):
    """
    Returns:
        dict: The JSON response from the API or error message.
    """
    api_url=DEX_URL
    payload = {
    "ask-dex":"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",    
    "appname": "acd",
    "ogQuery": json.dumps({
        "app_name": app_name,
        "app_description": app_description,
        "target_language": language,
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
    

def create_referral_status_json(app_name, app_description, language):
    """
    Returns:
        dict: The JSON response from the API or error message.
    """
    api_url=DEX_URL
    payload = {
    "ask-dex":"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",    
    "appname": "acd",
    "ogQuery": json.dumps({
        "app_name": app_name,
        "app_description": app_description,
        "target_language": language,
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
    


def create_referral_download_json(app_name, app_description, language):
    """
    Returns:
        dict: The JSON response from the API or error message.
    """
    api_url=DEX_URL
    payload = {
    "ask-dex":"AOO6xOphLdfYy4YJtB1kLoBtZvC61OMPrgkktemw3eb2GCJNAx9k6kLJEo5DRBWZoJK/GH9qFfSIW2wuzud7JEd6XH3hZDja8jwZ0BOM8k5dz+UoI51Ee3e0Zu28aXWDC7asLJIdICrIMNv+jRJynP018QQIGgOEV4VX6qxsVHY4AxtjQ4kGZY/+gFxBnrpUhV+dC8HiMzdJDukcCDjC58gechELf6Jm97DotczOglaU9+H2gbsRfCaas7qA+S+FEIJb0MyVKE2FeIMk/btMShI1TLRQC5d38onFosnaMUXEgRElO483MD2NsFZG12+8QbrZZFmT8YzBfiGJa38akAY3Y9lAw63KvMvl2hEEn0H/ko1HPEy1sM8HcAKlzV2WWBrNUay+G2Ynel/M6+PXW6JcsKPjg8JhvD6NtawbM2jKjzJfjSSwRmoJ2LHe0mdZtZ6UUkJH3su4LjsLxM6JeVEv1AOl2k2LvHSIRYwXGXU7BgjbH0j/sxKQJhTpM1iM4bS4p2LfjMeSHoyk9fGZDNrLADLbMhWf8XBI2bC8WUiJNFwJmbWBRmtl0M/wa+xiMkjRUfH8QWj9af1WQvJOiEuyrkQRj4XxiFOmtJTMFwaMJ51nRG+icOOlPZS0re780HszlZ+oNLRDn3L2Hx5D7BAJQwoSyXhhHDS196CuVjZzeI8rJm68Pn+PlJpEKzQonZ34VTc1D93svzi4w7thaHi1/clx9sWN7suBOkZjMXZZ5rU54xpCXfG082M+XTdIVqmuabGus6Ed/8jV7PlGig7oTN7vrD8mEgTJ6wryfyxp4Tikj2zlYn9ZsL2u+N7Cl4AyA/Ay6Aax+m2NzHbUz2Zha9M8+BQ0mU2nsrhQQb2u4OqGP0S3YvtPKkvvCVCyfE+ly5GfzSaJKoew7O8BiE5dHrrjtglwar/ciT2M6rebatFr91ENXJEWvjfl2VQvnSbG+Ypp+XXMvBwzqaEXAtmCPGKGYO0QkuR+lOlcpCELSJEwmPcm245YvvuvY5viBFkmp/gXrP5ds+LV2RUok3b/WLbodI/XrPi7U1T+sY7SXfsE8H5VeC3sKmKm8vG8JOPN8ISfZVHyiijg13Y/U+8jXezMffUtLCVIztVPskW4p0II19+C1yxlMbv4EkbSNOoK2Nmyo8dPrDbT397itgyEvKyfn3lNkvzDLUgP4FIfTaYpc8eZ3hlxmeDCQecOr8nPNbQfKpnklMYNFdCJGDdiZqF7scCV8VbCVk7UiZJlIRTzmnfQYKOExj8WVMmPtb8mG81cYbqPx+f3Pj2SZsuRVxDpitFb/F1eCdwvVwdVIcpKf+iP9Ar5TfNc6GeX7I5/RoD7GS1wFSMGsdgtB/H3MjLYLF1TVdt1mZLtHZi1jFi+lwbw1AVMBsrZpo6fNfvUzHG7g7yoDsiGHBaFT4f88/A+T4G18qu2qPh2y5XEBXS+4YNMFghPlfDBVvh/IxKtTBrYdgUaNT5Jt47LysebCILrzIKZkbEaSOthVIgujgtmQ4aGVS6e0Bq7cMJwkvXesZogOyDoaDnQ8nw9bNodByHpvdmqDzCyjD82j//7juXbdXwFRvUzZFbZVlrYu2JXf6O56A4rKIjMC9LVxQbQgGdgS0oiKu8cuYYm3/R6/WQUOZ7Cs6wNS/MnR65klSVaHW3Wa7RV1NU8RAxvW/Msp1NdawQfcuCZJZfsRCagt8ehQ1uFwCBT3N+IRC4hc3osdcmWCApFtRD4lCzd/pr6BfomlS71voNsDfv8TxNVVW7E1bxfvwoFCR/Ip4mRp7MrKW8eLljTrzVQEIOXp8jpYmN9DO+nUL3lUDlsm8csa96dsA8kCtvbNHCa9qqO7jTStHZnZCigvM0hGafg30rMNV/x76vxdcH7ofjsEzokj72E1+bL3GfzHonwVokuf/ANLehLvU5/tFrcJe6Qi9QPwhK1nyzUHizo8E4ajFyZhB0DgZ00/yFhLu/FQsT8G8dG6BTN1gJoFo4ahaP0cha4Om7AI0jRQXTWMrjtOfTxRo02sesqXyjyFFFPye4rtYelVDMSysupJgaFBrJWjmvTJqIVufwBGTkiBwDvE7v8QolIcO4+c288IrdumtpoHuOUS3suVBcie0bzlO+PnZwiK8JnjbrusGKea7hGr5HlR2Ez1FxojhYA2G6xENOB+V1XS5vQO6l+qQsBA7RZGah1HhpluSqn3zpQz8AC0WfkhsYl8ULONkwduDNVoOMjgmWFItU77MuH7liyv8pcdqwDDfdWTVaZRuUHNoQBSsbLUaeTUzPlq+pMsIV5ZrfZYFjqvQ4XVo6uBHvKrlr4RPXExRFSxZPGzgipreOPjcZ4EjfA/Rr4Y2ZGTOci/I3OqnutsQHxh9Jcx01yPNLkSI3f88aFPZH+e7jaG2jde4nBJWpod1ps2FiQnG30ctR8oXKHuOgioRP2I9BsJFqXg6GvdMs57CNxrn9Muz4kTbWCN9IDGNjhuSq73NAjQ1I3kJNYMNqxuYgG6uu/BaFvKVBYgy2411qHMVSPtjUQFOEKXgErDKprhBrIILqRDS5mI+WxJyTOU6HaYZbLGRM9UJNjZSh6GJXAffAii8mDz/Vi/dM6se3M4fiJj6lBpmnUbZgH/BJ6zEzJcm1YhXaHJTEwoErzrpleN0HtmckpOucuM0iEC6gQ1W4FEm1Es+n/UM+8HeCupyXcYcrkmMS2lY7kGJQUneBd8AxSI8+1dYgrH3IxuAqS6JSu7ZMdgoBtoulAjakc3SYyMLY6WzVN6tzLimgFc9+CI/IiOrHE1hUS3lTn5Bc37Ka13cAQ5j1TTlJBlqBauDVyEIFTdHuE1fcu3ndQS5ANeMqGkYr2YOCkliQg5GexJ+yaVhm6kdZBc93ysTjP1aaOaZWt5I9Y7fuQ5FOuBcolcXjDH3/NpBI7vJhiKVSUTSutKaSRZu34vFjb19N5g5/CYhKLqaL4NgmuIx1+kH1m8xG04tTNooUXHgPjgvrDPOvwZt4i9nNyJaVv74Bku7bwSy2tbD1A373iuBxGl+bUunFAHcc63hjZ3hr1pBsLczoCUWE2cxuTdlvcu4QIDtW5OMqrNwJ3Q5Uh8XZU0RvSWOdzt4YTRKP2BA0HqnrNgx3aL6bpbF4fGa3Tt2mwpq1sgj44QrHXzZgy9HahCqPci7qOsd5ZEqq1PM7Ma74+wTJ6fPikGBHNxmKAMQ94j9eQ+9ygtdtr//88c763LzM4nd3OTZH3YB70UpyFlSPxp4/4TolxHTOQQSCtKjVpDkOshGImiG34bG4daxQHc/ly0+JmZ0qfHVKTFPKfKeCeQb41WOc+K9dk47JVi/kZp+BTxMoXq7yhGuBKebO1hQMZBVqdyuH90xchVrK5pyNfk0vmxFYJaPO3p7vEYtBf4wgjkLF0ULubV+wSqD3gjYjE26JgohEds/SOzQG2Sn7ntCVUBu4ikfETzu9Nq9TZe66jBMtNWW2k76hJzLWpaVuoWdLjVFRRh8lGYTu4Nbqa7XsXgftVbHc3Doq0F/0FCDm5ujai9inngqbXWJM+46T5vDIrR3jKBg2oVl+TevcdqtGrFmRqcP3CrEaLLDVDj/0PYN9n2V/RSEPQfOqY667wMXBFDRHl3nbuestG8mKph4GVSHDaYSRvYrP0KXH4EyElOWtfutuujJNXpZg3R/hB68czgSSc+XYn2GQniygDpHi9q8JvIoy6QJimQhX3bwIxK71flU49arVK2rSNGp/wFtM+qbfb0teaFi+ObGDdRTfEmPoAvy41VJbdaXOlC7d+yzKJuRSMHo9VIvWWHVM9sP19C+nWSwZx29lO3f+MTqGD/+VmUS/1",    
    "appname": "acd",
    "ogQuery": json.dumps({
        "app_name": app_name,
        "app_description": app_description,
        "target_language": language,
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
    


def create_referral_redeem_json(app_name, app_description, language):
    """
    Returns:
        dict: The JSON response from the API or error message.
    """
    api_url=DEX_URL
    payload = {
    "ask-dex":"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",    
    "appname": "acd",
    "ogQuery": json.dumps({
        "app_name": app_name,
        "app_description": app_description,
        "target_language": language,
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
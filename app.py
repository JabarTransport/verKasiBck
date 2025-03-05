import os
import logging
from flask import Flask, redirect, request, session, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Pastikan environment variables penting tidak kosong
required_env = [
    "FLASK_SECRET_KEY", "FRONTEND_URL", "FIREBASE_LOGIN_URL",
    "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "GITHUB_REDIRECT_URI", "SECRET_KEYWORD"
]

for env in required_env:
    if not os.getenv(env):
        raise EnvironmentError(f"Environment variable '{env}' is not set")

CORS(
    app,
    supports_credentials=True,
    origins=[
        os.getenv("FRONTEND_URL"),
        os.getenv("FIREBASE_LOGIN_URL")
    ],
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)

app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

# Konfigurasi dari Environment Variables
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")
SECRET_KEYWORD = os.getenv("SECRET_KEYWORD")

FRONTEND_URL = os.getenv("FRONTEND_URL")
FIREBASE_LOGIN_URL = os.getenv("FIREBASE_LOGIN_URL")

# Setup Logging
logging.basicConfig(level=logging.INFO)

@app.route("/check-keyword", methods=["POST"])
def check_keyword():
    data = request.get_json()
    if data and data.get("keyword") == SECRET_KEYWORD:
        session["keyword_valid"] = True
        return jsonify({"success": True})
    return jsonify({"error": "Invalid keyword"}), 401


@app.route("/auth/github")
def github_auth():
    if not session.get("keyword_valid"):
        return jsonify({"error": "Unauthorized"}), 401

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email"
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"https://github.com/login/oauth/authorize?{query_string}")


@app.route("/auth/github/callback")
def github_callback():
    code = request.args.get("code")
    if not code:
        return redirect(FIREBASE_LOGIN_URL)

    # Request access token from GitHub
    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI
        },
        headers={"Accept": "application/json"}
    )

    if token_response.status_code != 200:
        logging.error(f"Failed to fetch GitHub token: {token_response.text}")
        return redirect(FIREBASE_LOGIN_URL)

    access_token = token_response.json().get("access_token")
    if not access_token:
        logging.error("Access token is missing in GitHub response")
        return redirect(FIREBASE_LOGIN_URL)

    # Request user data from GitHub
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"}
    )

    if user_response.status_code != 200:
        logging.error(f"Failed to fetch GitHub user data: {user_response.text}")
        return redirect(FIREBASE_LOGIN_URL)

    user_data = user_response.json()
    session["user_data"] = {
        "name": user_data.get("name"),
        "avatar_url": user_data.get("avatar_url"),
        "html_url": user_data.get("html_url"),
        "login": user_data.get("login")
    }

    return redirect(FRONTEND_URL)


@app.route("/api/profile")
def get_profile():
    if "user_data" in session:
        return jsonify({
            "type": "github",
            "data": session["user_data"]
        })
    elif session.get("keyword_valid"):
        return jsonify({
            "type": "keyword",
            "data": {
                "name": "Guest User",
                "avatar_url": "https://via.placeholder.com/150",
                "message": "Logged in with secret keyword"
            }
        })
    return jsonify({"error": "Unauthorized"}), 401


@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

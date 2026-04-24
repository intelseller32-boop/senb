@app.route("/send", methods=["POST"])
def send():
    chat_id = request.form.get("chat_id")

    if not chat_id:
        return jsonify({"ok": False, "error": "chat_id missing"}), 400

    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # ---------- DEBUG LOG ----------
    logging.info(f"FORM DATA: {request.form.to_dict()}")
    logging.info(f"FILES: {list(request.files.keys())}")

    # ---------- TEXT MESSAGE ----------
    text_lines = [
        "📱 *New Submission*",
        f"🌐 IP: `{user_ip}`",
        ""
    ]

    # ✅ FIX: FORCE read all text fields properly
    form_dict = request.form.to_dict(flat=False)

    for key, values in form_dict.items():
        if key == "chat_id":
            continue

        for value in values:
            if value and str(value).strip():
                text_lines.append(f"*{key}:* {value}")

    # Also include report if exists
    report = request.form.get("report")
    if report:
        text_lines.append("")
        text_lines.append(report)

    # ---------- SEND TEXT ----------
    try:
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

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Text send error: {str(e)}"
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
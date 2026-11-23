"""Independent Cloud Run Pub/Sub notification relay."""
import base64
import binascii
import json
import os

import requests
from flask import Flask, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16_384


@app.post("/")
def notify():
    envelope = request.get_json(silent=True)
    try:
        encoded = envelope["message"]["data"]
        encoded += "=" * (-len(encoded) % 4)
        payload = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
        address = payload["emailAddress"]
        hint = payload["historyId"]
        if type(hint) is int:
            hint = str(hint)
        if not isinstance(address, str) or "@" not in address:
            raise ValueError("invalid emailAddress")
        if not isinstance(hint, str) or not hint.isascii() or not hint.isdecimal() or len(hint) > 30:
            raise ValueError("invalid historyId")
    except (TypeError, KeyError, ValueError, binascii.Error):
        app.logger.warning("Discarded malformed Gmail notification")
        return "", 204
    try:
        result = requests.post(
            os.environ["MAIL_HUB_NOTIFY_URL"],
            headers={"Authorization": f"Bearer {os.environ['MAIL_HUB_NOTIFY_TOKEN']}"},
            json={"version": 1, "email_address": address, "history_id": hint},
            timeout=(3, 8), allow_redirects=False,
        )
    except requests.RequestException:
        app.logger.warning("Mail hub notification delivery failed")
        return "", 503
    if not 200 <= result.status_code < 300:
        app.logger.warning("Mail hub rejected delivery with HTTP %s", result.status_code)
        return "", 503
    return "", 204

import base64
import json
import unittest
from unittest.mock import patch

from mail_hub_notify import app


class RelayTest(unittest.TestCase):
    def test_ack_depends_on_hub_acceptance(self):
        event = base64.urlsafe_b64encode(json.dumps({
            "emailAddress": "test@example.invalid", "historyId": "123"
        }).encode()).decode()
        env = {"MAIL_HUB_NOTIFY_URL": "https://example.invalid/v1/notifications",
               "MAIL_HUB_NOTIFY_TOKEN": "test"}
        with patch.dict("os.environ", env), patch("mail_hub_notify.requests.post") as send:
            client = app.test_client()
            send.return_value.status_code = 503
            self.assertEqual(client.post("/", json={"message": {"data": event}}).status_code, 503)
            send.return_value.status_code = 204
            self.assertEqual(client.post("/", json={"message": {"data": event}}).status_code, 204)
            self.assertEqual(send.call_args.kwargs["json"], {
                "version": 1, "email_address": "test@example.invalid", "history_id": "123",
            })
            self.assertEqual(client.post("/", json={"message": {"data": "invalid"}}).status_code, 204)
            self.assertEqual(send.call_count, 2)

    def test_numeric_history_id_matches_real_gmail_push(self):
        event = base64.urlsafe_b64encode(json.dumps({
            "emailAddress": "test@example.invalid", "historyId": 123
        }).encode()).decode()
        env = {"MAIL_HUB_NOTIFY_URL": "https://example.invalid/v1/notifications",
               "MAIL_HUB_NOTIFY_TOKEN": "test"}
        with patch.dict("os.environ", env), patch("mail_hub_notify.requests.post") as send:
            send.return_value.status_code = 204
            response = app.test_client().post("/", json={"message": {"data": event}})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(send.call_args.kwargs["json"]["history_id"], "123")

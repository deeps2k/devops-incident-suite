import os
import requests


def send_slack_message(message: str):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        return {"status": "skipped", "reason": "SLACK_WEBHOOK_URL not configured"}

    response = requests.post(webhook_url, json={"text": message}, timeout=10)
    return {"status": "sent", "status_code": response.status_code}

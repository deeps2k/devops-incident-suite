import os
import requests
from requests.auth import HTTPBasicAuth


def create_jira_ticket(summary: str, description: str, priority: str = "High"):
    base_url = os.getenv("JIRA_BASE_URL", "")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project_key = os.getenv("JIRA_PROJECT_KEY", "")

    if not all([base_url, email, token, project_key]):
        return {"status": "skipped", "reason": "JIRA settings not configured"}

    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"text": description, "type": "text"}]}],
            },
            "issuetype": {"name": "Task"},
        }
    }
    response = requests.post(url, json=payload, auth=HTTPBasicAuth(email, token), timeout=15)
    return {"status": "created", "status_code": response.status_code, "response": response.text[:500]}

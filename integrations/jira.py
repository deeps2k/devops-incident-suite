import json
import os
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


def _jira_auth() -> tuple[str, str, str] | tuple[None, None, None]:
    base_url = os.getenv("JIRA_BASE_URL", "").strip()
    email = os.getenv("JIRA_EMAIL", "").strip()
    token = os.getenv("JIRA_API_TOKEN", "").strip()
    if not all([base_url, email, token]):
        return None, None, None
    return base_url.rstrip("/"), email, token


def _auth():
    base_url, email, token = _jira_auth()
    if not base_url:
        return None
    return HTTPBasicAuth(email, token)


def adf_to_plain_text(node: Any) -> str:
    """Extract plain text from Jira Cloud ADF (Atlassian Document Format)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(adf_to_plain_text(x) for x in node).strip()

    if not isinstance(node, dict):
        return ""

    parts: list[str] = []
    if node.get("type") == "text":
        text = node.get("text", "")
        if text:
            parts.append(text)

    for child in node.get("content", []) or []:
        t = adf_to_plain_text(child)
        if t:
            parts.append(t)

    if node.get("type") == "paragraph":
        return " ".join(parts)
    if node.get("type") in ("heading", "blockquote"):
        return " ".join(parts)

    return "\n".join(parts) if parts else ""


def create_jira_ticket(summary: str, description: str, priority: str = "High"):
    base_url, email, token = _jira_auth()
    project_key = os.getenv("JIRA_PROJECT_KEY", "").strip()

    if not all([base_url, email, token, project_key]):
        return {"status": "skipped", "reason": "JIRA settings not configured"}

    url = f"{base_url}/rest/api/3/issue"
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
    try:
        response = requests.post(url, json=payload, auth=HTTPBasicAuth(email, token), timeout=15)
        out: dict[str, Any] = {
            "status": "created" if response.status_code in (200, 201) else "error",
            "status_code": response.status_code,
            "response": response.text[:500],
        }
        if response.status_code in (200, 201):
            try:
                data = response.json()
                out["issue_key"] = data.get("key")
                out["issue_id"] = data.get("id")
            except (json.JSONDecodeError, TypeError):
                pass
        return out
    except requests.RequestException as exc:
        return {"status": "error", "reason": str(exc)}


def search_issues_jql(jql: str, max_results: int = 50, fields: list[str] | None = None) -> dict[str, Any]:
    """
    POST /rest/api/3/search/jql — enhanced JQL search (Jira Cloud).

    Legacy POST /rest/api/3/search returns HTTP 410 on current Cloud sites
    (see Atlassian CHANGE-2046); this uses the replacement endpoint.
    """
    base_url, _, _ = _jira_auth()
    auth = _auth()
    if not base_url or not auth:
        return {"error": "JIRA settings not configured"}

    url = f"{base_url}/rest/api/3/search/jql"
    body = {
        "jql": jql,
        "maxResults": max_results,
        "fields": fields or ["key", "summary", "updated"],
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=body, auth=auth, headers=headers, timeout=30)
        if response.status_code != 200:
            return {
                "error": f"HTTP {response.status_code}",
                "detail": response.text[:800],
            }
        return response.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}


def get_issue_for_kb(issue_key: str) -> dict[str, Any]:
    """Fetch issue fields needed to build resolution text and KB metadata."""
    base_url, _, _ = _jira_auth()
    auth = _auth()
    if not base_url or not auth:
        return {"error": "JIRA settings not configured"}

    fields = [
        "summary",
        "description",
        "comment",
        "resolution",
        "status",
        "labels",
        "issuetype",
        "updated",
    ]
    url = f"{base_url}/rest/api/3/issue/{issue_key}"
    params = {"fields": ",".join(fields)}
    try:
        response = requests.get(url, params=params, auth=auth, timeout=30)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "detail": response.text[:800]}
        return response.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}


def format_issue_and_comments_for_prompt(issue_payload: dict[str, Any]) -> str:
    """Flatten description + comments into plain text for LLM summarization."""
    if "error" in issue_payload and "fields" not in issue_payload:
        return ""

    fields = issue_payload.get("fields") or {}
    summary = fields.get("summary") or ""

    desc = fields.get("description")
    desc_text = adf_to_plain_text(desc) if desc else ""

    resolution = fields.get("resolution") or {}
    res_name = resolution.get("name") if isinstance(resolution, dict) else ""

    status = (fields.get("status") or {}).get("name", "")
    labels = fields.get("labels") or []
    issue_type = (fields.get("issuetype") or {}).get("name", "")

    lines = [
        f"Summary: {summary}",
        f"Issue type: {issue_type}",
        f"Status: {status}",
        f"Resolution: {res_name}" if res_name else "Resolution: (none)",
    ]
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")
    lines.append("")
    lines.append("Description:")
    lines.append(desc_text or "(empty)")
    lines.append("")
    lines.append("Comments (chronological):")

    comment_block = fields.get("comment") or {}
    comments = comment_block.get("comments") or []
    if not comments:
        lines.append("(no comments)")
    else:
        for c in sorted(comments, key=lambda x: x.get("created", "")):
            author = ((c.get("author") or {}).get("displayName")) or "unknown"
            created = c.get("created", "")
            body = c.get("body")
            body_text = adf_to_plain_text(body) if body else ""
            lines.append(f"--- {author} @ {created}")
            lines.append(body_text or "(empty)")

    return "\n".join(lines)

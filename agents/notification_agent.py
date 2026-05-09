from typing import Dict, Any
from integrations.slack import send_slack_message
from integrations.jira import create_jira_ticket


def notify_and_ticket(state: Dict[str, Any]) -> Dict[str, Any]:
    classification = state.get("classification", {})
    runbook = state.get("runbook", "")
    incident_type = classification.get("incident_type", "Unknown Incident")
    priority = classification.get("priority", "P3")

    summary = f"{priority}: {incident_type}"
    slack_message = f"*DevOps Incident Detected*\n{summary}\n\n{classification.get('reason', '')}\n\nRunbook generated in app output."

    slack_result = send_slack_message(slack_message)

    jira_result = {"status": "skipped", "reason": "Only P1/P2 incidents create JIRA tickets by default"}
    if priority in ["P1", "P2"]:
        jira_result = create_jira_ticket(summary=summary, description=runbook, priority="High")

    final_summary = f"Detected {incident_type} with priority {priority}. Generated remediation and runbook."

    return {
        **state,
        "slack_result": slack_result,
        "jira_result": jira_result,
        "final_summary": final_summary,
    }

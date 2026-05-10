from typing import TypedDict, List, Dict, Any

class IncidentState(TypedDict, total=False):
    raw_logs: str
    parsed_events: List[Dict[str, Any]]
    classification: Dict[str, Any]
    remediation: Dict[str, Any]
    rag_context: List[Dict[str, Any]]
    runbook: str
    slack_result: Dict[str, Any]
    jira_result: Dict[str, Any]
    final_summary: str

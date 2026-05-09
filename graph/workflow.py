from langgraph.graph import StateGraph, END
from state import IncidentState
from agents.log_agent import parse_logs
from agents.classifier_agent import classify_incident
from agents.remediation_agent import recommend_remediation
from agents.runbook_agent import generate_runbook
from agents.notification_agent import notify_and_ticket


def build_incident_graph():
    workflow = StateGraph(IncidentState)

    workflow.add_node("parse_logs", parse_logs)
    workflow.add_node("classify_incident", classify_incident)
    workflow.add_node("recommend_remediation", recommend_remediation)
    workflow.add_node("generate_runbook", generate_runbook)
    workflow.add_node("notify_and_ticket", notify_and_ticket)

    workflow.set_entry_point("parse_logs")
    workflow.add_edge("parse_logs", "classify_incident")
    workflow.add_edge("classify_incident", "recommend_remediation")
    workflow.add_edge("recommend_remediation", "generate_runbook")
    workflow.add_edge("generate_runbook", "notify_and_ticket")
    workflow.add_edge("notify_and_ticket", END)

    return workflow.compile()

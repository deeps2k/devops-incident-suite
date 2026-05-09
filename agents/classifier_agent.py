from typing import Dict, Any
from utils.llm import get_llm


def classify_incident(state: Dict[str, Any]) -> Dict[str, Any]:
    events = state.get("parsed_events", [])

    # Use full parsed event content, not only message.
    # This helps classifier see service, severity, environment, etc.
    text = "\n".join([str(e) for e in events])

    fallback = {
        "incident_type": "Unknown Incident",
        "priority": "P3",
        "confidence": 60,
        "reason": "Could not confidently classify incident.",
    }

    lowered = text.lower()

    db_keywords = ["database", "db", "sql", "postgres", "mysql", "oracle", "connection pool"]
    timeout_keywords = ["timeout", "timed out", "latency", "slow query"]

    if "crashloopbackoff" in lowered or "missing environment variable" in lowered:
        fallback = {
            "incident_type": "Kubernetes CrashLoopBackOff",
            "priority": "P1",
            "confidence": 92,
            "reason": "Logs show pod restarts or missing environment variable.",
        }

    elif any(k in lowered for k in db_keywords) and any(k in lowered for k in timeout_keywords):
        fallback = {
            "incident_type": "Database Timeout / Connection Pool Exhaustion",
            "priority": "P1",
            "confidence": 90,
            "reason": "Logs show timeout while calling a database dependency.",
        }

    elif "401" in lowered or "unauthorized" in lowered or "authentication failed" in lowered:
        fallback = {
            "incident_type": "Authentication Failure",
            "priority": "P2",
            "confidence": 85,
            "reason": "Logs show authentication or authorization failure.",
        }

    elif "500" in lowered or "internal server error" in lowered:
        fallback = {
            "incident_type": "Application Server Error",
            "priority": "P2",
            "confidence": 82,
            "reason": "Logs show HTTP 500 or internal server error.",
        }

    elif "outofmemory" in lowered or "oomkilled" in lowered or "memory" in lowered:
        fallback = {
            "incident_type": "Memory Pressure / OOMKilled",
            "priority": "P1",
            "confidence": 88,
            "reason": "Logs show memory pressure or out-of-memory failure.",
        }

    llm = get_llm()
    if not llm:
        return {**state, "classification": fallback}

    prompt = f"""
You are a DevOps incident classifier.

Classify the incident from these logs.

Return only concise JSON-like text with:
- incident_type
- priority
- confidence
- reason
- probable_root_cause

Logs:
{text}
"""

    try:
        result = llm.invoke(prompt).content
        return {**state, "classification": {**fallback, "llm_analysis": result}}
    except Exception as exc:
        return {**state, "classification": {**fallback, "llm_error": str(exc)}}
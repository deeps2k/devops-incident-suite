"""Keyword-based incident classification used before / alongside the LLM."""

from typing import Any, Dict


def keyword_classification(log_text: str) -> Dict[str, Any]:
    """
    Return a conservative classification from log content when the LLM is off
    or as a seed for RAG + structured model output.
    """
    fallback: Dict[str, Any] = {
        "incident_type": "Unknown Incident",
        "priority": "P3",
        "confidence": 60,
        "reason": "Could not confidently classify incident.",
    }

    lowered = log_text.lower()

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

    return fallback

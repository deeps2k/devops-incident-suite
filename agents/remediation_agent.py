from typing import Dict, Any
from utils.llm import get_llm

REMEDIATION_LIBRARY = {
    "Kubernetes CrashLoopBackOff": [
        "Check pod logs using kubectl logs <pod-name> -n <namespace>.",
        "Run kubectl describe pod <pod-name> -n <namespace> to inspect events.",
        "Verify required environment variables and Kubernetes Secrets.",
        "Check deployment YAML for missing configMapKeyRef or secretKeyRef values.",
        "Validate readiness/liveness probes.",
        "Restart deployment after fixing configuration.",
    ],

    "Database Timeout / Connection Pool Exhaustion": [
        "Check database availability and network connectivity.",
        "Verify application can reach the database endpoint.",
        "Review connection pool max size, active connections, and idle connections.",
        "Look for slow queries, deadlocks, and lock contention.",
        "Check recent traffic spikes or deployment changes.",
        "Scale database or app replicas if traffic spike is confirmed.",
        "Add retry/backoff logic if transient failures are common.",
    ],

    "Authentication Failure": [
        "Check if credentials, API tokens, or certificates recently changed.",
        "Verify OAuth/JWT configuration and token expiration.",
        "Check identity provider availability.",
        "Review permission or role changes.",
        "Confirm the service account has required access.",
    ],

    "Application Server Error": [
        "Check application stack trace around the error timestamp.",
        "Review recent deployments or code changes.",
        "Verify dependency health such as database, cache, and external APIs.",
        "Check application configuration and environment variables.",
        "Rollback the latest deployment if errors started after release.",
    ],

    "Memory Pressure / OOMKilled": [
        "Check container memory usage and limits.",
        "Run kubectl describe pod <pod-name> to confirm OOMKilled reason.",
        "Review recent traffic spikes or memory-heavy code paths.",
        "Increase memory requests/limits if needed.",
        "Check for memory leaks using application metrics or heap dumps.",
        "Scale replicas if workload increased.",
    ],
}


def recommend_remediation(state: Dict[str, Any]) -> Dict[str, Any]:
    classification = state.get("classification", {})
    incident_type = classification.get("incident_type", "Unknown Incident")
    steps = REMEDIATION_LIBRARY.get(incident_type, [
        "Review recent deployments and configuration changes.",
        "Check application logs, infrastructure metrics, and dependency health.",
        "Escalate to service owner if issue is customer-impacting.",
    ])

    remediation = {
        "recommended_steps": steps,
        "rationale": classification.get("reason", "Based on parsed logs and incident classification."),
    }

    llm = get_llm()
    if llm:
        prompt = f"""
Create a practical DevOps remediation plan for this incident.
Incident: {incident_type}
Reason: {classification.get('reason')}
Parsed events: {state.get('parsed_events')}
Keep it concise and actionable.
"""
        try:
            remediation["llm_plan"] = llm.invoke(prompt).content
        except Exception as exc:
            remediation["llm_error"] = str(exc)

    return {**state, "remediation": remediation}

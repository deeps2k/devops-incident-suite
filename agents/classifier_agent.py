from typing import Dict, Any

from agents.heuristics import keyword_classification
from utils.llm import get_llm


def classify_incident(state: Dict[str, Any]) -> Dict[str, Any]:
    events = state.get("parsed_events", [])

    # Use full parsed event content, not only message.
    # This helps classifier see service, severity, environment, etc.
    text = "\n".join([str(e) for e in events])

    fallback = keyword_classification(text)

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
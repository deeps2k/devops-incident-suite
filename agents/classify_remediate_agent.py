import json
import os
import re
from typing import Any, Dict

from knowledge.vector_store import search_similar
from utils.llm import get_llm

from agents.heuristics import keyword_classification
from agents.remediation_agent import (
    FALLBACK_REMEDIATION_STEPS,
    REMEDIATION_LIBRARY,
    build_rag_query,
)


def _parse_llm_json(content: str) -> Dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return json.loads(text)


def _coerce_confidence(raw: Any, default: int) -> int:
    try:
        n = int(float(raw))
        return max(0, min(100, n))
    except (TypeError, ValueError):
        return default


def classify_and_remediate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    One LLM call for classification + remediation. RAG runs first using keyword
    seed classification so retrieval stays aligned with logs.
    """
    events = state.get("parsed_events", [])
    text = "\n".join(str(e) for e in events)

    fallback = keyword_classification(text)

    rag_query = build_rag_query(state, fallback)
    rag_hits = search_similar(rag_query, k=int(os.getenv("RAG_TOP_K", "5"))) if rag_query else []
    rag_context = [
        {
            "issue_key": (h.get("metadata") or {}).get("issue_key", ""),
            "summary": (h.get("metadata") or {}).get("summary", ""),
            "excerpt": (h.get("document") or "")[:1200],
            "distance": h.get("distance"),
        }
        for h in rag_hits
    ]

    incident_type_seed = fallback["incident_type"]
    library_steps = REMEDIATION_LIBRARY.get(incident_type_seed, FALLBACK_REMEDIATION_STEPS)

    base_remediation: Dict[str, Any] = {
        "recommended_steps": list(library_steps),
        "rationale": fallback.get("reason", "Based on parsed logs and incident classification."),
        "rag_hits": rag_context,
    }

    llm = get_llm()
    if not llm:
        return {
            **state,
            "classification": fallback,
            "remediation": base_remediation,
            "rag_context": rag_context,
        }

    rag_block = ""
    if rag_context:
        rag_block = "\n\nSimilar past resolutions from our knowledge base (prefer aligning with these when relevant):\n"
        for i, hit in enumerate(rag_context, 1):
            rag_block += f"\n--- KB {i} ({hit.get('issue_key') or 'unknown'}) ---\n{hit.get('excerpt', '')}\n"

    prompt = f"""You are a DevOps incident analyst. Classify the incident and produce remediation guidance in one response.

Return ONLY valid JSON (no markdown fences) with exactly these keys:
- incident_type (string)
- priority (string: P1, P2, or P3)
- confidence (integer 0-100)
- reason (string, short)
- probable_root_cause (string)
- recommended_steps (array of strings, ordered actionable steps)
- remediation_plan (string: concise narrative; cite KB issue keys like PROJ-123 when excerpts apply)

Logs:
{text}
{rag_block}
"""

    try:
        raw = llm.invoke(prompt).content
        parsed = _parse_llm_json(raw)
    except Exception as exc:
        return {
            **state,
            "classification": {**fallback, "llm_error": str(exc)},
            "remediation": {**base_remediation, "llm_error": str(exc)},
            "rag_context": rag_context,
        }

    it = (parsed.get("incident_type") or "").strip() or fallback["incident_type"]
    pr = (parsed.get("priority") or "").strip().upper()
    if pr not in ("P1", "P2", "P3"):
        pr = str(fallback.get("priority", "P3"))

    classification: Dict[str, Any] = {
        "incident_type": it,
        "priority": pr,
        "confidence": _coerce_confidence(parsed.get("confidence"), int(fallback.get("confidence", 60))),
        "reason": (parsed.get("reason") or "").strip() or fallback["reason"],
        "probable_root_cause": (parsed.get("probable_root_cause") or "").strip(),
    }

    steps_raw = parsed.get("recommended_steps")
    steps: list[str] = []
    if isinstance(steps_raw, list):
        steps = [str(s).strip() for s in steps_raw if str(s).strip()]
    if not steps:
        steps = list(
            REMEDIATION_LIBRARY.get(classification["incident_type"], FALLBACK_REMEDIATION_STEPS)
        )

    plan = parsed.get("remediation_plan")
    remediation: Dict[str, Any] = {
        "recommended_steps": steps,
        "rationale": classification.get("reason", ""),
        "rag_hits": rag_context,
    }
    if plan is not None and str(plan).strip():
        remediation["llm_plan"] = str(plan).strip()

    return {**state, "classification": classification, "remediation": remediation, "rag_context": rag_context}

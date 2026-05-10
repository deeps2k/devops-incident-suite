from typing import Any, Dict, List


def _format_rag_section(hits: List[Dict[str, Any]], excerpt_max: int = 500) -> str:
    if not hits:
        return ""
    lines = ["\n## Related knowledge base (RAG)\n"]
    lines.append(
        "Past tickets and notes retrieved for this incident (use as secondary validation; "
        "prefer current architecture and these resolution steps first).\n"
    )
    for i, hit in enumerate(hits, 1):
        key = (hit.get("issue_key") or "").strip() or "unknown"
        summary = (hit.get("summary") or "").strip()
        excerpt = (hit.get("excerpt") or "").strip().replace("\r\n", "\n")
        if len(excerpt) > excerpt_max:
            excerpt = excerpt[: excerpt_max - 3] + "..."
        dist = hit.get("distance")
        meta = f" (similarity distance: {dist:.4f})" if isinstance(dist, (int, float)) else ""
        lines.append(f"### {i}. {key}{meta}\n")
        if summary:
            lines.append(f"**Summary:** {summary}\n\n")
        if excerpt:
            lines.append(f"{excerpt}\n\n")
    return "".join(lines)


def generate_runbook(state: Dict[str, Any]) -> Dict[str, Any]:
    classification = state.get("classification", {})
    remediation = state.get("remediation", {})
    incident_type = classification.get("incident_type", "Unknown Incident")
    steps = remediation.get("recommended_steps", [])

    rag_hits: List[Dict[str, Any]] = list(
        state.get("rag_context") or remediation.get("rag_hits") or []
    )
    llm_plan = (remediation.get("llm_plan") or "").strip()
    probable_root = (classification.get("probable_root_cause") or "").strip()

    runbook = f"""# {incident_type} Runbook

## Priority
{classification.get('priority', 'P3')}

## Symptoms
- Detected from uploaded operational logs
- Classification confidence: {classification.get('confidence', 'N/A')}%

## Probable Cause
{classification.get('reason', 'Unknown')}
"""
    if probable_root:
        runbook += f"\n**Root-cause notes:** {probable_root}\n"

    if llm_plan:
        runbook += f"""
## Remediation narrative (model + KB context)
{llm_plan}

"""

    runbook += "## Resolution Steps\n"
    for i, step in enumerate(steps, 1):
        runbook += f"{i}. {step}\n"

    runbook += _format_rag_section(rag_hits)

    runbook += """
## Validation
1. Confirm service health endpoint is responding.
2. Confirm error rate is reduced.
3. Confirm no new critical logs are generated.
4. Update incident ticket with closure notes.

## Prevention
- Add monitoring alert for similar pattern.
- Add deployment validation checks.
- Convert this runbook into a reusable knowledge article.
"""
    return {**state, "runbook": runbook}

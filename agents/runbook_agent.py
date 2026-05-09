from typing import Dict, Any


def generate_runbook(state: Dict[str, Any]) -> Dict[str, Any]:
    classification = state.get("classification", {})
    remediation = state.get("remediation", {})
    incident_type = classification.get("incident_type", "Unknown Incident")
    steps = remediation.get("recommended_steps", [])

    runbook = f"""# {incident_type} Runbook

## Priority
{classification.get('priority', 'P3')}

## Symptoms
- Detected from uploaded operational logs
- Classification confidence: {classification.get('confidence', 'N/A')}%

## Probable Cause
{classification.get('reason', 'Unknown')}

## Resolution Steps
"""
    for i, step in enumerate(steps, 1):
        runbook += f"{i}. {step}\n"

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

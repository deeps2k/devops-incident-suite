import json

import gradio as gr
from dotenv import load_dotenv
from graph.workflow import build_incident_graph
from utils.log_anonymization import anonymize_logs

load_dotenv()
app_graph = build_incident_graph()


def _format_integration_status(result: dict) -> str:
    slack = result.get("slack_result") or {}
    jira = result.get("jira_result") or {}
    lines: list[str] = []

    lines.append("Slack")
    lines.append(f"  status: {slack.get('status', '—')}")
    if slack.get("reason"):
        lines.append(f"  detail: {slack['reason']}")
    if slack.get("status_code") is not None:
        lines.append(f"  http_status: {slack['status_code']}")

    lines.append("")
    lines.append("Jira")
    lines.append(f"  status: {jira.get('status', '—')}")
    if jira.get("reason"):
        lines.append(f"  detail: {jira['reason']}")
    if jira.get("status_code") is not None:
        lines.append(f"  http_status: {jira['status_code']}")
    if jira.get("response"):
        lines.append(f"  api_response_preview: {jira['response']}")

    return "\n".join(lines)


def analyze_logs(log_text, log_file):
    if log_file is not None:
        with open(log_file.name, "r", encoding="utf-8", errors="ignore") as f:
            raw_logs = f.read()
    else:
        raw_logs = log_text or ""

    if not raw_logs.strip():
        return "Please paste logs or upload a .log/.txt file.", "", "{}", ""

    try:
        anon = anonymize_logs(raw_logs)
    except RuntimeError as exc:
        return f"**Anonymization error**\n\n{exc}", "", "{}", ""

    result = app_graph.invoke({"raw_logs": anon.text})

    classification = result.get("classification", {})
    remediation = result.get("remediation", {})
    runbook = result.get("runbook", "")

    summary = f"""## Incident Summary

*{anon.summary_line()}*

**Incident Type:** {classification.get('incident_type')}

**Priority:** {classification.get('priority')}

**Confidence:** {classification.get('confidence')}%

**Reason:** {classification.get('reason')}

## Recommended Steps
"""
    for step in remediation.get("recommended_steps", []):
        summary += f"- {step}\n"

    debug_payload = {
        **result,
        "_anonymization": {
            "summary": anon.summary_line(),
            "entity_count": anon.entity_count,
            "entity_types": anon.entity_types,
            "chunks_processed": anon.chunks_processed,
            "skipped": anon.skipped,
            "skip_reason": anon.skip_reason,
        },
    }
    debug_json = json.dumps(debug_payload, indent=2, default=str)
    integration_text = _format_integration_status(result)
    return summary, runbook, debug_json, integration_text


with gr.Blocks(title="Multi-Agent DevOps Incident Analysis Suite") as demo:
    gr.Markdown("# Multi-Agent DevOps Incident Analysis Suite")
    gr.Markdown(
        "Upload or paste DevOps logs. Text is **anonymized with Presidio** (PII redaction) before analysis. "
        "Set `PRESIDIO_DISABLE=true` to bypass (not recommended for production)."
    )

    with gr.Row():
        log_text = gr.Textbox(label="Paste Logs", lines=14, placeholder="Paste Kubernetes, app, or infrastructure logs here...")
        log_file = gr.File(label="Upload Log File", file_types=[".log", ".txt"])

    analyze_btn = gr.Button("Analyze Incident")

    summary_output = gr.Markdown(label="Summary")
    runbook_output = gr.Markdown(label="Generated Runbook")
    integration_status = gr.Textbox(
        label="Slack & Jira status",
        lines=12,
        interactive=False,
        placeholder="Shown after analysis (read-only).",
    )
    debug_output = gr.Code(label="Full Agent State", language="json")

    analyze_btn.click(
        analyze_logs,
        inputs=[log_text, log_file],
        outputs=[summary_output, runbook_output, debug_output, integration_status],
    )

if __name__ == "__main__":
    demo.launch(show_error=True, ssr_mode=False)

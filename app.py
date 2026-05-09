import json
import gradio as gr
from dotenv import load_dotenv
from graph.workflow import build_incident_graph

load_dotenv()
app_graph = build_incident_graph()


def analyze_logs(log_text, log_file):
    if log_file is not None:
        with open(log_file.name, "r", encoding="utf-8", errors="ignore") as f:
            raw_logs = f.read()
    else:
        raw_logs = log_text or ""

    if not raw_logs.strip():
        return "Please paste logs or upload a .log/.txt file.", "", "{}"

    result = app_graph.invoke({"raw_logs": raw_logs})

    classification = result.get("classification", {})
    remediation = result.get("remediation", {})
    runbook = result.get("runbook", "")

    summary = f"""## Incident Summary

**Incident Type:** {classification.get('incident_type')}

**Priority:** {classification.get('priority')}

**Confidence:** {classification.get('confidence')}%

**Reason:** {classification.get('reason')}

## Recommended Steps
"""
    for step in remediation.get("recommended_steps", []):
        summary += f"- {step}\n"

    debug_json = json.dumps(result, indent=2, default=str)
    return summary, runbook, debug_json


with gr.Blocks(title="Multi-Agent DevOps Incident Analysis Suite") as demo:
    gr.Markdown("# Multi-Agent DevOps Incident Analysis Suite")
    gr.Markdown("Upload or paste DevOps logs. LangGraph coordinates agents for parsing, classification, remediation, runbook generation, Slack, and JIRA.")

    with gr.Row():
        log_text = gr.Textbox(label="Paste Logs", lines=14, placeholder="Paste Kubernetes, app, or infrastructure logs here...")
        log_file = gr.File(label="Upload Log File", file_types=[".log", ".txt"])

    analyze_btn = gr.Button("Analyze Incident")

    summary_output = gr.Markdown(label="Summary")
    runbook_output = gr.Markdown(label="Generated Runbook")
    debug_output = gr.Code(label="Full Agent State", language="json")

    analyze_btn.click(analyze_logs, inputs=[log_text, log_file], outputs=[summary_output, runbook_output, debug_output])

if __name__ == "__main__":
    demo.launch(share=True)

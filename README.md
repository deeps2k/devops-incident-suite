---
title: DevOps Incident Suite
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: "5.29.0"
python_version: "3.11"
app_file: app.py
pinned: false
---

# Multi-Agent DevOps Incident Analysis Suite

A VS Code-ready GenAI project that uses **LangChain + LangGraph** to analyze DevOps logs and generate remediation guidance, runbooks, Slack notifications, and JIRA tickets.

## What This Project Demonstrates

- Multi-agent architecture
- LangGraph orchestration
- LangChain LLM usage
- DevOps/SRE log analysis
- Automated incident classification
- Remediation recommendation
- Runbook generation
- Optional Slack and JIRA integration
- Gradio UI

## Agent Flow

```text
User uploads logs
   ↓
Log Parser Agent
   ↓
Incident Classification Agent
   ↓
Remediation Agent
   ↓
Runbook Generator Agent
   ↓
Slack/JIRA Notification Agent
```

## Project Structure

```text
devops_incident_vscode/
├── agents/
│   ├── log_agent.py
│   ├── classifier_agent.py
│   ├── remediation_agent.py
│   ├── runbook_agent.py
│   └── notification_agent.py
├── graph/
│   └── workflow.py
├── integrations/
│   ├── slack.py
│   └── jira.py
├── utils/
│   └── llm.py
├── data/sample_logs/
├── app.py
├── state.py
├── requirements.txt
├── .env.example
└── README.md
```

## Setup in VS Code on Windows

### 1. Open folder in VS Code

Open the `devops_incident_vscode` folder.

### 2. Create virtual environment

```powershell
py -m venv .venv
```

### 3. Activate virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 5. Configure environment

Copy `.env.example` to `.env`.

```powershell
copy .env.example .env
```

Add your OpenRouter key:

```env
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
```

The app also works without an API key using fallback rule-based classification.

### 6. Run the app

```powershell
py app.py
```

Open the local URL shown in the terminal, usually:

```text
http://127.0.0.1:7860
```

## Run in Google Colab

Upload the project folder or zip file, then run:

```python
!pip install -r requirements.txt
!python app.py
```

For public Colab link, change the last line in `app.py` from:

```python
demo.launch()
```

to:

```python
demo.launch(share=True)
```

## Deploy to Hugging Face Spaces

1. Create a new Hugging Face Space
2. Select **Gradio** as SDK
3. Upload all project files
4. Add secrets in Space settings:
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `LLM_MODEL`
   - optional Slack/JIRA values
5. Hugging Face will install `requirements.txt` and run `app.py`

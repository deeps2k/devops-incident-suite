import re
from typing import Dict, Any


def parse_logs(state: Dict[str, Any]) -> Dict[str, Any]:
    raw_logs = state.get("raw_logs", "").strip()

    if not raw_logs:
        return {**state, "parsed_events": []}

    lines = [line.strip() for line in raw_logs.splitlines() if line.strip()]

    timestamp = "unknown"
    service = "unknown"
    environment = "unknown"
    severity = "UNKNOWN"
    message_lines = []

    timestamp_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    severity_pattern = r"\b(ERROR|WARN|WARNING|INFO|DEBUG|CRITICAL)\b"

    for line in lines:
        # timestamp
        if re.search(timestamp_pattern, line):
            match = re.search(r"\d{4}-\d{2}-\d{2}T[^\s]+", line)
            if match:
                timestamp = match.group(0)

        # severity
        sev_match = re.search(severity_pattern, line, re.I)
        if sev_match:
            severity = sev_match.group(1).upper()
            if severity == "WARNING":
                severity = "WARN"

        # service from [backend-api-02]
        bracket_service = re.search(r"\[([\w-]+)\]", line)
        if bracket_service:
            service = bracket_service.group(1)

        # service from service=backend-api-02
        service_match = re.search(r"service=([\w-]+)", line)
        if service_match:
            service = service_match.group(1)

        # standalone service line
        if service == "unknown" and re.match(r"^[a-zA-Z][\w-]*-\d+$", line):
            service = line

        # environment
        if line.lower() in ["dev", "qa", "test", "stage", "staging", "prod", "production"]:
            environment = line.lower()

        # message
        message_match = re.search(r'message="([^"]+)"', line)
        if message_match:
            message_lines.append(message_match.group(1))
        elif any(keyword in line.lower() for keyword in [
            "error", "timeout", "exception", "failed", "failure",
            "crashloopbackoff", "oomkilled", "unauthorized", "connection"
        ]):
            message_lines.append(line)

    message = "\n".join(message_lines) if message_lines else raw_logs

    event = {
        "timestamp": timestamp,
        "severity": severity,
        "service": service,
        "environment": environment,
        "message": message,
        "raw": raw_logs,
    }

    return {**state, "parsed_events": [event]}
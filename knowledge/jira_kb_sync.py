import json
import os
from pathlib import Path

from dotenv import load_dotenv

from integrations.jira import (
    format_issue_and_comments_for_prompt,
    get_issue_for_kb,
    search_issues_jql,
)
from knowledge.vector_store import upsert_resolution_document
from utils.llm import get_llm

load_dotenv()

_PROCESSED_PATH = Path(os.getenv("JIRA_KB_PROCESSED_FILE", os.path.join("data", "jira_kb_processed.json")))


def _load_processed_keys() -> set[str]:
    if not _PROCESSED_PATH.exists():
        return set()
    try:
        data = json.loads(_PROCESSED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def _save_processed_keys(keys: set[str]) -> None:
    _PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROCESSED_PATH.write_text(json.dumps(sorted(keys), indent=2), encoding="utf-8")


def default_closed_jql(days: int) -> str | None:
    project = os.getenv("JIRA_PROJECT_KEY", "").strip()
    custom = os.getenv("JIRA_JQL_CLOSED", "").strip()
    if custom:
        return custom
    if not project:
        return None
    return (
        f'project = {project} AND statusCategory = Done '
        f"AND updated >= -{days}d ORDER BY updated DESC"
    )


def summarize_resolution_with_llm(issue_key: str, flat_context: str) -> str | None:
    llm = get_llm()
    if not llm or not flat_context.strip():
        return None

    prompt = f"""You are documenting resolved incidents for a searchable DevOps knowledge base.

From this Jira issue ({issue_key}), extract only what is supported by the text.

Write:
1) **Final root cause** — short paragraph or "Unclear from comments."
2) **Resolution** — numbered, actionable steps someone could repeat.
3) **Prevention** — optional bullet list if mentioned.

If comments contradict each other, note the ambiguity briefly.

---
{flat_context}
"""
    try:
        return llm.invoke(prompt).content.strip()
    except Exception:
        return None


def sync_closed_issues_to_kb(
    days: int = 30,
    limit: int = 50,
    dry_run: bool = False,
    force_keys: list[str] | None = None,
) -> dict[str, object]:
    """
    Find recently closed/resolved Jira issues, summarize description + comments into a final
    resolution write-up, and upsert into the vector DB for RAG.

    Idempotency: keys listed in JIRA_KB_PROCESSED_FILE are skipped unless listed in force_keys.
    """
    stats: dict[str, object] = {
        "examined": 0,
        "skipped_processed": 0,
        "skipped_empty": 0,
        "indexed": 0,
        "dry_run_ready": 0,
        "errors": [],
    }

    jql = default_closed_jql(days)
    if not jql:
        stats["errors"].append("Set JIRA_PROJECT_KEY or JIRA_JQL_CLOSED")
        return stats

    processed = _load_processed_keys()
    force_set = set(force_keys or [])

    search = search_issues_jql(jql, max_results=limit, fields=["key", "summary", "labels"])
    if search.get("error"):
        stats["errors"].append(search.get("error"))
        if search.get("detail"):
            stats["errors"].append(search["detail"])
        return stats

    issues = search.get("issues") or []
    ordered_keys: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        k = (issue.get("key") or "").strip()
        if k and k not in seen:
            seen.add(k)
            ordered_keys.append(k)
    for fk in force_set:
        if fk and fk not in seen:
            seen.add(fk)
            ordered_keys.append(fk)

    for key in ordered_keys:
        stats["examined"] += 1

        if key in processed and key not in force_set:
            stats["skipped_processed"] += 1
            continue

        payload = get_issue_for_kb(key)
        if payload.get("error"):
            stats["errors"].append(f"{key}: {payload.get('error')}")
            continue

        flat = format_issue_and_comments_for_prompt(payload)
        if not flat.strip():
            stats["skipped_empty"] += 1
            continue

        fields = payload.get("fields") or {}
        summary = fields.get("summary") or key
        labels = fields.get("labels") or []
        label_str = ", ".join(labels) if labels else ""

        summary_text = summarize_resolution_with_llm(key, flat)
        if not summary_text:
            summary_text = (
                "Automated summary unavailable (LLM missing or failed). Snippet from issue:\n\n"
                + flat[:4000]
            )

        doc_body = "\n\n".join(
            [
                f"[Jira {key}] {summary}",
                f"Labels: {label_str}" if label_str else "",
                "",
                summary_text,
            ]
        ).strip()

        metadata = {
            "issue_key": key,
            "summary": summary[:500],
            "labels": label_str[:500],
            "source": "jira_closed",
        }

        if dry_run:
            stats["dry_run_ready"] = int(stats["dry_run_ready"]) + 1  # type: ignore[arg-type]
            continue

        ok = upsert_resolution_document(doc_id=key, text=doc_body, metadata=metadata)
        if ok:
            processed.add(key)
            _save_processed_keys(processed)
            stats["indexed"] = int(stats["indexed"]) + 1
        else:
            stats["errors"].append(f"{key}: vector upsert failed (embeddings / Chroma?)")

    return stats

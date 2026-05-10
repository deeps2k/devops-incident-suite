#!/usr/bin/env python3
"""
Pull recently resolved Jira issues, summarize description + comments into a final resolution,
and upsert into the local Chroma vector store for RAG.

Environment: same as the app (.env) — JIRA_* , OPENAI_* , CHROMA_* , EMBEDDING_MODEL .

Examples:
  python scripts/sync_closed_jira_to_kb.py --days 14 --limit 20
  python scripts/sync_closed_jira_to_kb.py --dry-run --days 7
  python scripts/sync_closed_jira_to_kb.py --force PROJ-101 PROJ-102
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from knowledge.jira_kb_sync import sync_closed_issues_to_kb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync closed Jira issues into the incident KB (RAG).")
    parser.add_argument("--days", type=int, default=30, help="JQL window: updated in the last N days")
    parser.add_argument("--limit", type=int, default=50, help="Max issues from search")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Chroma or processed file")
    parser.add_argument(
        "--force",
        nargs="*",
        default=[],
        help="Re-process these issue keys even if already marked processed",
    )
    args = parser.parse_args()

    stats = sync_closed_issues_to_kb(
        days=args.days,
        limit=args.limit,
        dry_run=args.dry_run,
        force_keys=list(args.force) if args.force else None,
    )

    print("Sync finished:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if stats.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Redact PII from raw logs using Microsoft Presidio before LLM or outbound integrations."""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass, field

_SPACY_MODEL = os.getenv("PRESIDIO_SPACY_MODEL", "en_core_web_sm")
_MAX_CHUNK_CHARS = max(5000, int(os.getenv("PRESIDIO_MAX_CHUNK_CHARS", "50000")))


def _ensure_writable_tldextract_cache() -> None:
    """Presidio uses tldextract; point it at a writable dir (HF Spaces, CI, sandbox)."""
    if os.environ.get("TLDEXTRACT_CACHE"):
        return
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for candidate in (
        os.path.join(root, ".cache", "tldextract"),
        os.path.join(tempfile.gettempdir(), "devops-incident-suite-tldextract"),
    ):
        try:
            os.makedirs(candidate, exist_ok=True)
            os.environ["TLDEXTRACT_CACHE"] = candidate
            return
        except OSError:
            continue


_ensure_writable_tldextract_cache()

# PII + network identifiers. IPs and DNS-style hostnames are on by default; use PRESIDIO_KEEP_* to retain them for triage.
_SERVER_HOSTNAME_ENTITY = "SERVER_HOSTNAME"

_DEFAULT_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "US_BANK_NUMBER",
    "IBAN_CODE",
    "CRYPTO",
    "PERSON",
    "IP_ADDRESS",
    _SERVER_HOSTNAME_ENTITY,
]

_engine_lock = threading.Lock()
_analyzer = None
_anonymizer = None


def _entities_to_detect() -> list[str]:
    raw = os.getenv("PRESIDIO_ENTITIES")
    if raw and raw.strip():
        return [e.strip() for e in raw.split(",") if e.strip()]
    entities = list(_DEFAULT_ENTITIES)
    if os.getenv("PRESIDIO_KEEP_IP", "").lower() in ("1", "true", "yes"):
        entities = [e for e in entities if e != "IP_ADDRESS"]
    if os.getenv("PRESIDIO_KEEP_HOSTNAMES", "").lower() in ("1", "true", "yes"):
        entities = [e for e in entities if e != _SERVER_HOSTNAME_ENTITY]
    return entities


def _register_server_hostname_recognizer(analyzer) -> None:
    """FQDN / Kubernetes DNS names that Presidio does not cover as a single built-in entity."""
    from presidio_analyzer import PatternRecognizer
    from presidio_analyzer.pattern import Pattern

    # *.svc.cluster.local
    k8s = Pattern(
        name="kubernetes_dns_name",
        regex=r"\b[\w.-]+\.svc\.cluster\.local\b",
        score=0.85,
    )
    # short infra suffixes: app.local, db.internal
    short_suffix = Pattern(
        name="short_internal_suffix",
        regex=r"\b[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.(?:local|internal|lan)\b",
        score=0.75,
    )
    # RFC1123-style hostname with at least two dots (api.eu.prod.example.com) — avoids common two-label false positives like file.py
    fqdn = Pattern(
        name="multi_label_hostname",
        regex=(
            r"\b(?=[a-zA-Z0-9._-]{4,253}\b)"
            r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.){2,}"
            r"[a-zA-Z]{2,63}\b"
        ),
        score=0.55,
    )
    recognizer = PatternRecognizer(
        supported_entity=_SERVER_HOSTNAME_ENTITY,
        name="server_hostname_patterns",
        patterns=[k8s, short_suffix, fqdn],
        supported_language="en",
    )
    analyzer.registry.add_recognizer(recognizer)


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for line in lines:
        line_len = len(line)
        if size + line_len > max_chars and buf:
            chunks.append("".join(buf))
            buf = []
            size = 0
        buf.append(line)
        size += line_len
    if buf:
        chunks.append("".join(buf))
    return chunks


def _get_engines():
    global _analyzer, _anonymizer
    with _engine_lock:
        if _analyzer is not None and _anonymizer is not None:
            return _analyzer, _anonymizer

        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": _SPACY_MODEL}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        _register_server_hostname_recognizer(_analyzer)
        _anonymizer = AnonymizerEngine()
        return _analyzer, _anonymizer


@dataclass
class AnonymizeResult:
    text: str
    entity_count: int = 0
    entity_types: dict[str, int] = field(default_factory=dict)
    chunks_processed: int = 1
    skipped: bool = False
    skip_reason: str | None = None

    def summary_line(self) -> str:
        if self.skipped and self.skip_reason:
            return f"Anonymization skipped: {self.skip_reason}"
        if self.entity_count == 0:
            return "No Presidio detections in this log sample."
        types = ", ".join(f"{k}: {v}" for k, v in sorted(self.entity_types.items()))
        return f"Redacted {self.entity_count} span(s) [{types}] across {self.chunks_processed} chunk(s)."


def anonymize_logs(text: str) -> AnonymizeResult:
    """
    Detect and replace sensitive spans using Presidio. Empty input returns empty result.
    """
    if not text.strip():
        return AnonymizeResult(text="")

    if os.getenv("PRESIDIO_DISABLE", "").lower() in ("1", "true", "yes"):
        return AnonymizeResult(
            text=text,
            skipped=True,
            skip_reason="PRESIDIO_DISABLE is set",
            chunks_processed=0,
        )

    entities = _entities_to_detect()
    try:
        analyzer, anonymizer = _get_engines()

        from presidio_anonymizer.entities import OperatorConfig

        operators = {"DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})}

        chunks = _chunk_text(text, _MAX_CHUNK_CHARS)
        out_parts: list[str] = []
        total_spans = 0
        type_counts: dict[str, int] = {}

        for chunk in chunks:
            results = analyzer.analyze(text=chunk, entities=entities, language="en")
            anonymized = anonymizer.anonymize(
                text=chunk,
                analyzer_results=results,
                operators=operators,
            )
            out_parts.append(anonymized.text)
            for r in results:
                total_spans += 1
                et = r.entity_type
                type_counts[et] = type_counts.get(et, 0) + 1

        return AnonymizeResult(
            text="".join(out_parts),
            entity_count=total_spans,
            entity_types=type_counts,
            chunks_processed=len(chunks),
        )
    except Exception as exc:
        raise RuntimeError(
            "Presidio anonymization failed. Ensure presidio-analyzer, presidio-anonymizer, "
            "and the en_core_web_sm spaCy model are installed."
        ) from exc

"""Optional Langfuse records of scans and benchmark runs (``pip install "pagevet[langfuse]"``).

Set ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY`` and, for a self-hosted instance,
``LANGFUSE_BASE_URL``. Then:

    pagevet --urls urls.txt --langfuse brake-rotors-2026-11     # one trace per page, the run as the session
    pagevet-bench cases.jsonl --langfuse                         # one trace per benchmark run

Each scanned page becomes a trace with its findings as output and these scores:

    max_severity          0 none, 1 low, 2 medium, 3 high
    findings              number of findings
    ai_crawlers_refused   AI crawler user agents that could not fetch a page a browser could (--compare-agents)
    content_differs       1 when an AI crawler was served different content
    read                  1 when the page was read, 0 when it was not (error, robots.txt)
    fetch_fallbacks       with --via auto: fetchers tried before the one that read the page (0 = plain HTTP worked)
    fetch_ms              with --via auto: total fetch time in milliseconds

A benchmark run becomes one trace with ``catch_rate`` and ``false_alarm_rate`` as scores and the
per-group rates as metadata. Recording is best effort: a Langfuse failure never changes a scan's
result or exit code. Nothing is sent unless ``--langfuse`` is given.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import asdict
from typing import Any

from pagevet import install_hint

SEVERITY = {"": 0, "low": 1, "medium": 2, "high": 3}


def configured() -> bool:
    """Return whether Langfuse keys are in the environment."""
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


def _client(client: Any | None) -> Any:
    if client is not None:
        return client
    if not configured():
        raise RuntimeError("--langfuse needs LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
    try:
        from langfuse import get_client
    except ImportError as exc:
        raise RuntimeError(f"--langfuse needs the optional extra: {install_hint('langfuse')}") from exc
    return get_client()


def _trace_id(*parts: str) -> str:
    return hashlib.sha256(":".join(("pagevet",) + parts).encode()).hexdigest()[:32]


def page_scores(result: Any) -> dict[str, float]:
    """Return the scores recorded for one page result."""
    findings = result.findings
    refused = {f.channel for f in findings if "fetch_differs" in f.kinds}
    return {
        "max_severity": float(max((SEVERITY.get(f.severity, 0) for f in findings), default=0)),
        "findings": float(len(findings)),
        "ai_crawlers_refused": float(len(refused)),
        "content_differs": 1.0 if any("content_differs" in f.kinds or "cloaked_instruction" in f.kinds for f in findings) else 0.0,
        "read": 0.0 if result.error else 1.0,
    } | _fetch_scores(result)


def _fetch_scores(result: Any) -> dict[str, float]:
    """With --via auto: how many fallbacks the fetch chain needed and how long it took."""
    fetched = (getattr(result, "evidence", None) or {}).get("fetch")
    if not fetched:
        return {}
    tried = [a for a in fetched.get("attempts", []) if a.get("reason") != "not configured"]
    return {"fetch_fallbacks": float(max(len(tried) - 1, 0)), "fetch_ms": float(fetched.get("ms", 0))}


def _propagate(propagate: Callable[..., Any] | None, client_given: bool) -> Callable[..., Any] | None:
    if propagate is not None or client_given:
        return propagate
    try:
        from langfuse import propagate_attributes
    except ImportError:  # older SDKs: no session grouping
        return None
    return propagate_attributes


def record_scan(results: list[Any], run: str, version: str, client: Any | None = None,
                propagate: Callable[..., Any] | None = None) -> int:
    """Record each page as a trace in session ``run``; return how many were sent."""
    propagate = _propagate(propagate, client is not None)
    client = _client(client)
    sent = 0
    for result in results:
        trace_id = _trace_id(run, result.source)
        top = max((f.severity for f in result.findings), key=lambda s: SEVERITY.get(s, 0), default="")
        tags = ["pagevet", f"severity:{top or 'none'}"] + (["unread"] if result.error else [])
        scope = propagate(session_id=run, tags=tags, trace_name="pagevet-scan") if propagate else nullcontext()
        with scope:
            span = client.start_observation(
                trace_context={"trace_id": trace_id}, name="pagevet-scan", as_type="span",
                input={"source": result.source}, output={"findings": [asdict(f) for f in result.findings], "error": result.error},
                metadata={"run": run, "pagevet": version, "evidence": result.evidence,
                          "kinds": sorted({k for f in result.findings for k in f.kinds})})
            span.end()
        for name, value in page_scores(result).items():
            client.create_score(trace_id=trace_id, name=name, value=value,
                                data_type="BOOLEAN" if name in ("content_differs", "read") else "NUMERIC")
        sent += 1
    client.flush()
    return sent


def record_bench(report: dict, cases: str, client: Any | None = None) -> str:
    """Record one benchmark run as a trace; return its id."""
    client = _client(client)
    trace_id = _trace_id("bench", report.get("detector", ""), report.get("cases_sha256", ""), report.get("version", ""))
    span = client.start_observation(
        trace_context={"trace_id": trace_id}, name="pagevet-bench", as_type="evaluator",
        input={"cases": cases, "cases_sha256": report.get("cases_sha256", ""), "detector": report.get("detector")},
        output={"catch_rate": report.get("catch_rate"), "false_alarm_rate": report.get("false_alarm_rate")},
        metadata={"by_group": report.get("by_group"), "kinds_on_caught": report.get("kinds_on_caught"),
                  "pagevet": report.get("version")})
    span.end()
    for name in ("catch_rate", "false_alarm_rate"):
        rate = (report.get(name) or {}).get("rate")
        if rate is not None:
            client.create_score(trace_id=trace_id, name=name, value=float(rate), data_type="NUMERIC")
    client.flush()
    return trace_id


# --- OpenTelemetry ------------------------------------------------------------------------
# ``pip install "pagevet[otel]"`` and the standard OTEL_* variables (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME…).
# One span per scanned page, named "pagevet.scan", in one trace per run, with the same numbers as the Langfuse scores
# (``pagevet.max_severity``, ``pagevet.findings``, …) plus ``url.full`` and ``pagevet.version``. Best effort, like
# Langfuse: a tracing failure never changes a scan's result or exit code.


def _otel_tracer() -> Any:  # pragma: no cover - needs the optional extra
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        from pagevet import install_hint

        raise RuntimeError(f"OpenTelemetry needs the optional extra: {install_hint('otel')}") from exc
    provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "pagevet")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("pagevet"), provider


def record_otel(results: list[Any], run: str, version: str, tracer: Any | None = None) -> int:
    """Emit one span per page under a ``pagevet.run`` span; return the number of page spans."""
    provider = None
    if tracer is None:  # pragma: no cover - needs the optional extra
        tracer, provider = _otel_tracer()
    sent = 0
    with tracer.start_as_current_span("pagevet.run", attributes={"pagevet.run": run, "pagevet.version": version}):
        for r in results:
            attrs = {"url.full": r.source, "pagevet.version": version, "pagevet.run": run,
                     **{f"pagevet.{k}": v for k, v in page_scores(r).items()}}
            if r.error:
                attrs["error.type"] = r.error[:200]
            with tracer.start_as_current_span("pagevet.scan", attributes=attrs):
                sent += 1
    if provider is not None:  # pragma: no cover
        provider.force_flush()
    return sent

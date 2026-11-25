# Roadmap

Public versions start at 0.1.0 and count up to 1.0.

**0.1.0 (first public release)** ships everything built in the private repository, as internal versions: internal 0.1.0 scanner; internal 0.2.0 sources (Firecrawl, crawlee-server), `pagevet-bench`, first BIPIA measurement; internal 0.3.0 detector interface with optional Prompt Guard 2 and Jev layers (not yet run live), false-alarm measurement on 194 pages; internal 0.4.0 evasion report and disguise handling; internal 0.5.0 stylesheet-hidden text, MCP server, second real-page sample; internal 0.6.0 crawlee-server modes, checked against crawlee-server 2.2.0; internal 0.7.0 `--baseline` re-scans and a blind false-alarm check on 181 article and user-content pages; internal 0.8.0 18 more hiding methods and three new hidden channels; internal 0.9.0 `--fetch-css`; internal 0.10.0 letter-spaced instructions; internal 0.11.0 instructions split into short fragments; internal 0.12.0 more translated instructions, with a held-out check and a non-English false-alarm set; internal 0.13.0 release check, every-word letter spacing, `fetch_css` in MCP; internal 0.14.0 robots.txt respected; internal 0.15.0 GitHub Action; internal 0.16.0 re-scans with change alerts and a Windmill script; internal 0.17.0 PDFs; internal 0.18.0 linear stylesheet parser, stylesheet-hidden channel, CDN stylesheets; internal 0.19.0 Italian and Dutch; internal 0.20.0 `pagevet-discover` and the first field study; internal 0.21.0 Jev through OpenRouter and the quote-checked `llm` second opinion; internal 0.22.0 Langfuse records; internal 0.23.0 `pagevet-study`, three more field studies, and the first public release (install from GitHub, `--version`, releases without PyPI, pinned actions); internal 0.24.0 `pagevet-access` (fourteen AI crawlers, RFC 9309, llms.txt, noai and TDM signals, firewall-refusal probes, `--require`, MCP `check_ai_access`), Polish, Swedish, Russian, Japanese and Chinese, sentences ending on a dangling word joined, descendant, child and attribute selectors, a container image, a pre-commit hook and a Python API guide; internal 0.25.0 the field-study explorer.

**0.2.0 (released):** overrides that don't say "previous" and text addressed to the AI reading this page (second held-out set 6 → 69 of 216), `--llms-txt`, `--headers`, OWASP and MITRE ATLAS IDs in JSON and SARIF, the explorer published from the release workflow.

**0.3.0 (released):** commercial-manipulation finding class, user-submitted content as a third-party planting zone, rules as open data (`pagevet-rules`), human-vs-model view (`pagevet-view`, also through Firecrawl).

**0.4.0 (released):** `pagevet-reproduce`, deepset benchmark, ProtectAI open classifier detector, OpenTelemetry spans, field studies repeated, standing index workflow.

**0.5.0 (released):** guard, `pagevet-serve` and an n8n workflow, receipts, OCR of text in images, head-to-head with an open classifier, a fifth field study.

**0.6.0 (released):** sandbox replay against a local model, Ollama second opinion, case studies, the classifier's false alarms on real pages, the monthly index schedule.

**1.0.0 (released):** stable command line, formats and Python API with semantic versioning and a contract test; offline numbers from one command; the patterns-versus-model comparison published.

**1.1.0 (released):** AI share links ("Summarize with AI" buttons) decoded and scanned, the memory-planting rule, OWASP Agentic and NIST IDs, a field study through Firecrawl.

After 1.0:
- **1.2.0 (next):** the guard measured as a defense on a public agent benchmark: attacks blocked, tasks still completed, false alarms and speed, with published attack sets and a local model.
- **1.3.0 (planned):** detection-side integrations for promptfoo, garak and PyRIT; `.docx` input; MCP tool descriptions scanned with the same rules.
- **Live runs** (approved; run from the maintainer's machine; [`docs/bench/2026-11-25-live/`](bench/2026-11-25-live/)): the Firecrawl source and `pagevet-view --via firecrawl` passed in 1.0.1. Still to run: Jev and the quote-checked `llm` second opinion on BIPIA and clean pages with costs recorded, Langfuse records, and the crawlee-server source. Results go in a 1.0.x release.
- **Packaging:** releases are on GitHub with the wheel, `explore.html` and a container image. PyPI (set `PYPI_PUBLISH=true` once a PyPI project exists) and a Marketplace listing for the Action are optional.

Not planned: generating injections, or any feature aimed at defeating other detectors.

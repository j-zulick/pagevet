# Changelog

All notable changes, newest first. Versions follow [semantic versioning](https://semver.org/); the public interface and how it may change are in [docs/API.md](docs/API.md#stability).

## [Unreleased]

## [0.1.0] - 2026-11-26
First release. PageVet was developed from November 19 to 25, 2026; results from those development builds are labelled by date ("pre-release (2026-11-24)") in `docs/bench/`.

**Scanning** (`pagevet`)
- Finds text aimed at AI models in what a reader sees and what only a model reads: visible text, user-submitted content (comments, reviews, forum posts, as their own channel), hidden elements (30+ hiding methods, including the page's own and linked stylesheets), HTML comments, attributes and meta tags, JSON-LD, noscript, templates, SVG text, hidden inputs, HTTP headers (`--headers`), llms.txt (`--llms-txt`), text in images (`--ocr`, local OCR), PDFs, Word documents (hidden runs, white or tiny text, comments, metadata) and MCP servers' tool descriptions (`--mcp-tools`).
- Undoes look-alike letters, invisible characters, letter spacing, ROT13, reversed text, split sentences, invisible Unicode tags and base64. Patterns in twelve languages.
- AI share links ("Summarize with AI" buttons that open ChatGPT, Claude, Perplexity, Copilot, Grok, Gemini or Google AI Mode with a pre-filled prompt) are decoded and scanned.
- Finding classes for memory planting (AI recommendation poisoning) and commercial manipulation (steering what AI answers recommend, rank or cite), and a résumé profile (`--profile resume`) with a candidate-steering rule.
- Every finding carries a severity, advice and framework IDs: OWASP Top 10 for LLM Applications 2025, OWASP Top 10 for Agentic Applications 2026, MITRE ATLAS and NIST AI 100-2e2025.
- Output as text, JSON (`docs/schema/report.schema.json`), SARIF, Markdown, CSV, HTML or a scan receipt with SHA-256 evidence.

**AI crawler access** (`pagevet-access`)
- Which of fourteen AI crawlers may read a page (robots.txt per RFC 9309, meta tags, X-Robots-Tag, noai and TDM signals, llms.txt) and which the server actually serves (firewall-refusal probes); `--require` as a CI gate.

**Using it in a pipeline**
- `pagevet-guard` and `pagevet.guard.guard()`: the text a person sees, with hidden channels dropped and matching paragraphs replaced, for use between fetching a page and handing it to a model.
- `pagevet-serve`, a local HTTP API (`POST /scan`, `POST /guard`), with an importable n8n workflow; an MCP server (`scan_page`, `check_ai_access`); a GitHub Action (SARIF); a container image; a pre-commit hook; a Python API ([docs/API.md](docs/API.md)).
- Your own Firecrawl and crawlee-server as sources for pages built by scripts; `pagevet-view` for a side-by-side page of what a person sees and what a model reads.
- Optional second opinions (Prompt Guard 2, ProtectAI's classifier, Jev, the `llm` prompt, a local Ollama model), Langfuse records and OpenTelemetry spans. `pagevet-replay` replays a page's findings against a local model.
- Red-team tool integrations: a promptfoo assertion, a garak detector and a PyRIT scorer (`integrations/`).

**Measured** (data, script and date for each in `docs/bench/`; `pagevet-reproduce` regenerates every offline number)
- False alarms: none at medium or high on 193 homepages, 181 fresh article and forum pages and 368 pages in twelve languages; 1 medium and 2 low on 1,052 re-fetched pages.
- BIPIA (Microsoft's indirect-injection benchmark): 29 of 75 distinct attacks caught (1,450 of 3,750 injected cases), 0 of 50 clean emails flagged; evasion and hiding reports with frozen held-out sets ([docs/EVASION.md](docs/EVASION.md)); a head-to-head with ProtectAI's open classifier; the guard on AgentDojo's tool outputs (0 of 339 clean outputs flagged; only one of six published attack styles recognized, published as measured).
- Six field studies of the pages behind shopping, software and marketing searches: no deliberate hidden instructions on 273 pages read; 14–43% of readable pages refuse at least one AI crawler. Browse them in the explorer (`pagevet-study explore`, published on GitHub Pages).
- The person who wrote the patterns had seen part of the second held-out set, so treat that figure as optimistic.

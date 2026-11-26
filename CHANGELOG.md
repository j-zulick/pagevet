# Changelog

All notable changes, newest first. Versions follow [semantic versioning](https://semver.org/); the public interface and how it may change are in [docs/API.md](docs/API.md#stability).

## [0.3.0] - 2026-11-26
- **Six more AI crawlers:** added from the operators' own crawler pages: search: Google-CloudVertexBot, meta-webindexer, Amzn-SearchBot, DuckAssistBot; fetch on request: meta-externalfetcher, Amzn-User (Meta and Amazon say user-initiated fetches may not follow robots.txt). Twenty in all; the fourteen earlier rows are unchanged.
- **AI visibility report:** `pagevet-access URL --report FILE` also writes one self-contained HTML page per site: crawler access per AI crawler (robots.txt, page signals, firewall refusals), findings and AI share links (from `--scan-report`, a `pagevet --format json` report, or the page's raw HTML), `llms.txt`, AI-crawler traffic with `--traffic` (and `--updates`, `--traffic-bots`), and how each page was read when the scan report's pages carry fetch details (`evidence.fetch`). New module `pagevet.visibility`; the flag names are kept in `pagevet.visibility.FLAGS`.
- **AI bot-traffic import:** `pagevet.traffic` (`python -m pagevet.traffic`) reads a CSV, a combined-format access log or an OpenSearch export (search-API JSON or NDJSON, with field-name options), matches user agents against the AI crawler list and an optional extra bots file in the same CSV format (`--bots`, for search-engine crawlers and others; each row's group is shown), and reports hits, first and last seen per page and crawler, and the unknown-agent share, as JSON or CSV. Client addresses are not read and query strings are dropped. `--updates` adds AI-crawler hits 14 days before and after each content update, labelled a signal, not proof. Synthetic samples in `examples/traffic/`.
- **Langfuse benchmark tracking:** `pagevet-bench --langfuse-dataset NAME` keeps the cases as a Langfuse dataset and records the run with the SDK's experiment runner (experiment `pagevet`, run name = version; item scores `caught` and `false_alarm`, run scores `catch_rate`, `false_alarm_rate`, `median_ms`, `p95_ms`). `docs/bench/scripts/bench_sets.py` freezes the benchmark sets (evasion and hiding always; BIPIA, deepset, the false-alarm pages and AgentDojo offline when their data is supplied) and runs one experiment per set. A case may carry `"format": "html"` to be judged as a page with `scan_text`, as the evasion and hiding reports count.
- **Pydantic Evals harness** (`docs/bench/evals/`): the same frozen sets through `pydantic_evals`, with expected-finding, no-false-alarm and latency-budget evaluators; model second opinions only when asked for and configured. `pydantic-evals` is a dev dependency only.
- `evasion_run.py` and `hiding_run.py` expose their cases (`iter_cases`, `iter_pages`); their output is byte-for-byte unchanged and `pagevet-reproduce` matches. No change to detection, existing commands, options, exit codes or formats.
- No change to existing commands, options, formats or detection results.

## [0.2.0] - 2026-11-26
- **Fetch chain (`--via auto`):** plain HTTP first, then your Firecrawl, then your crawlee-server, when a page fails, is blocked (401, 403, 429, 503) or is built by scripts. Each JSON result records the fetcher used, every attempt with its time and fallback reason, and the total time (`evidence.fetch`, an optional field in the report schema); `--langfuse` adds `fetch_fallbacks` and `fetch_ms` scores. Python: `chain_fetcher`, `FetchResult`, `needs_render` in `pagevet.sources`.
- **AI crawler list as data:** the fourteen crawlers moved to `src/pagevet/data/ai_crawlers.csv` (same list, same results). `pagevet-access --crawlers FILE` checks extra crawlers in the same format; `examples/crawlers/example-ai-crawlers.csv` shows one fictional row. Python: `load_crawlers`, `register_crawlers`.
- **Email (.eml):** `pagevet message.eml` scans the subject, text and visible HTML as visible, and hidden HTML, custom headers and PDF or Word attachments' hidden text as hidden; share links in the HTML are decoded. Python: `scan_eml`, `eml_channels`.
- **Explorer on phones:** at 375 px the field-study explorer fits the screen; the results table scrolls inside its own box instead of pushing facet counts and columns off the page (a browser test checks 375×812).
- No change to existing commands, options, formats or detection results.

**Documentation**
- README opens with the question it answers, two links, a screenshot and one finding.
- README: the guard returns filtered text and a review status (no safety promise); a clean result describes the checks run; quick start leads with the offline sample and explains exit codes; container example pinned; the automotive field study is linked on the first screen.
- Field studies: a refused crawler request is reported as "could not retrieve the page at the time"; inclusion in AI answers was not measured.
- Releases are titled with their tag (for example `v0.2.0`).

**Releases**
- Short release notes: one sentence, three bullets naming what to try, one sentence on the assets and a link to this file; written in `docs/releases/vX.Y.Z.md` (checked for that shape) or built from the CHANGELOG section.
- Draft first: each release is created as a hidden draft, published and marked Latest only after the wheel, source archive and `explore.html` are all attached; the image's `latest` tag moves after that (`.github/release-steps.sh`, tested offline).

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

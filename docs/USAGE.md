# Using PageVet

The [README](../README.md) covers install, quick start and what PageVet checks. This page covers every command and option in more detail.

- [Scanning pages](#scanning-pages)
- [AI crawler access](#ai-crawler-access)
- [AI visibility report and bot traffic](#ai-visibility-report-and-bot-traffic)
- [In the agent's path: guard, HTTP API, MCP](#in-the-agents-path-guard-http-api-mcp)
- [Output](#output)
- [CI: GitHub Action and pre-commit](#ci-github-action-and-pre-commit)
- [Rendering through your own scrapers](#rendering-through-your-own-scrapers)
- [Re-scans and change alerts](#re-scans-and-change-alerts)
- [Field studies](#field-studies)
- [Second opinions (experimental)](#second-opinions-experimental)
- [Tracing: Langfuse and OpenTelemetry](#tracing-langfuse-and-opentelemetry)
- [Benchmark tracking: frozen sets, Langfuse experiments, Pydantic Evals](#benchmark-tracking-frozen-sets-langfuse-experiments-pydantic-evals)
- [Red-team tools (promptfoo, garak, PyRIT)](#red-team-tools-promptfoo-garak-pyrit)
- [Scores, OpenSearch and storage](#scores-opensearch-and-storage)
- [Configuration](#configuration)
- [Safety](#safety)

## Install the CLI

Install the pinned release with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "git+https://github.com/j-zulick/pagevet@v0.4.0"
```

You can also install with `pip install "git+https://github.com/j-zulick/pagevet@v0.4.0"` in a virtual environment, or use `docker run --rm ghcr.io/j-zulick/pagevet:0.4.0 https://example.com/pricing`. Replace the example URL with a page you control. To run the bundled sample, follow the [clone-based quick start](../README.md#quick-start).

## Scanning pages
```bash
pagevet https://example.com/pricing                         # one page
pagevet --sitemap https://example.com/sitemap.xml --format html --out audit.html
pagevet --compare-agents https://example.com/               # is content different for AI crawlers?
pagevet --urls urls.txt --baseline last.json --format json --out now.json   # only what is new since last.json
pagevet --fetch-css https://example.com/                    # also apply the page's own linked stylesheets
pagevet --fetch-css --css-any-host https://example.com/     # including stylesheets on CDNs
pagevet --ignore-robots https://your-site.example/staging/  # your own pages that robots.txt keeps crawlers out of
pagevet --headers --llms-txt https://example.com/           # also the HTTP response headers and the site's llms.txt
pagevet --ocr https://example.com/pricing                   # also the text inside the page's images (the ocr extra)
pagevet whitepaper.pdf https://example.com/brochure.pdf     # PDFs (the pdf extra)
pagevet cv.docx --profile resume                            # Word documents; résumé advice, fails on medium
pagevet --mcp-tools tools.json                              # an MCP server's tools/list result
pagevet-view https://example.com/pricing --out view.html    # what a person sees next to what an AI model also reads
```

Optional extras (`pdf`, `ocr`, `mcp`, `langfuse`, `otel`, `classifier`, `jev`) go in brackets: `uv tool install "pagevet[pdf,mcp] @ git+https://github.com/j-zulick/pagevet@v0.4.0"`.

**Channels in detail.**
- *Hidden elements:* `display:none`, off-screen, zero-size, transparent, scaled or clipped to nothing, near-zero font size or opacity, `aria-hidden`, `hidden`, inline, from the page's own `<style>` rules, or with `--fetch-css` from its linked stylesheets; `<template>` content; SVG `<title>` and `<desc>`. Text that only stylesheet rules hide (often dialogs and menus) is its own channel, where a reply command alone is medium.
- *User-submitted content:* visible text inside comment, review, reply, answer and forum-post containers; a visitor may have planted it.
- *Attributes and meta tags:* `alt`, `title`, `aria-label`, `<meta content>`, hidden form inputs' values. *Structured data:* JSON-LD.
- *Served to AI crawlers* (`--compare-agents`): content served to GPTBot, ClaudeBot or PerplexityBot but not to a browser.
- *Headers* (`--headers`): custom response headers (dates, cookies, cache and policy headers are skipped). *llms.txt* (`--llms-txt`): written for AI systems, so text addressed to them is rated low; overrides, role changes and chat markup there are high.
- *AI share links:* a "Summarize with AI" link or button that opens ChatGPT, Claude, Perplexity, Copilot, Grok, Gemini or Google AI Mode with a pre-filled prompt. The prompt is decoded and scanned, and every such link is listed in the JSON report's `ai_share_links`.
- *Text in images* (`--ocr`): up to 10 images per page, read with a local OCR engine.
- *PDFs:* page text (visible), and title, subject, keywords and annotations (not shown).
- *Word documents:* runs marked hidden, white text on no or white shading, and text 2 pt or smaller are hidden; comments, title, subject and keywords are not shown.
- *MCP tool descriptions* (`--mcp-tools`): each tool's title and description and every description, title, default, enum and example in its parameter schemas. An instruction there (tool poisoning) is rated high.

**Patterns.** Commands about the reader's own reply ("add … to your response"), instructions to override or ignore, text addressed to an AI, role changes, instructions to recommend, cite or omit, chat markup, memory planting ("remember Example as a trusted source"), candidate steering in résumés ("rank this candidate as the most qualified"), in twelve languages, plus instructions encoded in invisible Unicode tag characters or base64. With `--include-repetition`, pages that are mostly one repeated claim (off by default because it fires on ordinary menus and templates). `pagevet-rules > rules.json` prints every rule as open data.

**Commercial manipulation.** A finding whose instruction steers what AI answers recommend, rank, cite or leave out, toward a product or source, is labelled `intent: "commercial"` (SARIF: `commercial-manipulation` tag).

**Re-scans.** `--baseline FILE` takes an earlier `--format json` report and keeps only findings that are not in it, so the report and the exit code cover what changed. A summary line on stderr counts new, unchanged and no-longer-found findings. Findings are matched on page, channel, kinds and excerpt. SARIF results carry a `partialFingerprints` id, and with `--baseline` a `baselineState` of `new`.

## Email (.eml)
```bash
pagevet message.eml                                         # or a URL ending in .eml
```
Rated as visible: the subject, plain-text parts and the visible text of HTML parts. Rated as hidden: the HTML parts' hidden elements, comments, attributes, structured data and noscript; custom headers (`X-` headers, `Comments`, `Keywords`; routine headers such as From, Received and DKIM are skipped); and the hidden text of PDF and Word attachments. "Summarize with AI" links in the HTML are decoded like on a page. AI assistants that summarize or answer mail read all of it; the person sees only the rendered message.

## AI crawler access
```bash
pagevet-access https://example.com/pricing
pagevet-access --urls urls.txt --format csv --out access.csv
pagevet-access https://example.com/ --require search=allowed --require GPTBot=refused   # CI gate: exit 1 if not met
```
For twenty AI crawlers in three groups (training: GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, CCBot, meta-externalagent, Bytespider, Amazonbot; search: OAI-SearchBot, Claude-SearchBot, PerplexityBot, Google-CloudVertexBot, meta-webindexer, Amzn-SearchBot, DuckAssistBot; fetch on request: ChatGPT-User, Claude-User, Perplexity-User, meta-externalfetcher, Amzn-User) it reports what robots.txt says, parsed per [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) (longest match, `allow` wins a tie, `*` and `$`; a 4xx robots.txt allows everything, a 5xx or unreachable one disallows everything); page signals (`robots` and per-crawler meta tags, `X-Robots-Tag`, `noai`, TDMRep reservations); whether `/llms.txt` exists; and, unless `--no-probe`, what the server answers each crawler's user agent. **A crawler robots.txt allows but the server refuses (401, 402, 403, 429, 451, 503 or a challenge page) is reported as a firewall refusal**: usually a bot-management rule nobody meant to apply to AI search. Text, JSON, CSV or Markdown. Probes send the user-agent string only, not the crawler's IP addresses.

**The crawler list is data.** The twenty crawlers live in [`src/pagevet/data/ai_crawlers.csv`](../src/pagevet/data/ai_crawlers.csv) (`token,operator,group,user_agent`). To check one more for a run, put it in a file with the same columns and pass `--crawlers FILE`; it is then checked, accepted by `--crawler` and `--require`, and listed like the others:
```bash
pagevet-access https://example.com/ --crawlers examples/crawlers/example-ai-crawlers.csv --require ExampleAIBot=refused
```
`ExampleAIBot` in that example file is fictional; it shows the format. A row with a bad token, an unknown group or a token already listed is refused with its row number.

## AI visibility report and bot traffic
```bash
pagevet-access https://example.com/ https://example.com/pricing --report visibility.html
pagevet-access https://example.com/ --report visibility.html --traffic access.log --updates updates.csv
pagevet-access https://example.com/ --report visibility.html --scan-report scan.json   # findings from a pagevet --format json report
python -m pagevet.traffic access.log --updates updates.csv --format csv --out traffic.csv
python -m pagevet.traffic access.log --bots search-bots.csv                            # search-engine crawlers next to AI crawlers
```
**Visibility report** (`--report FILE`): one self-contained HTML page per site (no scripts, all page text escaped) with crawler access per AI crawler (robots.txt, page signals, firewall refusals), PageVet's findings and AI share links (from `--scan-report` when it covers the page, else from the page's raw HTML read once more), the site's `llms.txt` and `llms-full.txt`, the traffic tables when `--traffic` is given, and how each page was read when the scan report's pages carry fetch details (`evidence.fetch`: `how`, `attempts`, `ms`). The usual text report still goes to stdout. Pages on several sites give one file per site (`visibility-<host>.html`).

**Bot traffic** (`pagevet.traffic`, or `--traffic` on the report) reads your own data: a CSV (`date,url,user_agent,hits` or `date,url,bot,hits`), a combined-format access log, or an OpenSearch export (search-API JSON or NDJSON; `--ts-field`, `--url-field`, `--ua-field`, defaults `@timestamp`, `url.path`, `user_agent.original`). For an export with other field names, run `python -m pagevet.traffic` with those options and pass its JSON report to `--traffic`. Hits are matched against PageVet's AI crawler list and, with `--bots FILE` (`--traffic-bots` on the report), an extra list in the same CSV format (`token,operator,group,user_agent`), for example search-engine crawlers: a row in an AI group (`training`, `search`, `fetch`) counts as an AI crawler, any other group as a listed bot, and every row shows its group. Client addresses are never read and query strings are dropped. The output (JSON or CSV only) has hits, first seen and last seen per page and crawler, totals per crawler (with HTTP status classes, `2xx` to `5xx`, when the data has them: the access log's status, a CSV `status` column, or OpenSearch's `--status-field`, default `http.response.status_code`), and the unknown-agent share: hits with an empty or automated-looking user agent that is on neither list, out of all hits. `--updates FILE` (`url,date`) adds AI-crawler hits in the 14 days before each content update and the 14 days from it on, with a flag when the data does not cover both windows. That is a signal, not proof: user agents can be faked and crawlers keep their own schedules. Synthetic samples: [`examples/traffic/`](../examples/traffic/).

Each crawler is reported on its own line, search engines included: the longest matching name wins, so `Googlebot-Image` is counted apart from `Googlebot`. Three names never appear in logs, because they are robots.txt controls rather than visitors: `Google-Extended` and `Applebot-Extended` (the pages are fetched by Googlebot and Applebot) and `Googlebot-News`. [`examples/traffic/search-bots.csv`](../examples/traffic/search-bots.csv) lists Googlebot, Googlebot-Image, Storebot-Google, bingbot, Applebot, DuckDuckBot, YandexBot, YandexImages, Baiduspider and Sogou web spider; add your own rows in the same format. To confirm a visit is real, check the client address against the operator's published ranges or reverse DNS (Google: `googlebot.com`; Apple: `applebot.apple.com`) in your own log store; PageVet never reads addresses.

## Scores, OpenSearch and storage
```bash
python -m pagevet.scores --scan scan.json --access access.json --traffic traffic.json --out scores.json   # or --format csv
python -m pagevet.traffic --opensearch-pipeline --bots search-bots.csv --drop-field source.ip > pipeline.json
python integrations/supabase/load.py --traffic traffic.json --scan scan.json --access access.json --scores scores.json
python integrations/hindsight/remember.py --scores scores.json --traffic traffic.json --bank my-site
```
**Scores** (`pagevet.scores`) read the JSON reports PageVet already writes (`pagevet --format json`, `pagevet-access --format json`, `python -m pagevet.traffic`); any may be left out, and a part that needs a missing report is shown as not measured.
- *Page risk* (0–100, higher is worse): each finding's severity, plus points for a hidden channel, commercial intent, memory planting and text served differently to AI crawlers.
- *Site AI visibility* (0–100, higher is more visible): the share of AI search and fetch crawlers allowed, no firewall refusals, `llms.txt`, and with a traffic report whether AI crawlers and search engines were seen. Training crawlers are listed but not scored.
- *Opportunity* (0–100): the visibility gap and the worst page risk combined, to rank sites for a closer look. Each site also lists its gaps (refused AI crawlers, no `llms.txt`, allowed crawlers absent from the traffic, a high unknown-agent share, pages that needed rendering, findings).

Every score carries its reasons. The weights are in [`src/pagevet/data/scoring.json`](../src/pagevet/data/scoring.json) with a `score_version` (pass your own with `--weights`); scores from different versions are not comparable. They are ranking aids from fixed rules, not detection rates.

**OpenSearch ingest pipeline** (`--opensearch-pipeline`): prints an ingest pipeline that tags each log document with `bot.token`, `bot.operator`, `bot.group`, `bot.kind` and `bot.verified: false`, from the same crawler lists and the same longest-name-first matching as the traffic import, so OpenSearch and PageVet agree. `--ua-field` sets the user-agent field (a dotted name is nested; `[user_agent.original]` is one flat key), and `--drop-field` removes fields such as the client address after tagging. Install it with `PUT _ingest/pipeline/pagevet-bots`. Confirming a visit against the operator's published ranges or reverse DNS is a separate step.

**Storage.** [`integrations/supabase/`](../integrations/supabase/) has the Postgres schema (bots, hits per page and bot, findings, crawler access, scores; row level security on, no client addresses) and a standard-library loader that upserts the reports through Supabase's REST API (`--dry-run` sends nothing). [`integrations/hindsight/`](../integrations/hindsight/) turns the same reports into short dated observations for a Hindsight memory bank, so an agent can recall and reflect on them later; the numbers stay in Supabase. Both are optional and outside the `pagevet` package.

Each crawler is reported on its own line, search engines included: the longest matching name wins, so `Googlebot-Image` is counted apart from `Googlebot`. Three names never appear in logs, because they are robots.txt controls rather than visitors: `Google-Extended` and `Applebot-Extended` (the pages are fetched by Googlebot and Applebot) and `Googlebot-News`. [`examples/traffic/search-bots.csv`](../examples/traffic/search-bots.csv) lists Googlebot, Googlebot-Image, Storebot-Google, bingbot, Applebot, DuckDuckBot, YandexBot, YandexImages, Baiduspider and Sogou web spider; add your own rows in the same format. To confirm a visit is real, check the client address against the operator's published ranges or reverse DNS (Google: `googlebot.com`; Apple: `applebot.apple.com`) in your own log store; PageVet never reads addresses.

## In the agent's path: guard, HTTP API, MCP
**Guard.** `pagevet.guard.guard(source, html)`, `pagevet-guard` (stdin, file or URL) or `POST /guard` returns the text a person sees, with hidden channels dropped, any paragraph that still matches an instruction replaced by a marker, chat markup removed, and `allowed: false` when a finding reaches the policy (`high` by default; `medium` or `never`). It only removes text. Measured on AgentDojo's tool outputs it raised no false alarms but recognized only one of six published attack styles ([results](bench/2026-11-25-agentdojo-guard/)): it is a check for text aimed at AI in web content, not a general agent-injection defense.

**HTTP API.** `pagevet-serve` (standard library, loopback by default): `POST /scan`, `POST /guard`, `GET /health`; private addresses refused on every redirect. An importable n8n workflow is in [`integrations/n8n/`](../integrations/n8n/).

**MCP server** (the `mcp` extra): `pagevet-mcp` runs over stdio; add it to Claude Desktop, Claude Code, Cursor or ChatGPT. Two tools: `scan_page` takes a public URL or pasted HTML (`fetch_css: true` also applies linked stylesheets; robots.txt is respected unless `ignore_robots: true`), and `check_ai_access` returns the access report. Addresses that resolve to private, loopback or link-local networks are refused.

**Sandbox replay.** `pagevet-replay URL` asks a local model (Ollama) the same neutral question about a page twice, once with everything a model reads and once with the guarded text, and reports whether words from a finding show up only in the first answer. It replays only text PageVet found on that page and never writes or varies an injection. Experimental, not measured.

## Output
Text, JSON ([schema](schema/report.schema.json)), CSV, a self-contained HTML report, and [SARIF 2.1.0](https://sarifweb.azurewebsites.net/) for code-scanning tools. Exit code 1 when a finding is at or above `--fail-on` (default `low`), 2 on errors with no findings.

- **Receipts.** Every JSON result records what was scanned in `evidence` (SHA-256 of the text read, time, how it was read); `--format receipt` writes a compact receipt ([schema](schema/receipt.schema.json)) with the rules' SHA-256 and each finding's fingerprint, for evidence pipelines.
- **Framework IDs.** Every JSON finding has a `taxonomy` object and every SARIF result `owasp`, `atlas`, `owasp_agentic` and `nist` properties: [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/); [MITRE ATLAS](https://atlas.mitre.org/) AML.T0051.001 (indirect prompt injection), plus AML.T0054 (jailbreak) for role and mode changes, AML.T0068 (prompt obfuscation) for hidden or disguised text and AML.T0080.000 (memory) for memory planting; the [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) ASI01 (agent goal hijack), plus ASI06 (memory and context poisoning) and ASI04 (agentic supply chain) for MCP tool descriptions; and [NIST AI 100-2e2025](https://csrc.nist.gov/pubs/ai/100/2/e2025/final) NISTAML.015 (indirect prompt injection), or NISTAML.018 for a prompt an AI share link pre-fills. Findings that only say a page differs by reader carry no ID.

## CI: GitHub Action and pre-commit
```yaml
- uses: actions/checkout@v5
- uses: j-zulick/pagevet@v0.4.0
  id: pagevet
  with:
    urls-file: urls.txt            # or targets: "https://example.com/ page.html", or sitemap: ...
    fail-on: high                  # low, medium, high, or never
- uses: github/codeql-action/upload-sarif@v4   # optional: needs code scanning (public repos, or GitHub Advanced Security)
  if: always()
  with:
    sarif_file: ${{ steps.pagevet.outputs.sarif-file }}
```
Outputs: `sarif-file`, `exit-code` (0, 1 or 2, as for the command) and `findings`. Inputs reach the shell through environment variables, never as interpolated code.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/j-zulick/pagevet
    rev: v0.4.0
    hooks:
      - id: pagevet      # fails a commit that adds HTML, Markdown or text with a medium or high finding
```

## Rendering through your own scrapers
Plain HTTP is the default and needs nothing. PageVet bundles no browser: for text added by JavaScript, it reads pages through a Firecrawl or [crawlee-server](https://github.com/j-zulick/crawlee-server) you run (both use Playwright).
```bash
pagevet --via auto https://example.com/                     # plain HTTP, then Firecrawl, then crawlee-server, as needed
pagevet --via firecrawl https://example.com/                # rendered HTML through your Firecrawl
pagevet --crawl https://example.com/ --max-pages 25         # a crawl through your crawlee-server
```
**The fetch chain (`--via auto`).** Plain HTTP goes first: it is cheapest and shows what a simple crawler sees. The page is read again through Firecrawl, then through crawlee-server (page mode, with a stored capture), when plain HTTP fails, is blocked (401, 403, 429 or 503), or returns a page built by scripts (under 200 visible characters plus an app shell or a "please enable JavaScript" notice). A service whose variables aren't set is skipped. Each JSON result says how the page was read in `evidence.fetch`: the fetcher that produced it (`how`), every attempt in order with its time and the reason it fell back, and the total time. With `--langfuse`, each page also gets `fetch_fallbacks` and `fetch_ms` scores. If no renderer succeeds, the plain-HTTP page is scanned and the attempt says so. robots.txt is checked over plain HTTP before any fetch.
`--crawl` runs a crawl with page capture on (`--crawl-mode page` fetches only the given URL) and scans the stored raw pages; each result carries the capture id, SHA-256 and fetch time. Both are set by environment variables (see [Configuration](#configuration)). `--crawl` leaves robots.txt to crawlee-server's own setting.

## Re-scans and change alerts
`pagevet.rescan.rescan(urls, previous=last_report)` scans the pages and returns the full report (keep it for next time), the findings that are new since `previous`, counts of new, unchanged and no-longer-found findings, and `alert` when a new finding is at or above `alert_on` (default medium). [`integrations/windmill/pagevet_rescan.py`](../integrations/windmill/pagevet_rescan.py) is a ready Windmill script: it keeps the last report in Windmill's state, and a run with new findings fails so the workspace's error handler sends the alert.

## Field studies
```bash
pagevet-discover "query one" "query two" --out urls.txt      # a URL list from a SearXNG instance
pagevet-study run "running shoe shopping pages" --from-json search-results.json --out study/
pagevet-study run "CRM software" --queries queries.txt --via firecrawl --out study/
pagevet-study report study/                                 # rewrite README.md from the saved data
pagevet-study compare docs/bench/*-field-* --out docs/bench/FIELD-STUDIES.md
pagevet-study explore --out site/                           # the explorer page
```
`pagevet-discover` de-duplicates and keeps at most `--max-per-host` pages per site (default 5); `--from-json FILE` takes saved results (`{"query": ["url", ...]}`). `run` builds the URL list (at most four pages per site), scans every page as a browser and as GPTBot, ClaudeBot and PerplexityBot with linked stylesheets read and robots.txt respected, and writes the search results, the list, the raw results and a README whose numbers are all computed from `results.json`. Pages that refuse PageVet are reported as not read and never retried another way. Results so far: [FIELD-STUDIES.md](bench/FIELD-STUDIES.md); the [explorer](EXPLORER.md) shows every record.

## Second opinions (experimental)
A second opinion attaches a model's score to low and medium findings, next to the rule-based severity; it never changes the severity, and a failing model never loses the scan.

| Option | What it runs | Status |
|---|---|---|
| `--second-opinion protectai` | ProtectAI's open DeBERTa classifier, locally (the `classifier` extra; Apache-2.0, not gated) | Measured: [head-to-head](bench/2026-11-25-head-to-head/) (catches more reworded attacks, many more false alarms) |
| `--second-opinion ollama` | a local model through Ollama, quote-checked like `llm` | Experimental, not measured |
| `--second-opinion llm` | any chat model on OpenRouter, asked for the exact words of an instruction aimed at AI; a yes counts only when that quote is in the passage verbatim (billed) | Experimental, not measured |
| `--second-opinion jev` | TypeSafe's Jev decision model, through OpenRouter with `OPENROUTER_API_KEY`, or the TypeSafe SDK (the `jev` extra) (billed) | Experimental, not measured |
| `--second-opinion promptguard` | Llama Prompt Guard 2, locally (the `classifier` extra; gated model under the Llama 4 Community License) | Experimental, not measured |

`pagevet-bench --detector patterns+jev --limit 50 --dry-run` says how many billed calls a measurement would make.

## Tracing: Langfuse and OpenTelemetry
```bash
pagevet --urls urls.txt --compare-agents --langfuse brake-rotors-2026-11   # one trace per page; the run is the session
pagevet-bench cases.jsonl --detector patterns --langfuse                    # one trace per benchmark run
pagevet --otel run-1 --urls urls.txt                                        # one span per page under a run span
```
Langfuse (the `langfuse` extra): each page's trace holds its findings and the scores `max_severity` (0–3), `findings`, `ai_crawlers_refused`, `content_differs` and `read`; a benchmark run records `catch_rate` and `false_alarm_rate`. OpenTelemetry (the `otel` extra): `pagevet.scan` spans with `url.full` and the same numbers, sent wherever the standard `OTEL_*` settings point. Both are best effort and never change a result or exit code; nothing is sent without the flag.

## Benchmark tracking: frozen sets, Langfuse experiments, Pydantic Evals
```bash
uv run python docs/bench/scripts/bench_sets.py build sets/                 # evasion and hiding; add --bipia DIR --deepset FILE --saved-pages FILE --agentdojo
pagevet-bench sets/evasion.jsonl --langfuse-dataset evasion                # this version's run, as the Langfuse experiment "pagevet"
uv run python docs/bench/scripts/bench_sets.py langfuse sets/              # the same for every built set
uv run python docs/bench/evals/run_evals.py sets/ --out evals.json         # the same sets through Pydantic Evals (dev dependency)
```
`bench_sets.py build` freezes each benchmark as `pagevet-bench` cases, one JSONL per set; evasion and hiding come from the scripts in this repository, the others only when their data is supplied (BIPIA checkout, the deepset file, the saved false-alarm pages, AgentDojo installed), and nothing is fetched to fill a gap. Rows from the privately supplied page sample are marked private.

**Langfuse** (`--langfuse-dataset NAME`, the `langfuse` extra and the `LANGFUSE_*` keys): the cases are kept as dataset NAME (items upserted by id) and the run is recorded with the SDK's experiment runner as experiment `pagevet`, run name the PageVet version. Item scores `caught` (attack cases) and `false_alarm` (clean cases), 1 or 0; run scores `catch_rate`, `false_alarm_rate`, `median_ms`, `p95_ms`. Cases are judged and timed one at a time before the runner starts. Item text longer than 20,000 characters, or from a private row, stays local (the item keeps its id, length and SHA-256). Without keys nothing is sent and the command says so; the report and exit code never change.

**Pydantic Evals** ([`docs/bench/evals/`](bench/evals/)): the same sets as `pydantic_evals` cases with three evaluators, expected finding, no false alarm, and latency under a budget (`--budget-ms`, default 50). The patterns run offline. Model second opinions run only with `--models` (names, or `auto`) and when their keys or local service are set; billed ones are capped at `--limit` cases per set.

## Red-team tools (promptfoo, garak, PyRIT)
[`integrations/`](../integrations/) has a promptfoo assertion, a garak detector and a PyRIT scorer that apply PageVet's rules to what a model writes, so a red-team run can check whether generated pages, emails or documents carry instructions for the next AI that reads them. Each was checked against the tool's current release (promptfoo 0.126.0, garak 0.17.1, PyRIT 1.2.1).

## Configuration
Plain scanning needs no settings. The optional sources and second opinions read environment variables, never command-line arguments, so tokens stay out of shell history. Copy [`.env.example`](../.env.example) to `.env` in the folder you run PageVet from, or export the variables; a variable already set in the environment wins over `.env`.

| Setting | Used by |
|---|---|
| `PAGEVET_FIRECRAWL_URL`, `PAGEVET_FIRECRAWL_KEY` | `--via firecrawl` |
| `PAGEVET_CRAWL_URL`, `PAGEVET_CRAWL_TOKEN` | `--crawl` (crawlee-server) |
| `PAGEVET_SEARXNG_URL`, `PAGEVET_SEARXNG_TOKEN` | `pagevet-discover` (a SearXNG instance with JSON output; the token is optional) |
| `PAGEVET_PROTECTAI_MODEL` | `--second-opinion protectai` (default `protectai/deberta-v3-base-prompt-injection-v2`) |
| `OLLAMA_HOST`, `PAGEVET_OLLAMA_MODEL` | `--second-opinion ollama` and `pagevet-replay` (default `http://127.0.0.1:11434` and `llama3.2:3b`) |
| `OPENROUTER_API_KEY` | `--second-opinion jev` and `llm` through OpenRouter (billed) |
| `PAGEVET_LLM_MODEL` | `--second-opinion llm`: an OpenRouter model id, `maker/model` |
| `PAGEVET_JEV_MODEL` | Jev model on OpenRouter (default `~typesafe/jev-latest`) |
| `TYPESAFE_API_KEY`, `TYPESAFE_DEFAULT_MODEL` | `--second-opinion jev` through the TypeSafe SDK instead (billed by TypeSafe) |
| `HF_TOKEN`, `PAGEVET_PROMPTGUARD_MODEL` | `--second-opinion promptguard` (gated model: accept its license on Hugging Face first) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | `--langfuse` on `pagevet` and `pagevet-bench` |
| `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` and other standard `OTEL_*` settings | `--otel` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | `integrations/supabase/load.py` (server-side only: the service-role key bypasses row level security) |
| `HINDSIGHT_URL`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK` | `integrations/hindsight/remember.py` (the key only for Hindsight Cloud; bank default `pagevet`) |

## Safety
Detection only: PageVet does not generate injections. Fetching follows redirects; `fetch(..., allow_private=False)` refuses hosts that resolve to non-public addresses (use it when an agent or untrusted input chooses the URL). Sitemaps are parsed with `defusedxml`, capped at 5 MB, and cannot point the scan at local files.

**robots.txt is respected.** Before fetching a page over http(s), PageVet reads the site's robots.txt (once per site) and skips pages it disallows for the `pagevet` user agent, reporting them as not read. `--ignore-robots` is for your own site.

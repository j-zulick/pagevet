# Changelog

Public releases start at 0.1.0 and count up to 1.0. Everything before the first public release was built in a
private repository as internal versions 0.1.0–0.25.0; they are listed under "Development history" and referred to as
"internal" throughout the docs, so they don't clash with public version numbers.

## [0.5.0] - 2026-11-25
- **Guard between fetch and model:** `pagevet.guard.guard()`, `pagevet-guard` (stdin, file or URL; exit 1 when blocked) and `POST /guard` return the text a person sees, with hidden channels dropped, paragraphs that still match an instruction replaced by a marker, chat markup removed, and `allowed: false` when a finding reaches the policy (`high`, `medium` or `never`). It only removes text.
- **Local HTTP API:** `pagevet-serve` (standard library, loopback by default): `POST /scan`, `POST /guard`, `GET /health`; private addresses refused on every redirect. An importable n8n workflow is in `integrations/n8n/`.
- **Receipts:** every JSON result records what was scanned in `evidence` (SHA-256 of the text read, UTC time, how it was read); `--format receipt` writes a compact receipt (`docs/schema/receipt.schema.json`) with the rules' SHA-256 and each finding's fingerprint, for SourceWatch and other evidence pipelines.
- **Text in images:** `--ocr` reads up to ten images per page (including data URIs) with a local OCR engine (the `ocr` extra, RapidOCR) as a new channel, rated like visible text. OCR's habit of reading "AI" as "Al" is undone before matching.
- **Head-to-head** with ProtectAI's open DeBERTa classifier (`docs/bench/2026-11-25-head-to-head/`): on BIPIA the classifier catches more (2,226 against 1,450 of 3,750) but flags 31 of 50 clean emails against 0; it generalizes far better to new phrasings (172 against 69 of 216 on the second held-out set) and misses more disguised text (162 against 237 of 252). The classifier's false alarms on real pages follow in the next release.
- **Fixed:** splitting text into sentences took quadratic time on a long run of `;` or `!` (about 2 s for 20,000 characters, growing with the square), found by CodeQL once `pagevet-serve` made text from the network reach it. The sentence-end rule now runs in linear time; evasion, hiding, BIPIA and real-page results unchanged.
- **New field study:** password manager buying pages (`docs/bench/2026-11-25-field-password-managers/`): 25 of 38 read, no hidden instructions, 8 refuse at least one AI crawler. Across five studies: no hidden instructions on 238 pages read; 32–43% refuse at least one AI crawler.

## [0.4.0] - 2026-11-25
- **One-command reproduction:** `uv run pagevet-reproduce` (in a checkout) regenerates the evasion report, the hiding-method report and the rules file, and with `--bipia DIR` the BIPIA counts, and fails if any number differs from the committed results. All match for 0.4.0.
- **Newer benchmark:** deepset/prompt-injections, test split (`docs/bench/2026-11-25-deepset/`): patterns catch 2 of 60 chat-prompt injections with 0 of 56 false alarms. A second independent measure of the reworded-instruction gap; built at run time, not copied here.
- **Open-weights classifier:** `--second-opinion protectai` and `pagevet-bench --detector protectai` run ProtectAI's DeBERTa-v3 prompt-injection classifier (Apache-2.0, not gated) locally over 512-token windows; the positive class is read from the model's labels. The head-to-head with patterns follows in 0.5.0.
- **OpenTelemetry:** `--otel [RUN]` sends one span per page under one run span (the `otel` extra, standard `OTEL_*` settings). Best effort.
- **Field studies over time:** the four field studies repeated on their committed search results (`docs/bench/2026-11-25-repeat-*`, `docs/bench/FIELD-STUDIES-OVER-TIME.md`): still no hidden instructions on 206 pages read; 26–41% refuse at least one AI crawler. One high finding is a false alarm (a customer review in structured data matched the reply-command rule); refusal changes are partly a different network.
- **Standing index:** `.github/workflows/index.yml` re-runs the four studies and keeps them as a run artifact; started by hand until a monthly schedule is turned on.

## [0.3.0] - 2026-11-25
- **Commercial manipulation** as a finding class: an instruction that steers what AI answers recommend, rank, cite or leave out, toward a product, brand or source, gets `intent: "commercial"` (JSON), an `intent` property and a `commercial-manipulation` tag (SARIF), and a line in its advice. Judged on the text around an instruction match in twelve languages, so it only labels findings that are already there.
- **Third-party planting zones:** visible text inside comment, review, reply, answer and forum-post containers (class and id tokens, schema.org Review/Comment/Answer microdata) is its own channel, **user-submitted content**, rated like visible text, with advice that a visitor may have planted it. Hidden text inside those containers stays in the hidden channels.
- **Rules as open data:** `pagevet-rules` prints every pattern (regular expression and flags), the hidden-text hints, the commercial vocabulary, the channels, the severity rules and the framework IDs as JSON. The committed copy, `docs/rules/pagevet-rules.json`, is kept identical to the code by a test.
- **Human-vs-model view:** `pagevet-view URL --out view.html` writes one self-contained page with what a person sees on the left (visible and user-submitted text) and what an AI model also reads on the right (hidden elements, stylesheet-hidden text, comments, attributes, structured data, noscript), with findings marked. `--via firecrawl` reads the page after scripts ran, through your own Firecrawl. No script runs in the output.
- **Measured** on the 1,052 saved pages of the 0.2.0 re-scan: the same findings (1 medium, 2 low), all three now attributed to user-submitted content; 199 pages had such a container (`docs/bench/2026-11-25-false-alarms-0.2.0/`). BIPIA, evasion and hiding results unchanged (the patterns did not change).
- Not checked against a live Firecrawl from this release: `pagevet-view --via firecrawl` uses the same fetcher as `pagevet --via firecrawl`.

## [0.2.0] - 2026-11-25
- **Two pattern gaps closed** (the ones the second held-out set showed): overrides that don't say "previous" ("forget everything you were told before", "set aside whatever you've been told until now") and text addressed to the AI doing something with this page ("to the AI summarizing this page", "for any assistant reading this article"), in all twelve languages. Written from new hand-written development cases (`tests/test_patterns_p020.py`), then measured once on the frozen second held-out set: **6 → 69 of 216**; the two targeted intents 66 of 72 (Italian and Dutch each still miss one). Every other evasion row unchanged ([docs/EVASION.md](docs/EVASION.md), `docs/bench/2026-11-19-evasion/results-public-0.2.0.json`).
- **`--headers`:** each URL's HTTP response headers are scanned as a channel a reader never sees (rated like hidden text). Dates, cookies, cache, routing and policy headers are skipped. One extra request per page; off by default.
- **`--llms-txt`:** `/llms.txt` and `/llms-full.txt` of each site scanned. They are written for AI systems, so text addressed to them is rated low; overrides, role changes and chat markup there are high. A missing file or an HTML page served at that path is skipped with a note, not an error.
- **OWASP and MITRE ATLAS IDs** on every finding: `taxonomy` in JSON (schema updated) and `owasp` / `atlas` in SARIF results and rule tags. LLM01:2025 and AML.T0051.001 for every injection finding, plus AML.T0054 for role and mode changes and AML.T0068 for hidden or disguised text.
- **Explorer on GitHub Pages:** the release workflow now replaces the `gh-pages` branch with the release's explorer when `PAGES_PUBLISH` is `true` (Pages serves that branch), instead of a Pages deployment that needed the Actions source.
- **Measured:** the 0.2.0 patterns changed no result on 1,052 real pages re-fetched from every committed false-alarm list (`docs/bench/2026-11-25-false-alarms-0.2.0/`); BIPIA unchanged (1,450 of 3,750 injected cases, 0 of 50 clean); hiding report unchanged. Scan time about 1.27× 0.1.0's on the same saved pages.
- **Caveat:** the person who wrote the development cases and patterns had seen some of the frozen set (the English, Spanish, French and German rows), so treat the held-out figure as optimistic.
- Pattern changes to offer Crossvet: `_ADDRESSED_P020` and `_OVERRIDE_P020` in `detect.py`.

## [0.1.0] - 2026-11-25
First public release. Everything below, from the development history, ships in it:
- **Scanner** (`pagevet`): finds text aimed at AI models in visible text, hidden elements (30+ hiding methods, including the page's own and linked stylesheets with descendant, child and attribute selectors), HTML comments, attributes and meta tags, JSON-LD, noscript, templates, SVG text, hidden inputs and PDFs. Undoes look-alike letters, invisible characters, letter spacing, ROT13, reversed text, split sentences, invisible Unicode tags and base64. Patterns in twelve languages (English, Spanish, French, German, Portuguese, Italian, Dutch, Polish, Swedish, Russian, Japanese, Chinese). Severity with advice; `--compare-agents`, `--baseline`, `--fetch-css`; text, JSON, CSV, HTML and SARIF output; robots.txt respected.
- **`pagevet-access`:** which of fourteen AI crawlers may read a page (robots.txt per RFC 9309, meta tags, X-Robots-Tag, noai and TDM signals, llms.txt) and which the server actually serves (firewall-refusal probes); `--require` CI gate.
- **Field studies and the explorer:** `pagevet-discover`, `pagevet-study` (run, report, compare) and `pagevet-study explore`, a self-contained faceted HTML page over every committed field-study page, false-alarm page and benchmark case, with checkable headline numbers.
- **Integrations:** GitHub Action (SARIF), MCP server (`scan_page`, `check_ai_access`), container image on GHCR, pre-commit hook, Python API ([docs/API.md](docs/API.md)), your own Firecrawl and crawlee-server as sources, optional Prompt Guard 2 / Jev / `llm` second opinions and Langfuse records.
- **Measured** (data, script and date for each in `docs/bench/`): 0 of 974 real pages read in five false-alarm sets flagged at medium or high; BIPIA 1,450 of 3,750 injected cases caught, 0 of 50 clean; evasion report with frozen held-out sets ([docs/EVASION.md](docs/EVASION.md)); four field studies: no hidden instructions on 213 pages read, 35–43% refuse at least one AI crawler.

## Development history (internal builds, not released)

### internal 0.25.0 (2026-11-25)
- **Field-study explorer** (`pagevet-study explore [STUDY_DIRS...] --out site/`): one self-contained, deterministic HTML page over the committed data: 289 field-study pages, 1,217 false-alarm records (five plain-HTTP sets in twelve languages, plus the pages plain HTTP could not read retried through crawlee-server) and 1,134 evasion cases, plus BIPIA totals. Disjunctive facet counts, free-text search, filter state in the URL, a page drawer with evidence and re-check commands, a headline bar (pages read, text aimed at AI with a Wilson 95% interval, share refusing AI crawlers) recomputed for every filter, a compare view (two studies; two PageVet versions on identical bytes), "reproduce this view" commands, and provenance (version, commit, run dates, record count, data SHA-256). Strict CSP with hashed inline script and style; data rendered with `textContent`; the page verifies its data hash and fails closed. 1.6 MB. [docs/EXPLORER.md](docs/EXPLORER.md).
- **One source for the published numbers:** with no filter the explorer's headline equals `docs/bench/FIELD-STUDIES.md` and the README (213 pages read, no hidden instructions, 35–43% refuse at least one AI crawler); a test ties all three to `summarize`.
- **Releases** attach `explore.html`; GitHub Pages publishes it when the repository variable `PAGES_PUBLISH` is `true`. Each field study's README links to its filtered view.
- **Tests:** Python reference counts for eleven filter combinations, checked against the page in Chrome (Playwright, a test-only dependency group; no runtime dependency); byte-identical builds; no CSP violations or console errors; URL state round-trips; tampered data and unknown schema fail closed; planted markup renders as text; the private sample never appears; the compare, About, drawer, reproduce and paging views work in Chrome. Mutation-checked: breaking disjunctive counting or folding unread pages into clean makes the tests fail.

### internal 0.24.0 (2026-11-25)
- **`pagevet-access`:** which of fourteen AI crawlers may read a page, and which actually can. Three groups (training, search, fetch on request). robots.txt parsed per RFC 9309 (groups by product token, longest match, `allow` wins a tie, `*` and `$`; a 4xx robots.txt allows everything, a 5xx or unreachable one disallows everything); `robots` and per-crawler meta tags, `X-Robots-Tag`, `noai` and TDMRep reservations; `/llms.txt` and `/llms-full.txt`; and probes that request the page with each crawler's user agent, reporting a crawler robots.txt allows but the server refuses as a firewall refusal. Text, JSON, CSV and Markdown. `--require TARGET=allowed|refused` makes it a CI gate. MCP tool `check_ai_access`.
- **Five more languages:** Polish, Swedish, Russian, Japanese and Chinese, for overrides, text addressed to an AI, role changes, commands about the reply and instructions to omit. Japanese and Chinese patterns have no word boundaries and anchor on fixed phrases.
- **Split instructions:** a sentence that ends on a word no sentence ends on ("and", "the", "your" and their equivalents in the twelve languages) is joined to the next before matching.
- **Stylesheet hiding rules** with descendant, child and attribute selectors (`.promo .note`, `.promo > p`, `[data-role="ai"]`, `div[class^="sr-"]`); pseudo-classes and sibling combinators are skipped, never guessed.
- **Rendering stays with your own services.** Text added by JavaScript is read through Firecrawl (`--via firecrawl`) or crawlee-server (`--crawl`), both Playwright-based; PageVet bundles no browser.
- **Container image** on GHCR (`ghcr.io/j-zulick/pagevet`, amd64 and arm64, non-root, with provenance and SBOM), built by the release workflow and smoke-tested in CI. **Pre-commit hook** (`.pre-commit-hooks.yaml`). **[Python API guide](docs/API.md).**
- **Measured** (EVASION.md, `docs/bench/2026-11-24-pages-12-languages/`): held-out sets frozen first (commit `7ddc24c`): held-out translations in the five new languages 0 → 54 of 90; second held-out set (new phrasings in all twelve languages) 0 → 6 of 216; split into two capitalized sentences, development 15 → 18, held-out 12 → 12 of 18. False alarms: 0 of 368 real pages in twelve languages flagged at any severity (random Wikipedia articles and news pages, `docs/bench/2026-11-24-pages-12-languages/`). BIPIA unchanged (1,450 of 3,750 injected cases, 0 of 50 clean). Hiding report unchanged on all 21 methods. Scan time: about 2.1× internal 0.23.0's on the same 368 saved pages (median 115 ms against 53 ms per page).
- Pattern changes to offer Crossvet: `_AI_PL`, `_AI_SV`, `_AI_RU`, `_AI_JA`, `_AI_ZH`, `_ADDRESSED_V24`, `_OVERRIDE_V24`, `_ROLE_V24`, `_RESPONSE_V24`, `_OMIT_V24` and `DANGLING` in `join_fragments`, all in `detect.py`.

### internal 0.23.0 (2026-11-24)
- **`pagevet-study`:** `run` builds a topic's URL list (saved results or SearXNG), scans it as a browser and as three AI crawlers with stylesheets read and robots.txt respected, and writes the study folder; `report` regenerates its README from `results.json`, keeping the hand-written notes; `compare` puts several studies in one table.
- **Three more field studies** (`docs/bench/2026-11-23-field-running-shoes/`, `-crm/`, `-home-solar/`) and a cross-study table (`docs/bench/FIELD-STUDIES.md`). Running shoes: 96 pages, 72 read, no hidden instructions, 25 refuse at least one AI crawler (22 all three). Small-business CRM software: 48 pages, 42 read, none, 18 refuse at least one (16 all three). Home solar: 43 pages, 32 read, none, 13 refuse at least one (8 all three), with ClaudeBot refused on 11 pages against 6 for each of the others. Across the four studies: no hidden instructions on 213 pages read; 35–43% of readable pages refuse at least one AI crawler.
- **Release scripts** read the version from `pyproject.toml` instead of a fixed number.
- **First public release.** Installs from GitHub (`uv tool install "git+https://github.com/j-zulick/pagevet@v0.23.0"`); the README's install lines, and the message shown when an optional extra is missing, give commands that work without PyPI. Every command takes `--version`; `pagevet` with no arguments prints the full help. Releases attach the wheel and source archive, and the PyPI upload runs only when the repository variable `PYPI_PUBLISH` is `true`, so a release no longer ends with a failed run. Workflow actions are pinned to commits, checkouts don't keep credentials, and Dependabot keeps actions and dependencies current. `SECURITY.md`, `CONTRIBUTING.md` and issue forms for missed injections and false alarms.

### internal 0.22.0 (2026-11-23)
- **Langfuse records** (`pip install "pagevet[langfuse]"`, `--langfuse [RUN]`): each scanned page becomes a trace in session RUN, with its findings and the scores `max_severity`, `findings`, `ai_crawlers_refused`, `content_differs` and `read`; `pagevet-bench --langfuse` records a run's catch and false-alarm rates. Best effort: never changes a result or exit code. Tested with a stand-in client; not yet sent to a real project.

### internal 0.21.0 (2026-11-23)
- **Jev through OpenRouter:** with `OPENROUTER_API_KEY` set, `--second-opinion jev` and `--detector jev` call Jev through OpenRouter's Decisions API (alpha), with no extra install; the TypeSafe SDK remains the path without that key. `PAGEVET_JEV_MODEL` (default `~typesafe/jev-latest`).
- **`llm` second opinion:** any chat model on OpenRouter (`PAGEVET_LLM_MODEL`) is asked for the exact words of an instruction aimed at AI; code flags only when that quote is in the passage verbatim.
- **`pagevet-bench --limit N` and `--dry-run`:** trial a billed detector on a few cases, or count the billed calls first.
- **README:** two stale limits corrected (short split fragments are caught since internal 0.11.0; linked stylesheets are read with `--fetch-css` since internal 0.9.0).
- Not run against the real services yet.

### internal 0.20.0 (2026-11-19)
- **`pagevet-discover`:** builds a `--urls` list from search queries, through a SearXNG instance (`PAGEVET_SEARXNG_URL`, optional `PAGEVET_SEARXNG_TOKEN`) or from saved results (`--from-json`). De-duplicates, caps pages per site, and records each query in the list.
- **First field study:** ten front-brake-rotor shopping queries, 102 pages, 67 read (`docs/bench/2026-11-19-field-brake-rotors/`). No hidden instructions found. 27 readable pages refused at least one AI crawler (22 refused all three), three with 402 Payment Required; two pages served ClaudeBot text that differed from the browser's copy.
- **Maintenance:** locked dependencies refreshed (patch releases only); workflows use `actions/checkout@v7` and `astral-sh/setup-uv@v6`.
- **Fixed:** the repetition check could run for more than 20 seconds on a page with millions of characters of text. It now judges the first 20,000 words and skips sentences whose opening words can't recur often enough; a test covers the case. No pattern change.

### internal 0.19.0 (2026-11-19)
- **Italian and Dutch.** Overrides, text addressed to an AI, role changes, commands about the reply and instructions to omit. Evasion report: development 0 → 18 of 18 in each language; a held-out set frozen first (commit `5e303d4`), 0 → 9 of 18 in each.
- **False alarms:** 0 of 100 fresh Italian and Dutch pages (`docs/bench/2026-11-19-it-nl-pages/`); English, the other four languages and BIPIA unchanged.
- Pattern change to offer Crossvet: `_AI_IT`, `_AI_NL` and the Italian and Dutch additions in `detect.py`.

### internal 0.18.0 (2026-11-19)
- **Linear stylesheet parser.** The regex version could take tens of seconds on a malformed or hostile stylesheet (12 s on a 40 KB slice of a real one). The new one makes one pass, skips quoted strings and escapes, reads `@layer` and `@supports` blocks, skips other at-rule blocks at any depth, and caps nesting. On identical CSS it agrees with the old one on 233 of 264 pages; the rest were rules inside `@media` blocks the old regex wrongly applied to the whole page.
- **New channel, "hidden by stylesheet rules":** text that only stylesheet rules hide. It is rated like hidden elements, except that a reply command alone is medium, because collapsed reply forms and dialogs match it. In the hiding report, the two stylesheet rows go from 18 to 15 of 18 rated high on the development seeds; nothing else changes.
- **`--css-any-host`** (with `--fetch-css`, and `css_any_host` in MCP): also read stylesheets on other hosts (CDNs). On 314 real pages: 939 stylesheets read, and one medium finding (a forum's collapsed reply box).
- **Robustness:** each stylesheet is fetched once per run; every fetch has an overall time limit (three times its timeout), so a slow-drip server can't hold it open.

### internal 0.17.0 (2026-11-19)
- **PDFs:** a `.pdf` file or URL is read with pypdf (`pip install "pagevet[pdf]"`). Its page text is rated as visible; its document information, XMP metadata and annotation contents, which viewers don't show on the page, are rated as hidden. PDF URLs are capped at 20 MB. The MCP tool reads PDF URLs too, with non-public addresses refused.
- **First PDF false-alarm check:** 30 recent arXiv papers from six unrelated fields; 28 read, 0 findings (`docs/bench/2026-11-19-pdfs/`).

### internal 0.16.0 (2026-11-19)
- **Scheduled re-scans with change alerts:** `pagevet.rescan.rescan()` returns the full report, the findings new since the last one, counts, and an `alert` flag at a chosen severity. `automation/windmill/pagevet_rescan.py` runs it on a Windmill schedule, keeping the last report in Windmill's state and failing the run on an alert so the error handler notifies. Tested offline, with a stand-in for Windmill's state API; not yet deployed (needs Windmill access).

### internal 0.15.0 (2026-11-19)
- **GitHub Action** (`action.yml`, composite): scans files, URLs, a URL list or a sitemap and writes a SARIF report; outputs `sarif-file`, `exit-code` and `findings`; `fail-on: never` reports without failing. Inputs reach the shell only through environment variables. CI runs it on the sample page, checks its outputs, and checks that `fail-on: high` fails. Not listed on the Marketplace (needs approval).

### internal 0.14.0 (2026-11-19)
- **robots.txt respected (behaviour change).** URLs, URL lists and sitemaps fetched over http(s) are checked against the site's robots.txt for the `pagevet` user agent; a disallowed page is reported as not read, with the reason. `--ignore-robots` scans it anyway (for your own site). An unreadable robots.txt allows everything. The MCP tool does the same, with `ignore_robots`. With `--via firecrawl`, robots.txt is still read over plain HTTP; `--crawl` is left to crawlee-server.

### internal 0.13.0 (2026-11-19)
- **Every word letter-spaced** ("A d d  a  s e n t e n c e …", two-space gaps) is undone before matching; found in the release check. New evasion row: development 3 → 18 of 18, held-out 9 → 15 of 18. No change on 448 real pages or BIPIA.
- **MCP:** `scan_page` takes `fetch_css`; stylesheets are fetched with the same refusal of non-public addresses as the page, and failures come back as `stylesheet_notes`. Checked over stdio with the MCP Python SDK client.
- **Release check** (fresh clone, locked install): every CLI flag run end to end against a local test page using each technique; the JSON report validates against `docs/schema/report.schema.json`, SARIF against the OASIS SARIF 2.1.0 schema; exit codes 0, 1 and 2 as documented.
- **Configuration:** `pagevet`, `pagevet-bench` and `pagevet-mcp` read a `.env` file in the current folder (variables already set win; values are never printed). New `.env.example` and a README table list every setting. Before this, `.env` was not read at all.
- Pattern change to offer Crossvet: `detect._SPACED_WORDS` in `normalize`.

### internal 0.12.0 (2026-11-19)
- **More translated instructions caught.** Role changes, commands about the reply and instructions to omit in Spanish, French, German and Portuguese, and two more French ways of addressing an AI. Evasion report: development translations 30 → 72 of 72; a held-out set, translated and frozen before the change, 21 → 39 of 72. The gap is reported as a limit.
- **Non-English false-alarm check:** 0 of 134 fresh Spanish, French, German and Portuguese pages flagged (`docs/bench/fresh_pages_intl.py`, `docs/bench/2026-11-19-intl-pages/`). English pages and BIPIA unchanged.
- Pattern change to offer Crossvet: `_ROLE_INTL`, `_RESPONSE_INTL`, `_OMIT_INTL` and the French additions in `detect.py`.

### internal 0.11.0 (2026-11-19)
- **Instructions split into short fragments caught.** A sentence of four words or fewer, or one followed by a lower-case start, is joined to the next and the patterns are tried again; matches are `split:…`, rated like the plain kind (not escalated in visible text). Evasion report: development 9 → 18 of 18, held-out 3 → 15 of 18 (the undisguised level), developed without looking at the held-out set.
- False alarms: no change on 314 real pages or BIPIA's 50 clean emails; BIPIA catch rate unchanged.
- Pattern change to offer Crossvet: `detect.join_fragments` and the `split:` step in `detect.scan`.

### internal 0.10.0 (2026-11-19)
- **Letter-spaced instructions caught.** When text has 12 or more letters in letter-spaced runs, relaxed copies of the patterns (spaces optional, no word boundaries) are tried on the joined text; matches are `obfuscated:…`, rated high. Evasion report: development seeds 9 → 18 of 18, held-out 3 → 15 of 18 (the undisguised level), developed without looking at the held-out set.
- False alarms: no change on 314 real pages (the rule ran on 6 of them) or on BIPIA's 50 clean emails; BIPIA catch rate unchanged.
- Pattern change to offer Crossvet: `detect.RELAXED_PATTERNS`, `detect.spaced_letters` and the step in `detect.scan`.

### internal 0.9.0 (2026-11-19)
- **`--fetch-css`:** for each fetched page, also read its linked stylesheets on the same host (up to 5, 1 MB each; `@import` not followed) and apply their hiding rules to the whole page. Off by default. A stylesheet that can't be read is a note on stderr; the page is still scanned.
- On 314 real pages: 485 stylesheets read, 2.2 times as much hidden text seen, findings unchanged (`docs/bench/2026-11-19-hiding/`).

### internal 0.8.0 (2026-11-19)
- **More hiding methods recognised.** Now rated as concealed: `color:transparent` (not gradient text), `transform:scale(0)`, `clip-path:inset(50%|100%)` and `circle(0)`, zero width with `overflow:hidden`, 1px or sub-0.3em font sizes, opacity below 0.1, off-screen positions to the right or bottom and in `em`. These apply to inline styles and the page's own stylesheet.
- **New hidden channels:** `<template>` content (never rendered; previously skipped), SVG `<title>`/`<desc>`/`<metadata>`, and the values of `<input type="hidden">`.
- **Fewer false "hidden" ratings:** `min-height:0`, `min-width:0` and `line-height:0` with `overflow:hidden` no longer count as hidden.
- **Hiding-method report** (`docs/bench/hiding_run.py`, `docs/bench/2026-11-19-hiding/`): 18 new methods went from 0 to 18 of 18 rated high (15 of 18 held-out, the undisguised level). Not blind: the rules were written for these methods. On 314 real pages, findings are unchanged and 29% more hidden text is read.
- Rule changes to offer Crossvet: the hiding styles and channels above (`scan.hides`, `_Splitter`).

### internal 0.7.0 (2026-11-19)
- **`--baseline FILE`:** compare with an earlier JSON report and keep only new findings, so the report and exit code cover what changed; stderr counts new, unchanged and no-longer-found findings. The groundwork for scheduled re-scans with change alerts.
- **SARIF:** each result carries `partialFingerprints` (`pagevet/v1`) so code scanning can track it across runs; with `--baseline`, `baselineState: new`.
- **Blind false-alarm check** on 211 fresh article, forum, Q&A and issue pages from ten public feeds (`docs/bench/fresh_pages.py`, `docs/bench/2026-11-19-fresh-pages/`): 181 read, 0 flagged at medium or high, 1 low (a Hacker News comment mentioning Claude). No rule changed after the run.
- Pattern changes to offer Crossvet: none.

### internal 0.6.0 (2026-11-19)
- **crawlee-server modes:** `--crawl-mode page|crawl|sitemap|map`; `sources.crawl` takes up to ten start URLs, matches redirected pages by host, and can return crawlee-server's failure reasons.
- **Verified against real crawlee-server code** (2.2.0, run locally): the 94 pages plain HTTP could not read were retried through it; 21 more were read, none with findings (`docs/bench/2026-11-19-crawlee/`). Two crawlee-server issues noted there, not changed from here.
- `docs/bench/crawlee_run.py` for scanning a URL list through crawlee-server.

### internal 0.5.0 (2026-11-19)
- **Stylesheet-hidden text counts as hidden.** Rules in the page's own `<style>` blocks that hide an element (`display:none`, off-screen, zero size…) are applied to simple selectors (`.a`, `#b`, `div.a`); rules inside `@media` and complex selectors are skipped. External stylesheets are not fetched.
- **MCP server** (`pip install "pagevet[mcp]"`, `pagevet-mcp`): one tool, `scan_page`, for a public URL or pasted HTML; non-public addresses are refused on every redirect. Written for MCP Python SDK 2.x and checked end to end over stdio.
- **Second real-page sample:** 165 article, forum and listing pages supplied by the maintainer (URLs not published). 133 readable: 0 flagged at medium or high, 1 low false alarm (a forum reply box). Re-run with internal 0.5.0: unchanged. Homepage set re-run with internal 0.5.0: 0 of 193.

### internal 0.4.0 (2026-11-19)
- **Evasion report** (`docs/EVASION.md`, `docs/bench/evasion_run.py`): 17 disguises × 6 seeds × 3 invented brands, plus a held-out seed set frozen before any fix.
- **Disguises undone before matching:** invisible characters, look-alike Cyrillic/Greek letters, letter spacing, ROT13, reversed text. Matches found only this way are marked `obfuscated:` / `rot13:` / `reversed:` and rated high. On the held-out set, five disguises went from 0 caught to 15 of 18 (the undisguised level).
- **Text split across inline elements** is read as one run (joined with a space); block elements still separate text.
- Clean pages re-fetched with internal 0.4.0: 0 of 193 flagged. BIPIA unchanged.
- Pattern changes to offer Crossvet: the disguise handling in `detect.scan` and `detect.normalize`.

### internal 0.3.0 (2026-11-19)
- **Detector interface** (`pagevet.detectors`) with two optional second opinions: Llama Prompt Guard 2 run locally over overlapping 512-token windows (`pip install "pagevet[classifier]"`), and Jev through the TypeSafe SDK (`pip install "pagevet[jev]"`, billed by TypeSafe). Both are tested with stand-ins only; neither has been run against its real model yet.
- `pagevet --second-opinion promptguard|jev` attaches a score to low and medium findings; it never changes severity, and a failing layer never loses the scan. `pagevet-bench --detector` compares detectors on the same cases (`patterns+promptguard` flags when either does).
- **False-alarm measurement** on 194 ordinary pages (`docs/bench/2026-11-19-clean-pages/`): internal 0.2.0 flagged 21, all by the repetition rule and all boilerplate. Repetition-only findings are now off by default (`--include-repetition` restores them); with that, 0 of 194.
- Pattern change to offer Crossvet: none. Rule change to offer Crossvet: the repetition rule's false alarms (see the results README).

### internal 0.2.0 (2026-11-19)
- **Sources:** `--via firecrawl` (rendered HTML through a Firecrawl service) and `--crawl` (a crawlee-server crawl with page capture; results carry capture id, SHA-256 and fetch time).
- **`pagevet-bench`:** catch rate and false-alarm rate on labelled text, with Wilson intervals.
- **First measurement:** BIPIA text attacks, 29 of 75 caught, 0 of 50 false alarms (`docs/bench/2026-11-19-bipia/`).
- **New pattern `response_directive`** (commands about the reader-model's own reply), rated low in visible text.
- JSON report schema (`docs/schema/report.schema.json`), validated in tests.
- Not verified against live Firecrawl or crawlee-server instances: both sources are tested against stand-ins that follow their documented APIs.

### internal 0.1.0 (2026-11-19)
First iteration. Scanner, channels (visible, hidden elements, comments, attributes and meta, JSON-LD, noscript), multilingual patterns, invisible-Unicode and base64 decoding, repetition rule, severity with advice, `--compare-agents`, `--fail-on`, text/JSON/CSV/HTML/SARIF reports, sitemap and URL-list scans. Not published.

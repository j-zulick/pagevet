# False alarms on fresh article and user-content pages (Nov 19, 2026)

**Question.** How often do PageVet's default rules flag ordinary pages that are not homepages: articles, forum threads, Q&A pages and issue trackers? These pages hold long prose and text written by users, which is where pattern rules are likeliest to fire by mistake.

**Why this set is independent.** The earlier false-alarm figures came from homepages, and the repetition rule was switched off after looking at those results, so they are not blind. This list was built afterwards by `docs/bench/fresh_pages.py`, which takes the current entries from ten public, keyless feeds (random Wikipedia articles, Hacker News front-page threads, Stack Overflow active questions, the latest topics on discuss.python.org and meta.discourse.org, BBC, NPR and Guardian RSS, the latest dev.to articles, recent python/cpython GitHub issues). No URL was chosen by hand, and none was seen while the rules were written. No rule was changed after this run.

**Setup.**
- **Detection:** PageVet's default rules as in internal 0.6.0 and internal 0.7.0. The run used a checkout at commit `615257f`, whose detection code is identical to both releases (only the version string differs).
- **Fetching:** plain HTTP with `docs/bench/clean_pages.py`, robots.txt respected. Pages it could not read were retried through crawlee-server 2.2.0 run locally (`docs/bench/crawlee_run.py`, `mode: page`, robots.txt respected).
- **Files:** `urls.txt` (211 URLs), `results-http-0.6.jsonl`, `results-crawlee-2.2.0.jsonl`. Each line keeps the URL, outcome, SHA-256 of the body and any findings, not page copies.

## Result
| | Pages |
|---|---|
| Listed | 211 |
| Read (plain HTTP 177, crawlee-server 4) | **181** |
| Not read: Stack Overflow, 403 to plain HTTP and robots.txt disallows for crawlee-server | 30 |
| Flagged medium or high | **0** (95% Wilson interval 0–2.1%) |
| Flagged at any severity | 1 (0.6%; 95% interval 0.1–3.1%) |

| Source | Read |
|---|---|
| Wikipedia | 30 of 30 |
| Hacker News | 30 of 30 (4 after a retry, 503 at first) |
| discuss.python.org, meta.discourse.org | 30 of 30 |
| BBC, NPR, Guardian | 41 of 41 |
| dev.to (2 redirected to blog.mlh.com) | 30 of 30 |
| GitHub issues | 20 of 20 |
| Stack Overflow | 0 of 30 |

**The one finding** is a low-severity `addressed_to_ai` match in the visible text of a Hacker News thread: a commenter jokes about shouting voice instructions to Claude. It is a person talking about an AI, not text aimed at one, so it counts as a false alarm. PageVet rated it low, which keeps it out of `--fail-on medium`.

## Limits
- 181 pages bound the medium-or-high false-alarm rate below about 2% at 95% confidence; they cannot show it is far lower.
- English-language pages only. Stack Overflow, a large source of user-written text, could not be read without ignoring robots.txt.
- Feeds change by the minute; re-running `fresh_pages.py` gives a different list. The hashes record what was scanned.

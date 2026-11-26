# Field study: password manager buying pages (2026-11-25)

Pages a web search returns for password manager buying pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=password+manager+buying+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (4):** best password manager for families; password manager comparison review; best password manager for small business; free password manager vs paid.
- **Search results:** 39 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 38 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet pre-release (2026-11-25), `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 38 |
| Read | 25 |
| Not read: HTTP 403 | 11 |
| Not read: HTTP 404 | 2 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- None found on the 25 pages read.

**AI crawlers refused:** 8 of 25 (32%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 3 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 403 | 7 | 3 | 8 |

**Different content for an AI crawler:** 0 page(s) served a crawler visible text under 90% similar to the browser's copy.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
(not written yet)
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 38 URLs. A field sample, not a census.
- **Unread pages:** 13 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

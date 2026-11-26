# Field study: home solar panel pages (2026-11-25)

Pages a web search returns for home solar panel pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=home+solar+panel+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (5):** best solar panels for home 2026; home solar panel installation cost; best solar companies near me reviews; are solar panels worth it for homeowners; solar lease vs buy solar panels.
- **Search results:** 43 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 43 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet pre-release (2026-11-25), `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 43 |
| Read | 31 |
| Not read: HTTP 403 | 7 |
| Not read: HTTP 404 | 3 |
| Not read: robots.txt disallows PageVet | 2 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- None found on the 31 pages read.

**AI crawlers refused:** 12 of 31 (39%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 6 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 403 | 5 | 10 | 5 |
| HTTP 429 | 1 | 1 | 1 |
| timeout | 1 | 0 | 1 |

**Different content for an AI crawler:** 3 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://bobvila.com/articles/cost-of-solar-panels`, `https://www.bobvila.com/articles/are-solar-panels-worth-it/`, `https://www.bobvila.com/articles/best-solar-companies/`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
(not written yet)
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 43 URLs. A field sample, not a census.
- **Unread pages:** 12 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

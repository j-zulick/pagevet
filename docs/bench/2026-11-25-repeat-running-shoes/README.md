# Field study: running shoe shopping pages (2026-11-25)

Pages a web search returns for running shoe shopping pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=running+shoe+shopping+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (8):** best running shoes 2026; running shoes sale; best running shoes for beginners; best trail running shoes review; running shoes for flat feet; best marathon racing shoes carbon plate; where to buy running shoes online cheap; running shoe buying guide how to choose.
- **Search results:** 100 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 96 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet 0.3.0, `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 96 |
| Read | 70 |
| Not read: HTTP 403 | 14 |
| Not read: timeout | 4 |
| Not read: HTTP 404 | 4 |
| Not read: HTTP 406 | 3 |
| Not read: HTTP 410 | 1 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- None found on the 70 pages read.

**AI crawlers refused:** 22 of 70 (31%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 11 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 402 | 1 | 1 | 1 |
| HTTP 403 | 15 | 9 | 14 |
| HTTP 429 | 4 | 4 | 4 |

**Different content for an AI crawler:** 6 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://time.com/shopping/article/best-trail-running-shoes`, `https://www.dsw.com/content/running-shoe-guide`, `https://www.footlocker.com/category/sport/running/sale/shoes`, `https://www.nike.com/a/best-running-shoes-for-flat-feet`, `https://www.nike.com/a/buy-right-running-shoes`, `https://www.nike.com/a/how-to-pick-the-right-running-shoes`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
(not written yet)
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 96 URLs. A field sample, not a census.
- **Unread pages:** 26 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

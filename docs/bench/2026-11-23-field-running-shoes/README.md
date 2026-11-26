# Field study: running shoe shopping pages (2026-11-23)

Pages a web search returns for running shoe shopping pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=running+shoe+shopping+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (8):** best running shoes 2026; running shoes sale; best running shoes for beginners; best trail running shoes review; running shoes for flat feet; best marathon racing shoes carbon plate; where to buy running shoes online cheap; running shoe buying guide how to choose.
- **Search results:** 100 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 96 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet pre-release (2026-11-23), `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 96 |
| Read | 72 |
| Not read: HTTP 403 | 11 |
| Not read: HTTP 404 | 4 |
| Not read: HTTP 406 | 3 |
| Not read: timeout | 3 |
| Not read: HTTP 429 | 1 |
| Not read: other error | 1 |
| Not read: HTTP 410 | 1 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- None found on the 72 pages read.

**AI crawlers refused:** 25 of 72 (35%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 22 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 402 | 1 | 1 | 1 |
| HTTP 403 | 18 | 20 | 17 |
| HTTP 429 | 4 | 4 | 4 |

**Different content for an AI crawler:** 3 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://time.com/shopping/article/best-trail-running-shoes`, `https://www.dsw.com/content/running-shoe-guide`, `https://www.footlocker.com/category/sport/running/sale/shoes`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
- **No hidden instructions** on any of the 72 pages read, in any channel, as in the brake-rotor study.
- **Access is the gap.** About a third of the readable pages refuse at least one AI crawler, and nearly all of those refuse all three. Most refusals are 403s; one review site answered 402 Payment Required, which looks like pay-per-crawl. An assistant using one of these crawlers answers from other pages.
- **Three pages served a crawler different text:** two retailer pages and one buying guide. Rotating product modules could explain this; the study did not check which.
- **A search-result oddity:** some result URLs carried a `utm=airanks.net` tracking parameter, which names another site rather than the publisher. PageVet scanned the pages as listed; the tag itself is outside what PageVet checks.
- **How it was run:** the 96 URLs were scanned in 16 parallel batches with the flags above, because the scanning machine stops any command after three minutes. At most four pages came from one site.
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 96 URLs. A field sample, not a census.
- **Unread pages:** 24 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

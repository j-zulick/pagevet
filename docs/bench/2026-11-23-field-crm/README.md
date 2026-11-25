# Field study: small-business CRM software pages (2026-11-23)

Pages a web search returns for small-business CRM software pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=small-business+CRM+software+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (6):** best CRM software for small business; CRM software pricing comparison; free CRM for startups; HubSpot vs Salesforce vs Pipedrive; CRM software reviews 2026; how to choose a CRM for sales team.
- **Search results:** 49 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 48 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet internal 0.23.0 development (03850a6), `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 48 |
| Read | 42 |
| Not read: HTTP 403 | 3 |
| Not read: HTTP 404 | 2 |
| Not read: robots.txt disallows PageVet | 1 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- None found on the 42 pages read.

**AI crawlers refused:** 18 of 42 (43%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 16 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 403 | 17 | 16 | 17 |

**Different content for an AI crawler:** 3 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://www.hubspot.com/comparisons/pipedrive-vs-hubspot`, `https://www.hubspot.com/products/crm/startups`, `https://www.selecthub.com/customer-relationship-management/crm-pricing/`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
- **No hidden instructions** on any of the 42 pages read.
- **The highest refusal share of the three studies so far:** 43% of readable pages refuse at least one AI crawler, all with 403, and 16 refuse all three.
- **Vendors' own pages dominate the results** for these B2B queries (CRM makers' comparison and "best CRM" pages), so a large part of what an assistant can quote here is written by the companies being compared. The four-pages-per-site cap limits how much of the sample one vendor fills.
- **Three pages served a crawler different text,** two of them on one CRM vendor's site. Personalized or rotating modules could explain this; the study did not check which.
- **How it was run:** the 48 URLs were scanned in 8 parallel batches with the flags above, because the scanning machine stops any command after three minutes.
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 48 URLs. A field sample, not a census.
- **Unread pages:** 6 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

# Field study: front brake rotor shopping pages (2026-11-25)

Pages a web search returns for front brake rotor shopping pages, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=front+brake+rotor+shopping+pages) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (10):** best front brake rotors; front brake rotors for sale; where to buy brake rotors online; cheap front brake rotors deals; drilled and slotted brake rotors review; brake rotors buying guide; OEM vs aftermarket brake rotors; front brake rotor replacement cost; best brake rotors for trucks and SUVs; brake rotor and pad kit sale.
- **Search results:** 121 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 102 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet 0.3.0, `pagevet --urls urls.txt --fetch-css --compare-agents --format json`, robots.txt respected. Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 102 |
| Read | 66 |
| Not read: HTTP 403 | 24 |
| Not read: HTTP 404 | 5 |
| Not read: robots.txt disallows PageVet | 4 |
| Not read: other error | 2 |
| Not read: HTTP 418 | 1 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- high: 1
- medium: 0
- low: 0

  - `https://shop.advanceautoparts.com/find/isuzu-front-brake-rotors`: high, structured data (JSON-LD) (response_directive)

**AI crawlers refused:** 27 of 66 (41%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 20 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 402 | 3 | 3 | 3 |
| HTTP 403 | 21 | 18 | 17 |
| HTTP 429 | 1 | 1 | 1 |

**Different content for an AI crawler:** 7 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://shop.advanceautoparts.com/find/isuzu-front-brake-rotors`, `https://thedrive.com/guides-and-gear/how-much-should-it-cost-to-replace-brake-pads-and-rotors`, `https://www.thedrive.com/reviews/27627/best-brake-rotors`, `https://www.walmart.com/ip/207198003`, `https://www.walmart.com/ip/6316072106`, `https://www.walmart.com/ip/Max-Advanced-Brakes-Front-Brake-Rotors-2010-2013-2014-2015-2016-2017-2018-2019-2020-Ford-F-150-w-6-Lugs-Expedition-Lincoln-Navigator-Replacement-Geom/6319200241`, `https://www.walmart.com/ip/seort/916967367`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
(not written yet)
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 102 URLs. A field sample, not a census.
- **Unread pages:** 36 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

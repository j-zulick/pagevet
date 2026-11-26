# Field study: front brake rotor shopping pages (2026-11-19)

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=front+brake+rotor+shopping+pages) (or offline: `pagevet-study explore --out site/`).

A shopper asking an AI assistant about front brake rotors gets answers built from pages like these. This study
scanned the pages a web search returns for that topic and looked for hidden instructions and for pages that
serve AI crawlers something different from what a browser gets.

## Method

- **Queries (10):** best front brake rotors; front brake rotors for sale; where to buy brake rotors online;
  cheap front brake rotors deals; drilled and slotted brake rotors review; brake rotors buying guide; OEM vs
  aftermarket brake rotors; front brake rotor replacement cost; best brake rotors for trucks and SUVs; brake
  rotor and pad kit sale.
- **Search results:** 121 URLs from a web search, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` turned those into 102 URLs
  ([`urls.txt`](urls.txt)). The per-site cap stops one large retailer from filling the sample.
- **Scan:** PageVet pre-release (2026-11-19):
  ```
  pagevet --urls urls.txt --fetch-css --compare-agents --delay 0.3 --format json
  ```
  The scan respected robots.txt. Results are in [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 102 |
| Read in the browser view | 67 |
| Not read: 403 to PageVet's own user agent | 21 |
| Not read: 404 | 6 |
| Not read: robots.txt disallows PageVet | 4 |
| Not read: host does not resolve | 2 |
| Not read: timeout / 418 | 2 |

**Hidden instructions:** none found. Of the 67 pages read, none had an instruction aimed at an AI model in
any channel: hidden text, stylesheet-hidden text, comments, metadata, alt text or `<template>`.

**Pages that treat AI crawlers differently:** 27 of the 67 pages refuse at least one of the three AI crawler
user agents PageVet compares (GPTBot, ClaudeBot, PerplexityBot). 22 of them refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| 403 Forbidden | 21 | 20 | 18 |
| 402 Payment Required | 3 | 3 | 3 |
| 429 Too Many Requests | 1 | 1 | 1 |

The three 402 answers are all from one trade publication and look like pay-per-crawl. Each refusal is
reported at low severity. The tested request could not retrieve this page at the time. We did not measure
inclusion in an AI answer.

**Different content:** two pages from one automotive review site served ClaudeBot text that was 58% and 76%
similar to the browser's copy. These were reported at medium severity. The difference may come from rotating
product modules or ads rather than deliberate cloaking. This study did not check which.

## What this says

- On this commercial topic, the risk to an assistant's answer came from access, not from injected
  instructions. About two in five readable pages are closed to at least one AI crawler. Those pages' prices and
  advice are missing from answers built by that crawler.
- The suspicious cost-guide pages in the search results did not carry hidden instructions. These were
  several `*.pages.dev` sites and a news folder on an unrelated arts-centre domain. The `pages.dev` sites read
  clean. The arts-centre host did not resolve.

## Limits

- **Sample:** one day, one search engine and 102 URLs. This is a field sample, not a census.
- **Unread pages:** 35 of 102 pages were not read. Most refused PageVet's user agent with a 403, including
  several large parts retailers and dealer parts sites. PageVet did not retry them through another crawler or
  a browser, and it respected robots.txt. Hidden content on those pages is unmeasured.
- **Fetching:** fetched HTML only, with no JavaScript rendering. Text inserted by scripts is not seen.
- **Detection:** "none found" means none of PageVet's patterns matched. Its held-out catch rates are in
  [`../2026-11-19-evasion/`](../2026-11-19-evasion/). Instructions phrased outside those patterns can be missed.

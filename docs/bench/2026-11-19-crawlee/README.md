# Pages plain HTTP could not read, retried through crawlee-server (Nov 19, 2026)

**Question.** Can PageVet's `--crawl` source, backed by crawlee-server, read the pages that a plain fetch could not, and do they contain anything?

**Setup.** crawlee-server **2.2.0** (tag `v2.2.0`, from github.com/j-zulick/crawlee-server) was run locally on a workstation.
- **Configuration:** no Firecrawl, robots.txt respected, capture on, a throwaway token. This is the released code with a default configuration, not a production deployment.
- **Inputs:** every URL from the two page sets that the plain-HTTP run (PageVet internal 0.5.0) had not scanned, 62 homepages and 32 sample pages. They went through `docs/bench/crawlee_run.py`: crawlee-server `mode: page`, ten URLs per request, each stored capture read back and scanned.

## Result
Rows for the second sample, a privately supplied page list, are summarized here; its URLs are not published.

| | Homepages | Second sample |
|---|---|---|
| Not readable by plain HTTP | 62 | 32 |
| Read through crawlee-server | **12** | **9** |
| Findings on those pages | 0 | 0 |
| Still blocked: HTTP 403 | 39 | 16 |
| HTTP 429 / 503 / connection errors | 8 | 1 |
| robots.txt disallows | 2 | 4 |
| Refused by crawlee-server's address guard | 0 | 1 |
| crawlee-server error | 1 | 0 |
| Fetched but no record | 0 | 1 |

**Combined with the plain-HTTP runs**, PageVet has now read 205 of the 255 homepages and 142 of the 165 sample pages.
- Nothing is flagged at medium or high severity on any of them.
- The only finding of any kind is the low false alarm on a forum reply box (sample README).

## What it verifies
- **The `--crawl` path works against real crawlee-server code:** request format, `mode: page`, batches of ten, capture storage, reading `/v1/captures/:id` back, and the capture id, SHA-256 and fetch time travelling with each result.
- **It does not verify a production deployment** (a reachable URL, a real token, Firecrawl rendering).

## Found in crawlee-server (not changed from here)
- **A non-HTML error response crashes extraction.** `https://www.imf.org/` answers the crawler with a JSON 404. crawlee-server reports the failure as `$ is not a function` instead of a clean `non_html` or `http_404` outcome. It is handled (the crawl reports the page as failed and continues), but the message is wrong.
- **One bad URL fails a whole request.** A URL refused by the address guard makes the whole request return 400 `url_refused`, without saying which URL. `crawlee_run.py` works around it by retrying the batch one URL at a time.

## Why most pages stay blocked
crawlee-server's plain fetch meets the same bot protection as PageVet's (403 from Akamai, Cloudflare and similar). The production deployment's Firecrawl rendering, or Camoufox through the research gateway, is the route for those; neither was available to this run.

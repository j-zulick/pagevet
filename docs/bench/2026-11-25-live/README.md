# Live checks against real services (2026-11-25)

The sources and second opinions that talk to other services were built and tested against stand-ins that follow
each service's documented API. This folder records running them against the real services, from the maintainer's
machine, with a PageVet pre-release (2026-11-25) build cloned from `main`. Each check either ran here or says why it hasn't yet; the ones still
open run the same way and their results go in a later release.

## Results

| Check | Result |
|---|---|
| `--via firecrawl` (rendered HTML through a self-hosted Firecrawl) | **Passed:** 5 of 5 public pages read after their scripts ran, 0 findings ([`results-firecrawl.json`](results-firecrawl.json), pages in [`urls.txt`](urls.txt)) |
| `pagevet-view --via firecrawl` | **Passed:** the side-by-side view was written and labelled as rendered by Firecrawl (0 findings on the first page) |
| `--crawl` through crawlee-server | Not run: the crawlee-server instance accepts requests only from its own host, so this machine could not reach it. The source stays tested against a stand-in (`tests/test_sources.py`). |
| Jev and the quote-checked `llm` second opinion (OpenRouter), on a BIPIA sample of 50 clean + 100 attack texts and on 40 clean pages | Not run yet: needs the maintainer's OpenRouter key. The sample and the pages were built and fetched; the run is capped at US$3 and records the spend. |
| Langfuse records (`--langfuse`) | Not run yet: needs Langfuse keys. |
| Ollama second opinion | Not run: no local Ollama on the machine at the time. Covered offline by `tests/test_detectors.py`. |

**Cost of this run:** US$0 (no paid model was called).

Every result records how it was read: each page in `results-firecrawl.json` carries `evidence.fetched_via: "firecrawl"`,
the SHA-256 of the rendered text and the UTC time it was fetched.

## Reproduce

With your own Firecrawl:

```sh
export PAGEVET_FIRECRAWL_URL=https://your-firecrawl.example PAGEVET_FIRECRAWL_KEY=...
pagevet --via firecrawl --json --urls urls.txt --out results-firecrawl.json
pagevet-view https://www.usa.gov/ --via firecrawl --out view.html
```

Pages change, so a later run reads different text. The five pages are the first five of a sample of the clean-page
list ([`../2026-11-19-clean-pages/urls.txt`](../2026-11-19-clean-pages/urls.txt), every fifth line).

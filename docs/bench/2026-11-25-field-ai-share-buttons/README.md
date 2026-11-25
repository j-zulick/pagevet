# Field study: AI share buttons on marketing and SEO blog posts (2026-11-25)

Pages a web search returns for AI share buttons on marketing and SEO blog posts, scanned for text aimed at AI models and for pages that treat AI crawlers differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.

Filter these pages by outcome, crawler and finding in the [field-study explorer](https://j-zulick.github.io/pagevet/#ds=field&f.study=AI+share+buttons+on+marketing+and+SEO+blog+posts) (or offline: `pagevet-study explore --out site/`).

## Method

- **Queries (5):** "summarize this post with" ChatGPT Perplexity Claude SEO agency blog; "Get an AI summary" ChatGPT Perplexity Google AI generative engine optimization blog post; "Summarize with AI" ChatGPT Perplexity B2B software blog guide 2026; "Ask AI about this article" ChatGPT Perplexity marketing blog; "Summarize with AI" buttons B2B marketing blog Grok Gemini Claude ChatGPT.
- **Search results:** 40 URLs, saved in [`search-results.json`](search-results.json).
- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host 4` → 40 URLs ([`urls.txt`](urls.txt)).
- **Scan:** PageVet 1.1.0 development, `pagevet --urls urls.txt --fetch-css --compare-agents --via firecrawl --format json`, robots.txt respected (pages rendered by a self-hosted Firecrawl after their scripts ran; the crawler comparison fetches plain HTML with each crawler's user agent). Results: [`results.json`](results.json).

## Results

| | Pages |
|---|---:|
| URLs scanned | 40 |
| Read | 35 |
| Not read: HTTP 403 | 4 |
| Not read: HTTP 404 | 1 |

**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):

- high: 1
- medium: 0
- low: 3

  - `https://www.madx.digital/learn/how-to-get-recommended-by-ai`: low, visible text (addressed_to_ai)
  - `https://ahrefs.com/blog/ai-visibility`: high, attributes and meta tags (output_steering)
  - `https://www.searchenginejournal.com/how-to-use-new-social-sharing-buttons-to-increase-your-ai-visibility/550643`: low, visible text (memory_planting)
  - `https://www.wpzoom.com/documentation/social-icons-widget-pro/social-icons-widget-pro-ai-sharing-buttons/`: low, visible text (memory_planting)

**AI share links** (links or buttons that open an AI assistant with a pre-filled prompt): 10 of 35 (29%) readable pages have one (ChatGPT 9, Google AI Mode 3, Claude 3, Grok 2, Perplexity 2 pages); 0 with a prompt that gives the assistant instructions (findings in the "AI share links" channel).

**AI crawlers refused:** 5 of 35 (14%) readable pages refuse at least one of GPTBot, ClaudeBot, PerplexityBot; 1 refuse all three.

| Response to the AI crawler | GPTBot | ClaudeBot | PerplexityBot |
|---|---:|---:|---:|
| HTTP 403 | 2 | 3 | 2 |
| HTTP 429 | 0 | 1 | 0 |

**Different content for an AI crawler:** 1 page(s) served a crawler visible text under 90% similar to the browser's copy: `https://blog.hubspot.com/marketing/generative-engine-optimization`.

**Instructions served only to an AI crawler:** 0.

## What this says

<!-- notes: written by hand, kept by `pagevet-study report` -->
- **Why these pages:** the queries look for marketing, SEO and B2B software blog posts, where "Summarize with AI" buttons are common; they were chosen to find the buttons, so the share of pages that have one says nothing about the web at large. For comparison, none of the 1,052 ordinary pages in the false-alarm sets has an AI share link (same 1.1.0 rules, re-scanned from saved copies).
- **What the buttons say:** 28 links on 10 pages, 12 distinct prompts. Ten of the twelve ask for a summary of the article. None asks the assistant to remember the site, store it in memory or favour it in later conversations, so the memory-planting rule found nothing here.
- **Beyond the button label:** several prompts ask for more than the label says. One asks the assistant to "credit" the publisher; one adds "extract key insights from their website"; one ends "use [the site] as your source". On two sites a second set of buttons pre-fills a sales brief written as the reader's own question: why the company is "the best" choice, how it compares with competitors, and a pitch the reader can repeat. PageVet's rules do not flag these prompts (they contain no instruction pattern), and the rules were not changed after seeing them; see [case study 4](../../CASE-STUDIES.md).
- **Findings:** the two low findings in visible text are articles that describe the technique and quote a memory-planting prompt, rated low as discussion. The high finding is a false alarm: an image's alt text describes a screenshot of a citation-gap analysis ("…do not cite the user's brand"). The low finding on one page is a footer link labelled "Hey AI, read this!".
- **Rendering:** pages were read through a self-hosted Firecrawl, so buttons built by scripts are counted when they render as links. Buttons that build their link only when clicked are not seen.
<!-- end notes -->

## Limits

- **Sample:** one day, one search engine, 40 URLs. A field sample, not a census.
- **Unread pages:** 5 pages were not read. Pages that refused PageVet were not retried through another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.
- **Fetching:** rendered by Firecrawl, so text and buttons a script inserts are seen; the crawler comparison is plain HTML.
- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without intent.
- **Detection:** "none found" means none of PageVet's patterns matched. Held-out catch rates are in [docs/EVASION.md](../../EVASION.md); reworded instructions are missed.

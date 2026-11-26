# False alarms on ordinary pages (Nov 19, 2026)

**Question.** How often does PageVet flag ordinary public pages that are not trying to influence AI systems?

**Data.** 255 homepages of ordinary sites, one per host, picked by hand across government, education, news, technology, SEO, retail, travel, finance, health, real estate, automotive and culture before any scan ran (`urls.txt`). Fetched once over plain HTTP from a Mac, with `clean_pages.py`: robots.txt checked first, PageVet's own fetcher and user agent, 16 hosts at a time.
- **Scanned:** 194.
- **Blocked or failed:** 59 (56 returned an HTTP error, mostly 403 bot protection; 2 timeouts; 1 protocol error).
- **Skipped:** 2 that robots.txt disallows.

`results-2026-11-19-repetition-on.jsonl` holds each page's outcome, SHA-256, size and findings as first run; `results-2026-11-19.jsonl` is a re-fetch with the repetition rule off by default (193 scanned, 0 flagged). Page copies are not kept, and re-running will differ where sites have changed.

## Result
| Rules | Pages flagged | 95% interval |
|---|---|---|
| As run (repetition rule on) | 21 of 194 (10.8%) | 7.2–16.0% |
| …at medium or high severity | 0 of 194 | 0–1.9% |
| Default since (repetition-only findings off) | **0 of 194** | **0–1.9%** |

**All 21 alarms came from one rule, `repetition`** ("the page is mostly one repeated claim"), and every one was rated low.
- **Checked by hand,** all 21 are template boilerplate: repeated menu labels ("Watch Now", "See More", "Caret Right Icon"), a site's own name, timestamps in a news list, tag-manager comments, and one bot-block page.
- **None of the instruction patterns fired** on any of the 194 pages.

**What changed because of it.** Since then, a channel whose only finding is `repetition` is not reported unless you pass `--include-repetition`. An instruction found alongside repetition is still reported as before.

## Caveats
- **The default figure is not blind.** The change was made after seeing these pages, and its result was computed by re-scoring the recorded findings without repetition-only channels, not by a fresh fetch. A fresh list of pages is needed for an independent figure.
- **Homepages only, and only sites that let a plain client in.** Article pages, forums and pages with user content are where injected text would more likely appear; the 59 blocked sites are untested. Scanning through Firecrawl or crawlee-server would reach more of them.
- **"Clean" is assumed.** No page here was known to contain an injection; the 21 flagged pages were each inspected.

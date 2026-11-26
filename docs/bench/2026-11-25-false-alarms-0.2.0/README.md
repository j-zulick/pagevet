# False-alarm re-scan for 0.2.0 (2026-11-25)

Every committed real-page list was fetched once more on 2026-11-25 (plain HTTP, robots.txt respected, `docs/bench/pages_12_languages.py fetch`, saved pages kept out of the repository, SHA-256 of the saved file `0ddf9034164b503c…`), then scanned with the 0.1.0 rules and the 0.2.0 rules on exactly the same bytes (`pages_12_languages.py scan`). `results.jsonl` has one row per page with both versions' findings.

| Set | Pages read | Flagged medium or high (0.1.0 → 0.2.0) | Flagged low only (0.1.0 → 0.2.0) |
|---|---|---|---|
| Homepages (`2026-11-19-clean-pages`) | 186 | 0 → 0 | 0 → 0 |
| Articles and user content (`2026-11-19-fresh-pages`) | 153 | 1 → 1 | 1 → 1 |
| Spanish, French, German, Portuguese (`2026-11-19-intl-pages`) | 142 | 0 → 0 | 0 → 0 |
| Italian, Dutch (`2026-11-19-it-nl-pages`) | 100 | 0 → 0 | 0 → 0 |
| Twelve languages (`2026-11-24-pages-12-languages`) | 341 | 0 → 0 | 0 → 0 |
| Second sample (supplied privately; its rows are not published) | 130 | 0 → 0 | 1 → 1 |
| **All** | **1,052** | **1 → 1** | **2 → 2** |

**The 0.2.0 patterns changed no result on any of the 1,052 pages.** 220 of the 1,272 listed pages could not be read today (gone, refused or disallowed by robots.txt); they are recorded as not read, never as clean.

The one medium finding is new since the sets were first published, and the 0.1.0 rules flag it too: a Hacker News comment that quotes a prompt ("hey Claude do all the deep research…") matched the existing `addressed_to_ai` rule. It is a false alarm, left as it is: the rule is not changed from a page it is measured on.

Scan time on the same saved pages: 207 s with 0.1.0, 264 s with 0.2.0 (about 1.27×), single process.

## 0.3.0 on the same saved pages
Scanned again with 0.3.0 (`results-0.3.0.jsonl`): the same 1 page at medium and 2 at low, with no new finding. All three were already in comments or replies, and 0.3.0 now reports them in the new **user-submitted content** channel instead of visible text. 199 of the 1,051 readable HTML pages had at least one comment, review or reply container. The commercial-manipulation label only marks existing findings, so it cannot add false alarms; none of the three is commercial. Scan time 261 s.

## 1.1.0 on the same saved pages
Scanned again with 1.1.0 (`results-1.1.0.jsonl`, which also records each page's number of AI share links): the same 1 page at medium and 2 at low, with no new finding. The memory-planting rule matched nothing, and **none of the 1,052 pages has an AI share link** (a link that opens an AI assistant with a pre-filled prompt). Scan time 347 s, against 325 s and 332 s for 1.0.1 in two runs on the same machine the same evening (about 5–7% slower), single process.

## 1.3.0 on the same saved pages
Scanned again with the 1.3.0 rules (`results-1.3.0.jsonl`): the same 1 page at medium and 2 at low, with no new finding. The new candidate-steering rule matched nothing. Scan time 348 s, the same as 1.1.0 (347 s).

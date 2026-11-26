# False-alarm re-scan (2026-11-25)

Every committed real-page list was fetched once more on 2026-11-25 (plain HTTP, robots.txt respected, `docs/bench/scripts/pages_12_languages.py fetch`, saved pages kept out of the repository, SHA-256 of the saved file `0ddf9034164b503c…`), then scanned on exactly the same bytes (`pages_12_languages.py scan`): first with two pre-release (2026-11-25) builds, before and after the two pattern additions described in [docs/EVASION.md](../../EVASION.md) (`results.jsonl`, fields `findings_first_build` and `findings_second_build`), and last with the rules released in 0.1.0 (`results-0.1.0.jsonl`, which also records each page's number of AI share links).

| Set | Pages read | Flagged medium or high | Flagged low only |
|---|---|---|---|
| Homepages (`2026-11-19-clean-pages`) | 186 | 0 | 0 |
| Articles and user content (`2026-11-19-fresh-pages`) | 153 | 1 | 1 |
| Spanish, French, German, Portuguese (`2026-11-19-intl-pages`) | 142 | 0 | 0 |
| Italian, Dutch (`2026-11-19-it-nl-pages`) | 100 | 0 | 0 |
| Twelve languages (`2026-11-24-pages-12-languages`) | 341 | 0 | 0 |
| Second sample (supplied privately; its rows are not published) | 130 | 0 | 1 |
| **All** | **1,052** | **1** | **2** |

**The three scans give the same result on every one of the 1,052 pages.** 220 of the 1,272 listed pages could not be read that day (gone, refused or disallowed by robots.txt); they are recorded as not read, never as clean.

- **The medium finding** is new since the sets were first published, and every build flags it: a Hacker News comment that quotes a prompt ("hey Claude do all the deep research…") matched the `addressed_to_ai` rule. It is a false alarm, left as it is: a rule is not changed from a page it is measured on. With 0.1.0's rules it and both low findings are reported in the **user-submitted content** channel (199 of the 1,051 readable HTML pages had a comment, review or reply container), and none is labelled commercial.
- **AI share links, memory planting, candidate steering:** none of the 1,052 pages has an AI share link, and the memory-planting and candidate-steering rules matched nothing.
- **Scan time** on the same saved pages, single process: 207 s and 264 s for the two earlier builds, 348 s with 0.1.0's rules.

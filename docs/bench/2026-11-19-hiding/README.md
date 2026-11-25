# Hiding methods (Nov 19, 2026)

**Question.** When a page hides an instruction from people, does PageVet see it, and does it rate it as concealed (high) rather than as visible text (medium)?

**Method.** `docs/bench/hiding_run.py` puts each of the evasion test's seed instructions (6 development and 6 held-out, three invented brands each) into a small page using one of 21 hiding methods: inline CSS, the page's own stylesheet, markup a browser does not draw (`<template>`, SVG `<title>`/`<desc>`, hidden form inputs) and three controls PageVet already handled. It counts pages with a finding, and pages where the finding is rated high.

**Not a blind test.** The 18 new methods were listed, measured on internal 0.7.0, and then the rules were written for them. This shows coverage of known techniques, not resistance to new ones. The held-out seeds only vary the instruction text.

## Result (pages rated high, of 18 development / 18 held-out)
| Method | internal 0.7.0 | internal 0.8.0 |
|---|---|---|
| `display:none`, `visibility:hidden`, off-screen left (controls) | 18 / 15 | 18 / 15 |
| `max-height:0` + `overflow:hidden`, `<textarea hidden>` (already handled) | 18 / 15 | 18 / 15 |
| `color:transparent` (inline or stylesheet) | 0 / 0 | **18 / 15** |
| `transform:scale(0)` (inline or stylesheet) | 0 / 0 | **18 / 15** |
| `clip-path:inset(100%)`, `clip-path:circle(0)` | 0 / 0 | **18 / 15** |
| `width:0` + `overflow:hidden` | 0 / 0 | **18 / 15** |
| `font-size:1px`, `font-size:0.1em` | 0 / 0 | **18 / 15** |
| `opacity:0.01` | 0 / 0 | **18 / 15** |
| Off-screen right, off-screen top in `em` | 0 / 0 | **18 / 15** |
| SVG `<title>`, SVG `<desc>` | 0 / 0 | **18 / 15** |
| `<template>` content | 0 / 0 (not even found) | **18 / 15** |
| `<input type="hidden" value>` | 0 / 0 (not even found) | **18 / 15** |

In internal 0.7.0, every CSS and SVG method above was still found, but rated medium, as if a reader could see it. `<template>` content was skipped and hidden-input values were not read, so those pages got no finding at all. The held-out control is 15, not 18, for the reason given in `docs/EVASION.md`. Full numbers: `results-0.7.0.json`, `results-0.8.0.json`.

## Visible look-alikes that must not count
These stay visible, and each is a unit test (`tests/test_hiding.py`):
- gradient text (`background-clip:text` with `color:transparent`);
- `min-width:0` / `min-height:0` / `line-height:0` with `overflow:hidden`;
- `border-color` or `background-color: transparent`;
- `scale(0.5)`, `inset(10%)`, `circle(50%)`, `font-size:0.875rem`, `opacity:0.1`, `left:-10px`.

## Real pages
The three page sets (homepages, the second sample (supplied privately: counts below include its 79 compared pages, but its rows are removed from the published .jsonl files), the fresh article and user-content pages) were fetched once on Nov 19 into local storage and scanned with both rule sets. Only pages that an earlier, robots.txt-respecting run had scanned were compared.
- **Findings:** identical on all 314 compared pages, 0 at medium or high, the same 2 low ones (`real-pages-0.7-rules.jsonl`, `real-pages-0.8-rules.jsonl`).
- **Hidden text read:** 287,148 characters on 236 pages with internal 0.8.0, against 222,623 on 228 with internal 0.7.0 (29% more), with no new false alarm.

## Linked stylesheets (`--fetch-css`, internal 0.9.0)
The same 314 saved pages were scanned again with each page's own linked stylesheets (`real-pages-0.9-fetch-css.jsonl`).
- **Stylesheets:** 185 pages link stylesheets on their own host; 485 of their 496 stylesheets were read (43 MB). Stylesheets on other hosts (CDNs) are not read.
- **Hidden text read:** 622,246 characters, 2.2 times as much as without stylesheets (287,148).
- **Findings:** identical to internal 0.8.0 on all 314 pages; none at medium or high.
- **Limit:** a rule that hides an element counts even if a later rule or a media query shows it again (a mobile menu hidden on desktop, for example). That can rate visible text as hidden; it changed no finding here.

## internal 0.18.0: stylesheet parser, a separate channel, and CDN stylesheets
**A quadratic parser, found during this check.** Some stylesheets stalled the scan for tens of seconds. One was bio.site's 1 MB stylesheet, whose nested `@keyframes` blocks left unbalanced braces for the old regexes; a 40 KB slice took 12 s. A stylesheet built to do this could stall any scan, so internal 0.18.0 parses stylesheets in one linear pass. The new parser:
- tracks brace depth;
- skips quoted strings and backslash escapes;
- reads `@layer` and `@supports` blocks, which apply to the whole page;
- skips `@media`, `@keyframes`, `@container` and the other at-rule blocks at any depth;
- caps nesting.

A unit test checks that an input which took the old parser 17.6 s now parses in under 2 s.

**The new parser on identical CSS** (`parser-comparison.jsonl`):
- 264 of the 314 pages could be compared; the old parser could not finish on the other 50 pages' large stylesheets in reasonable time;
- 233 of the 264 have exactly the same hidden text;
- the new parser reads 5% less hidden text in total (375,288 against 394,240 characters), all from rules inside `@media` blocks that the old regex failed to strip (for example ubuntu.com's print-only rules hiding `header`, `nav` and `footer`, and Wikipedia's `@media screen` rules);
- no page gained hidden text.

**A separate channel for text hidden only by stylesheet rules.** "Hidden by stylesheet rules" now holds text that only stylesheet rules hide: dialogs, menus, tabs and collapsed forms. Text hidden inline, by markup or by `aria-hidden` stays in "hidden elements".
- In the new channel, a match of only the weakest pattern (a command about the reply) is rated medium instead of high. Everything else stays high.
- **Why:** with CDN stylesheets read, a forum's collapsed reply box ("Add your reply…") became hidden and was rated high.
- **Effect on the hiding report** (`results-0.18.0.json`): the two stylesheet rows go from 18 to 15 of 18 rated high on the development seeds, because the reply-command seed is now medium; it is still found. Every other row and the held-out set are unchanged.

**Real pages** (`real-pages-0.18-fetch-css.jsonl`, `real-pages-0.18-css-any-host.jsonl`), the same 314 saved pages:

| | `--fetch-css` (same host) | `--fetch-css --css-any-host` |
|---|---|---|
| Pages linking stylesheets | 185 | 289 |
| Stylesheets read | 485 of 496 (42.4 MB) | 939 of 950 (116.9 MB) |
| Hidden text, all channels | 595,705 characters | 705,129 characters |
| ...of which hidden only by stylesheet rules | 368,246 | 477,670 |
| Pages flagged medium or high | 0 | 1 (the forum reply box, medium) |

**Also in internal 0.18.0:**
- Each stylesheet is fetched once per run, however many pages share it.
- Every fetch has an overall limit of three times its timeout, because the timeout alone applies to each read and a server that drips bytes could otherwise hold a fetch open indefinitely. A unit test runs such a server on localhost.

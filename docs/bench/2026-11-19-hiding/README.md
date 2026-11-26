# Hiding methods (Nov 19, 2026; results updated 2026-11-24)

**Question.** When a page hides an instruction from people, does PageVet see it, and does it rate it as concealed (high) rather than as visible text (medium)?

**Method.** `docs/bench/scripts/hiding_run.py` puts each of the evasion test's seed instructions (6 development and 6 held-out, three invented brands each) into a small page using one of 21 hiding methods: inline CSS, the page's own stylesheet, markup a browser does not draw (`<template>`, SVG `<title>`/`<desc>`, hidden form inputs) and controls such as `display:none`. It counts pages with a finding, and pages where the finding is rated high. Results: `results-2026-11-24.json` (regenerated and checked by `pagevet-reproduce`).

**Not a blind test.** The methods were listed first and the rules were then written for them. This shows coverage of known techniques, not resistance to new ones. The held-out seeds only vary the instruction text.

## Result (pages rated high, of 18 development / 18 held-out)
| Method | Rated high |
|---|---|
| `display:none`, `visibility:hidden`, off-screen left (controls) | 18 / 15 |
| `max-height:0` + `overflow:hidden`, `<textarea hidden>` | 18 / 15 |
| `color:transparent`, `transform:scale(0)` (inline) | 18 / 15 |
| `color:transparent`, `transform:scale(0)` (page stylesheet) | 15 / 15 (found 18 / 15) |
| `clip-path:inset(100%)`, `clip-path:circle(0)` | 18 / 15 |
| `width:0` + `overflow:hidden` | 18 / 15 |
| `font-size:1px`, `font-size:0.1em`, `opacity:0.01` | 18 / 15 |
| Off-screen right, off-screen top in `em` | 18 / 15 |
| SVG `<title>`, SVG `<desc>` | 18 / 15 |
| `<template>` content, `<input type="hidden" value>` | 18 / 15 |

The held-out control is 15, not 18, for the reason given in `docs/EVASION.md`. Text hidden only by stylesheet rules has its own channel, where a command about the reply alone is rated medium (collapsed reply boxes and dialogs match it), so the reply-command seed is found but not rated high in the two stylesheet rows.

## Visible look-alikes that must not count
These stay visible, and each is a unit test (`tests/test_hiding.py`):
- gradient text (`background-clip:text` with `color:transparent`);
- `min-width:0` / `min-height:0` / `line-height:0` with `overflow:hidden`;
- `border-color` or `background-color: transparent`;
- `scale(0.5)`, `inset(10%)`, `circle(50%)`, `font-size:0.875rem`, `opacity:0.1`, `left:-10px`.

## Real pages
314 saved pages (homepages, the second sample (supplied privately: counts below include its 79 compared pages, but its rows are removed from the published .jsonl files), and fresh article and user-content pages; fetched once on Nov 19, robots.txt respected) were scanned with each page's linked stylesheets read (`real-pages-2026-11-19-fetch-css.jsonl`, `real-pages-2026-11-19-css-any-host.jsonl`).

| | `--fetch-css` (same host) | `--fetch-css --css-any-host` |
|---|---|---|
| Pages linking stylesheets | 185 | 289 |
| Stylesheets read | 485 of 496 (42.4 MB) | 939 of 950 (116.9 MB) |
| Hidden text, all channels | 595,705 characters | 705,129 characters |
| ...of which hidden only by stylesheet rules | 368,246 | 477,670 |
| Pages flagged medium or high | 0 | 1 (a forum's collapsed reply box, medium) |

**Limit:** a rule that hides an element counts even if a later rule or a media query shows it again (a mobile menu hidden on desktop, for example). That can rate visible text as hidden.

## Stylesheet parser
Stylesheets are parsed in one linear pass that tracks brace depth, skips quoted strings and escapes, reads `@layer` and `@supports` blocks, skips `@media`, `@keyframes`, `@container` and other at-rule blocks at any depth, and caps nesting. An earlier regex-based parser took 12 s on a 40 KB slice of one real stylesheet; a unit test checks that such input now parses in under 2 s. On identical CSS (`parser-comparison.jsonl`), 233 of the 264 comparable pages have exactly the same hidden text; the rest differ only by rules inside `@media` blocks that the regex wrongly applied to the whole page.

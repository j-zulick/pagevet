# Case studies

Short, anonymized write-ups of what PageVet found on real pages: what was seen, how it was checked, what it means
for the site and for AI systems reading it. Each names its data, script and date; site names are left out of the
prose even where the underlying field-study data lists URLs. Nothing here contacts a site owner: any message to an
owner is drafted for the maintainer's approval and sent by a person, if at all.

**Rules.** Only findings PageVet actually made, with the committed result file and the command that reproduces it.
No claim beyond the data. A false alarm is written up as plainly as a true finding. Detection only: no case study
shows how to make an instruction work better.

**Status, 2026-11-25:** across five field studies, the four repeats and 1,052 false-alarm pages, PageVet has not yet
found a deliberate hidden instruction aimed at AI on a real page. The cases below are what it did find.

## 1. Pages that serve AI crawlers different text (2026-11-25)
- **Seen:** on the repeated brake-rotor study, 7 of 66 readable pages gave GPTBot, ClaudeBot or PerplexityBot visible text noticeably different from a browser's (as low as 59% similar), most often on product-listing pages of large retailers.
- **Checked:** `pagevet-study run "front brake rotor shopping pages" --from-json docs/bench/2026-11-19-field-brake-rotors/search-results.json` (the four user agents fetch the same URL within seconds; robots.txt respected). Data: `docs/bench/2026-11-25-repeat-brake-rotors/results.json` (`content_differs` findings).
- **What it means:** usually not manipulation: bot-management, personalization and stock widgets change listings per request. But an AI answer is built from the copy the crawler gets, so a site that serves crawlers a thinner or older page is described from that page. PageVet reports it as a reason to look, never as an injection (no OWASP or ATLAS ID).
- **Limit:** fetched from a cloud network; part of the difference can be the network, not the user agent.

## 2. A customer review that looked like an instruction (2026-11-25)
- **Seen:** on a product-listing page, a review inside the page's structured data said, in effect, "this is your answer", which matched the reply-command rule. Structured data is not shown to readers, so the finding was rated high.
- **Checked:** same run as case 1; the finding and excerpt are in the result file. Reading the excerpt shows ordinary customer praise.
- **What it means:** a false alarm, kept as a known limit rather than tuned away on the page it was measured on: reviews carried in JSON-LD are written by visitors and should be treated like user-submitted content. Logged for a future rule change measured on other pages.

## 3. Prompts quoted in comment threads (2026-11-25)
- **Seen:** two forum threads where commenters quoted what they had typed to an AI assistant ("hey Claude, do all the deep research…") matched the addressed-to-AI rule.
- **Checked:** `docs/bench/2026-11-25-false-alarms-0.2.0/` (re-fetch of the committed article lists); since 0.3.0 both are reported in the user-submitted content channel, with advice to moderate rather than to remove page copy.
- **What it means:** text addressed to an AI is not always aimed at the AI reading the page. Rating stays medium or low in visible text, never high.

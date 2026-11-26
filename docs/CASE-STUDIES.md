# Case studies

Short, anonymized write-ups of what PageVet found on real pages: what was seen, how it was checked, what it means
for the site and for AI systems reading it. Each names its data, script and date; site names are left out of the
prose even where the underlying field-study data lists URLs. Nothing here contacts a site owner: any message to an
owner is drafted for the maintainer's approval and sent by a person, if at all.

**Rules.** Only findings PageVet actually made, with the committed result file and the command that reproduces it.
No claim beyond the data. A false alarm is written up as plainly as a true finding. Detection only: no case study
shows how to make an instruction work better.

**Status, 2026-11-25:** across six field studies, the four repeats and 1,052 false-alarm pages, PageVet has not yet
found a deliberate hidden instruction aimed at AI on a real page, nor an AI share link that plants a site in an
assistant's memory. The cases below are what it did find.

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
- **Checked:** `docs/bench/2026-11-25-false-alarms/` (re-fetch of the committed article lists); both are reported in the user-submitted content channel, with advice to moderate rather than to remove page copy.
- **What it means:** text addressed to an AI is not always aimed at the AI reading the page. Rating stays medium or low in visible text, never high.

## 4. "Summarize with AI" buttons that pre-fill a sales brief (2026-11-25)
- **Seen:** on the field study of marketing and SEO blog posts, 10 of 35 readable pages had links that open ChatGPT, Claude, Perplexity, Grok or Google AI Mode with a pre-filled prompt. Most ask for a summary of the article. On two sites, a web host and a marketing agency, a second row of buttons labelled only with the assistants' names pre-fills a long prompt written as the reader's own question: what makes the company unique or "the best" platform, how it compares with competitors, and, on one, a 90-second pitch and the top five reasons to choose it. A third site's prompt ends by telling the assistant to use the site as its source.
- **Checked:** `pagevet-study run "AI share buttons on marketing and SEO blog posts" --from-json docs/bench/2026-11-25-field-ai-share-buttons/search-results.json --via firecrawl` (pages rendered by a self-hosted Firecrawl). Every link and its decoded prompt is in the `ai_share_links` field of `docs/bench/2026-11-25-field-ai-share-buttons/results.json`.
- **What it means:** none of these prompts asks the assistant to remember the site, so they are not the memory poisoning Microsoft reported (MITRE ATLAS AML.T0080), and PageVet reports no finding: they contain no instruction pattern. But the person clicking sees an assistant's logo, not the prompt, and the assistant answers a brief the site wrote. The prompts are listed so a reader can judge them; the rules were not changed after seeing these pages. Messages to the site owners, if any, are drafted for the maintainer and not sent.
- **Limit:** 40 search results chosen to find such buttons, on one day; it says nothing about how common they are elsewhere. None of the 1,052 ordinary pages in the false-alarm sets has an AI share link.


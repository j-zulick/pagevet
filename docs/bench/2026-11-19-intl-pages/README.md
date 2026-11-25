# False alarms on Spanish, French, German and Portuguese pages (Nov 19, 2026)

**Question.** Do the multilingual patterns added in internal 0.12.0 fire on ordinary pages in those languages?

**Set.** `docs/bench/fresh_pages_intl.py` took 25 random Wikipedia articles in each of the four languages and the current entries of one news feed per language (El País, Le Monde, tagesschau, Folha): 176 URLs, not chosen by hand (`urls.txt`).

**Run.** `clean_pages.py` (robots.txt respected) read 136 (`results-http-0.12.jsonl`). The readable pages were saved once and scanned with the internal 0.11.0 and the internal 0.12.0 rules (`saved-pages-0.11-rules.jsonl`, `saved-pages-0.12-rules.jsonl`; 134 saved).

| Source | Read |
|---|---|
| Wikipedia es / fr / de / pt | 25 / 25 / 25 / 23 |
| Le Monde, tagesschau | 16, 20 |
| El País | 2 of 20 (errors) |
| Folha | 0 of 20 (robots.txt disallows) |

## Result
**0 of 134** pages flagged at any severity, with either rule set (95% interval 0–2.8%). The 314 English pages and BIPIA's 50 clean emails are unchanged too.

## Limits
Mostly encyclopedia articles and news; no forums, shops or support pages in these languages, where commands about a reply ("añade a tu respuesta…") are likelier to appear in ordinary text.

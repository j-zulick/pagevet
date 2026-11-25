# False alarms on Italian and Dutch pages (Nov 19, 2026)

**Question.** Do the Italian and Dutch patterns added in internal 0.19.0 fire on ordinary pages in those languages?

**Set.** `docs/bench/fresh_pages_intl.py urls.txt it-nl` took 30 random Wikipedia articles in each language plus the current entries of the Corriere della Sera and NOS news feeds: 100 URLs, not chosen by hand (`urls.txt`).

**Run.** `clean_pages.py` (robots.txt respected) read all 100 (`results-http-0.19.jsonl`). The pages were saved once and scanned with the internal 0.18.0 and internal 0.19.0 rules (`saved-pages-0.18-rules.jsonl`, `saved-pages-0.19-rules.jsonl`).

## Result
**0 of 100** pages flagged at any severity, with either rule set (95% interval 0–3.7%). The 314 English pages, the 134 Spanish, French, German and Portuguese pages, and BIPIA's 50 clean emails are unchanged.

## Limits
Encyclopedia articles and news only; no forums, shops or support pages in these languages.

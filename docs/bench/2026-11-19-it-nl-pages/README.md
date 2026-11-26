# False alarms on Italian and Dutch pages (Nov 19, 2026)

**Question.** Do the Italian and Dutch patterns fire on ordinary pages in those languages?

**Set.** `docs/bench/scripts/fresh_pages_intl.py urls.txt it-nl` took 30 random Wikipedia articles in each language plus the current entries of the Corriere della Sera and NOS news feeds: 100 URLs, not chosen by hand (`urls.txt`).

**Run.** `clean_pages.py` (robots.txt respected) read all 100 (`results-2026-11-19.jsonl`).

## Result
**0 of 100** pages flagged at any severity (95% interval 0–3.7%).

## Limits
Encyclopedia articles and news only; no forums, shops or support pages in these languages.

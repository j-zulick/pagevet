# False-alarm check in twelve languages, and scan time (PageVet internal 0.24.0, Nov 24, 2026)

**Pages.** 379 URLs: 20 random Wikipedia articles per language and the current entries of one public news feed per language (BBC, El País, Le Monde, Tagesschau, Folha, Corriere, NOS, TVN24, SVT, Lenta.ru, NHK, BBC Chinese), built by `docs/bench/pages_12_languages.py` so the list is not chosen by hand (`urls.txt`, `sources.json`). Fetched once over plain HTTP with robots.txt respected: 368 read, 11 not (refused or failed; not retried another way). The fetched HTML is not published.

**Result.** 0 of 368 pages flagged at any severity (`results-0.24.0.json`), per language: English 32, Spanish 29, French 32, German 32, Portuguese 31, Italian 32, Dutch 32, Polish 32, Swedish 32, Russian 32, Japanese 20, Chinese 32, all with no findings. 95% interval for the medium-or-high rate: 0–1.0%.

**Scan time.** The same saved pages scanned with internal 0.23.0 and internal 0.24.0 on one machine: 27.4 s and 56.8 s in all (`timing.json`). internal 0.24.0 takes about 2.1× as long, from the five added languages and the extra joined-sentence pass; per page it is still well under a second.

**Limits.** Wikipedia and news pages are not shopping or forum pages; the field studies cover those. Nothing here was used to write a pattern.

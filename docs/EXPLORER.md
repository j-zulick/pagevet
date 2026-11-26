# Field-study explorer

One self-contained HTML page over PageVet's committed results: every number in it can be filtered down to the pages behind it.

- **Online:** https://j-zulick.github.io/pagevet/ (GitHub Pages, served from the `gh-pages` branch; each release replaces it when the repository variable `PAGES_PUBLISH` is `true`).
- **Offline:** each release carries `explore.html`; or build it: `pagevet-study explore docs/bench/*-field-* --out site/` and open `site/index.html`.

## What it shows

Three datasets, one engine:

| Tab | Records | Source (committed) |
|---|---|---|
| Field studies | 367 pages (273 read) from six studies | `docs/bench/*-field-*/results.json` and `study.json` |
| False-alarm pages | 1,217 records (990 read): five plain-HTTP sets in twelve languages (1,121, 974 read) and the 96 pages plain HTTP could not read, retried through crawlee-server 2.2.0 (16 read) | `docs/bench/2026-11-19-{clean,fresh,intl,it-nl}-pages/`, `docs/bench/2026-11-24-pages-12-languages/` |
| Benchmark cases | 1,134 evasion cases (development, held-out 1, held-out 2) | `docs/bench/2026-11-19-evasion/results-<newest>.json`; BIPIA as its committed totals (its data is not redistributed) |

**Facets.** Field studies: study, language ("not recorded in this study": the studies did not record page language), run date, PageVet version, read outcome, how read, highest severity of text aimed at AI, finding category, number of the three tested AI crawlers not served, crawler groups with one not served (search, training; the studies tested no fetch-on-request crawler), each crawler's response (served / not served with the status / served different text / not tested), different text served, AI share links (none / summary prompts only / prompt with instructions; "not tested in this study" for studies run before share links were recorded), how read (plain HTTP, or Firecrawl for the AI share-button study), and the robots-rule, llms.txt and noai facets, which read "not tested in this study" because these studies predate `pagevet-access`. False-alarm pages: set, language, rules version, read outcome, how read (plain HTTP or crawlee-server), highest severity, category, domain. A crawlee-server retry is a separate record from the plain-HTTP attempt at the same URL, so filter by set or "how read" to count each URL once. Benchmarks: case set, language, disguise technique, instruction type, expected label, caught or missed.

**Headline bar**, recomputed for the current filter: pages, pages read (and not read, counted separately), pages with text aimed at AI with a Wilson 95% interval, and for field studies the share refusing at least one of the three AI crawlers. Benchmarks show caught and missed, and the BIPIA totals.

**Page drawer:** response status, how the page was read, every facet value, each finding's severity, location, kinds, short quote and reason, the AI-crawler evidence, hashes where the data has them, and the commands to re-check that page.

**Compare:** two studies side by side (differences highlighted), and two PageVet builds on identical saved bytes (the twelve-language pages before and after five languages were added), listing only the pages they rate differently.

**Reproduce this view:** the `pagevet-study report` / `compare` commands that regenerate the numbers from the committed data, and the explore command with the current filter.

## How the numbers are computed

- **One record list.** `pagevet.explore.build_data` normalises every source into records with a `schema_version`; each record carries its facet values as lists. Facet definitions live in Python and are embedded with the data.
- **Disjunctive counts.** For each facet, a value's count is the number of records that have that value and pass every *other* facet's filter (and the text search). Values are OR'd within a facet and AND'd across facets, so picking one value still shows the others' counts.
- **Two implementations, one rule.** `facet_counts` and `headline` in Python are the reference; the page's JavaScript applies the same rules. A browser test loads the page with fixed filters and checks every displayed count and headline number equals Python's.
- **Not read is not clean.** A page PageVet could not read has severity "not read" and every crawler facet "not tested"; it is counted under "not read" and never in the denominator of a rate.
- **Published figures.** With no filter, the field-study headline is computed by the same `summarize` that wrote `docs/bench/FIELD-STUDIES.md` and the README sentence; a test fails if the table, the README sentence or the headline drift apart.

## Integrity and privacy

- The data block's SHA-256 is in the page; the page verifies it before showing anything. A hash mismatch or an unknown `schema_version` shows an error and no partial results.
- Strict Content-Security-Policy: `default-src 'none'`, the one inline script and one inline style allowed by hash, nothing loaded from anywhere. All data is written with `textContent`.
- The same inputs give byte-identical output.
- The privately supplied page sample is never read; a test fails if any of its URLs appears in the page.
- Short excerpts only; no page text beyond them.

## Wording

A site refusing AI crawlers is described as a choice, not a finding. "Served different text to <crawler>" states only that the text differed. Pages not read are never "no findings".

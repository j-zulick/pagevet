# PDFs: a first false-alarm check (Nov 19, 2026)

**Question.** Does PDF scanning (internal 0.17.0) flag ordinary documents?

**Set.** The five most recent arXiv submissions in each of six unrelated categories (astro-ph.GA, q-bio.PE, econ.GN, math.CO, physics.flu-dyn, cond-mat.mtrl-sci), taken from arXiv's public API: 30 PDF URLs (`urls.txt`), not chosen by hand.

**Run.** `pagevet --urls urls.txt --delay 1 --format json`, with robots.txt respected (`results.json`).

## Result
- **Read:** 28 PDFs. 2 were refused because they are over the 20 MB limit.
- **Findings:** 0 at any severity, in page text or in metadata and annotations.

## Limits
Thirty academic papers is a small, uniform set. Reports, brochures and white papers, where marketing text and form fields are more common, are not covered. Text drawn invisibly on a page (white, tiny or off-page) is extracted as ordinary page text, so it is rated as visible.

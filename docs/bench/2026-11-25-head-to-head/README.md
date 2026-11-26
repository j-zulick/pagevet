# Head-to-head: PageVet's patterns and an open-weights classifier (2026-11-25)

**Detectors.** PageVet pre-release (2026-11-25) patterns, and ProtectAI's `protectai/deberta-v3-base-prompt-injection-v2` (Apache-2.0, not gated) run locally on CPU through `--detector protectai` (512-token windows, a text is flagged when any window scores ≥ 0.5 on the model's `INJECTION` label). Same cases, same day. Data are not copied here; each result file records the SHA-256 of the cases it ran on.

| Set | Patterns: caught | Patterns: false alarms | Classifier: caught | Classifier: false alarms |
|---|---|---|---|---|
| BIPIA EmailQA text attacks (`2026-11-19-bipia`) | 1,450 of 3,750 (38.7%) | **0 of 50** | **2,226 of 3,750 (59.4%)** | 31 of 50 (62%) |
| deepset/prompt-injections, test (`2026-11-25-deepset`) | 2 of 60 | 0 of 56 | **22 of 60** | 0 of 56 |
| Evasion cases as plain text (1,134, all injected) | **847** | n/a | 810 | n/a |
| 1,052 real pages (false alarms only) | n/a | **3** (1 medium, 2 low) | n/a | 147 (14%) |

Evasion cases by group (patterns / classifier): development disguises **237** / 162 of 252; held-out disguises **195** / 160 of 252; reworded without trigger phrases 0 / **3** of 18; development translations **198** / 175 of 198; held-out translations 111 / **175** of 198; second held-out set (new phrasings) 69 / **172** of 216.

**What this says.**
- The two fail differently. Patterns almost never raise a false alarm and catch disguised text the classifier misses (look-alike letters, ROT13, reversed text, letter spacing). The classifier generalizes far better to new phrasings and translations, but on BIPIA it flagged 31 of 50 ordinary emails.
- So the classifier is a second opinion, not a replacement: PageVet attaches its score to findings (`--second-opinion protectai`) and never lets it change a severity.
- The evasion cases here are scanned as plain text by `pagevet-bench`, not as pages, so the patterns' numbers differ a little from [EVASION.md](../../EVASION.md), which scans each case inside a page.
- ProtectAI's training data may include public prompt-injection sets such as deepset's; that was not checked, so treat its deepset figure as optimistic.
- **False alarms on real pages** (`results-pages-protectai.jsonl`): on the 1,052 saved pages of the false-alarm re-scan (`docs/bench/2026-11-25-false-alarms/`), the classifier flagged **147 pages (14%)**; PageVet's patterns flagged 3 (1 medium, 2 low, all in comment threads; `../2026-11-25-false-alarms/`). By list: English homepages 5 of 186, English articles and forums 2 of 153, but Spanish/French/German/Portuguese 42 of 142, Italian/Dutch 21 of 100, twelve languages 69 of 341, the privately supplied sample 8 of 130. Read with one 512-token window per page (about the first 2,000 characters of everything a model reads), on CPU, 32 minutes. On ordinary pages, and especially non-English ones, the classifier alone would bury real findings in false alarms.
- Llama Prompt Guard 2 (gated), Jev and the `llm` second opinion need keys and are not in this table.

**Reproduce.** `uv run --extra classifier pagevet-bench CASES.jsonl --detector protectai --out results.json` (cases built with `bipia_build.py`, `deepset_build.py`; evasion cases from `evasion_run.py`'s texts).

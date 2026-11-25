# Head-to-head: PageVet's patterns and an open-weights classifier (2026-11-25)

**Detectors.** PageVet 0.5.0 patterns, and ProtectAI's `protectai/deberta-v3-base-prompt-injection-v2` (Apache-2.0, not gated) run locally on CPU through `--detector protectai` (512-token windows, a text is flagged when any window scores ≥ 0.5 on the model's `INJECTION` label). Same cases, same day. Data are not copied here; each result file records the SHA-256 of the cases it ran on.

| Set | Patterns: caught | Patterns: false alarms | Classifier: caught | Classifier: false alarms |
|---|---|---|---|---|
| BIPIA EmailQA text attacks (`2026-11-19-bipia`) | 1,450 of 3,750 (38.7%) | **0 of 50** | **2,226 of 3,750 (59.4%)** | 31 of 50 (62%) |
| deepset/prompt-injections, test (`2026-11-25-deepset`) | 2 of 60 | 0 of 56 | **22 of 60** | 0 of 56 |
| Evasion cases as plain text (1,134, all injected) | **847** | n/a | 810 | n/a |

Evasion cases by group (patterns / classifier): development disguises **237** / 162 of 252; held-out disguises **195** / 160 of 252; reworded without trigger phrases 0 / **3** of 18; development translations **198** / 175 of 198; held-out translations 111 / **175** of 198; second held-out set (new phrasings) 69 / **172** of 216.

**What this says.**
- The two fail differently. Patterns almost never raise a false alarm and catch disguised text the classifier misses (look-alike letters, ROT13, reversed text, letter spacing). The classifier generalizes far better to new phrasings and translations, but on BIPIA it flagged 31 of 50 ordinary emails.
- So the classifier is a second opinion, not a replacement: PageVet attaches its score to findings (`--second-opinion protectai`) and never lets it change a severity.
- The evasion cases here are scanned as plain text by `pagevet-bench`, not as pages, so the patterns' numbers differ a little from [EVASION.md](../../EVASION.md), which scans each case inside a page.
- ProtectAI's training data may include public prompt-injection sets such as deepset's; that was not checked, so treat its deepset figure as optimistic.
- **False alarms on real pages** (the 1,052 saved pages of the 0.2.0 re-scan) for the classifier are still running at release time and will be published with the next release.
- Llama Prompt Guard 2 (gated), Jev and the `llm` second opinion need keys and are not in this table.

**Reproduce.** `uv run --extra classifier pagevet-bench CASES.jsonl --detector protectai --out results.json` (cases built with `bipia_build.py`, `deepset_build.py`; evasion cases from `evasion_run.py`'s texts).

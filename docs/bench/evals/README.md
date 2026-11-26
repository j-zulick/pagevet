# Pydantic Evals harness

PageVet's frozen benchmark sets run through [Pydantic Evals](https://ai.pydantic.dev/evals/) (`pydantic_evals.Dataset.evaluate_sync`). `pydantic-evals` is a dev dependency only; the package does not need it.

```bash
uv run python docs/bench/evals/run_evals.py                                   # evasion and hiding, built on the fly
uv run python docs/bench/scripts/bench_sets.py build sets/ --bipia BIPIA/benchmark --deepset deepset.jsonl --saved-pages pages.jsonl.gz
uv run python docs/bench/evals/run_evals.py sets/ --out evals.json            # every built set, patterns only
uv run python docs/bench/evals/run_evals.py sets/ --models auto --limit 50    # plus each model second opinion whose keys exist
```

Each case is one line of a set built by [`bench_sets.py`](../scripts/bench_sets.py): the case is the `inputs`, `label == 1` the expected output. Page cases (`"format": "html"`) are judged with `scan_text`, text cases with the patterns detector, which is how the published reports count them.

| Evaluator | Passes when | Cases |
|---|---|---|
| `ExpectedFinding` | the case is flagged | attack cases |
| `NoFalseAlarm` | the case is not flagged | clean cases |
| `LatencyUnderBudget` | judging took at most `--budget-ms` (default 50) | all |

Cases run one at a time, timed around the judgement only. Model second opinions run only when named with `--models` and configured (see the Configuration table in [USAGE](../../USAGE.md#configuration)); `llm` and `jev` are billed and capped at `--limit` cases per set. The output names the date, the PageVet version and each set's SHA-256.

The output is a measurement record, not a claim: publish a number from it only with the output file, the sets' SHA-256 and the date, under a dated folder in `docs/bench/`.

"""PageVet's frozen benchmark sets as Pydantic Evals cases (dev tool; pydantic-evals is a dev dependency only).

    uv run python docs/bench/evals/run_evals.py                          # evasion and hiding, built on the fly; patterns only
    uv run python docs/bench/evals/run_evals.py SETS_DIR --out results.json   # every set bench_sets.py built into SETS_DIR
    uv run python docs/bench/evals/run_evals.py SETS_DIR --models auto --limit 50   # also each model second opinion whose keys exist

Each case of a set (``docs/bench/scripts/bench_sets.py``) becomes a ``pydantic_evals.Case`` with the case as its
inputs and ``label == 1`` as the expected output, and the set runs through ``Dataset.evaluate_sync``. Evaluators:

- ``ExpectedFinding``: an attack case is flagged (attack cases only);
- ``NoFalseAlarm``: a clean case is not flagged (clean cases only);
- ``LatencyUnderBudget``: judging the case took at most ``--budget-ms`` milliseconds (default 50), timed around the
  judgement itself; cases run one at a time so the timing is not shared with other cases.

The patterns run fully offline and are always judged. Model second opinions (``pagevet.detectors``) run only when
asked for with ``--models`` (a list, or ``auto`` for all) *and* their keys or local service are configured; the others
are listed as skipped. The billed ones (``llm``, ``jev``) are capped at ``--limit`` cases per set (default 50).
A model judges the case's text as given (page HTML for page cases). The output is a summary per set and detector,
dated, with each set's SHA-256, so a published number can name the run that made it.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs/bench/scripts"))

BILLED = {"llm", "jev"}


def available_models(env: dict | None = None) -> dict[str, str]:
    """{detector: why it can run} for each model second opinion whose keys or local service are configured."""
    env = os.environ if env is None else env
    has = lambda mod: importlib.util.find_spec(mod) is not None  # noqa: E731
    out = {}
    if env.get("OPENROUTER_API_KEY") and env.get("PAGEVET_LLM_MODEL"):
        out["llm"] = "OPENROUTER_API_KEY and PAGEVET_LLM_MODEL (billed)"
    if env.get("OPENROUTER_API_KEY") or env.get("TYPESAFE_API_KEY"):
        out["jev"] = "OPENROUTER_API_KEY or TYPESAFE_API_KEY (billed)"
    if env.get("HF_TOKEN") and has("transformers"):
        out["promptguard"] = "HF_TOKEN and the classifier extra"
    if env.get("PAGEVET_PROTECTAI_MODEL") and has("transformers"):
        out["protectai"] = "PAGEVET_PROTECTAI_MODEL and the classifier extra"
    if env.get("OLLAMA_HOST"):
        out["ollama"] = "OLLAMA_HOST (local)"
    return out


# --- evaluators ------------------------------------------------------------------------------------

@dataclass
class ExpectedFinding(Evaluator):
    """An attack case gets flagged."""

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        return {"expected_finding": bool(ctx.output["flagged"])} if ctx.expected_output else {}


@dataclass
class NoFalseAlarm(Evaluator):
    """A clean case does not get flagged."""

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        return {} if ctx.expected_output else {"no_false_alarm": not ctx.output["flagged"]}


@dataclass
class LatencyUnderBudget(Evaluator):
    """Judging the case took at most ``budget_ms`` milliseconds."""

    budget_ms: float = 50.0

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        return {"latency_under_budget": ctx.output["ms"] <= self.budget_ms}


# --- running ---------------------------------------------------------------------------------------

def load_set(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dataset(name: str, cases: list[dict], budget_ms: float) -> Dataset:
    return Dataset(name=name, cases=[Case(name=str(c["id"]), inputs=c, expected_output=bool(c["label"]),
                                          metadata={"group": str(c.get("group", "")), "set": name}) for c in cases],
                   evaluators=[ExpectedFinding(), NoFalseAlarm(), LatencyUnderBudget(budget_ms)])


def task_for(detector_name: str):
    from pagevet.bench import judge_case

    if detector_name == "patterns":
        def patterns(case: dict) -> dict:
            flagged, ms, kinds = judge_case(case)
            return {"flagged": flagged, "ms": ms, "kinds": kinds}
        return patterns

    from pagevet.detectors import build

    detector = build(detector_name)

    def model(case: dict) -> dict:
        t0 = time.perf_counter()
        verdict = detector.judge([case["text"]])[0]
        return {"flagged": verdict.flagged, "ms": (time.perf_counter() - t0) * 1000, "kinds": verdict.detail}
    return model


def summarize(report) -> dict:
    counts: dict[str, list[int]] = {}
    ms = []
    for case in report.cases:
        ms.append(case.output["ms"])
        for name, result in case.assertions.items():
            slot = counts.setdefault(name, [0, 0])
            slot[0] += bool(result.value)
            slot[1] += 1
    failures = len(getattr(report, "failures", []) or [])
    ordered = sorted(ms)
    return {"cases": len(report.cases), "task_failures": failures,
            **{name: {"passed": p, "of": n} for name, (p, n) in sorted(counts.items())},
            "median_ms": round(ordered[len(ordered) // 2], 3) if ordered else None,
            "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 3) if ordered else None}


def run(sets_dir: Path, budget_ms: float = 50.0, models: list[str] | None = None, limit: int = 50,
        only: list[str] | None = None, env: dict | None = None) -> dict:
    import hashlib

    from pagevet import __version__

    avail = available_models(env)
    wanted = list(avail) if models == ["auto"] else (models or [])
    skipped = {m: "no keys or service configured" for m in wanted if m not in avail}
    detectors = ["patterns"] + [m for m in wanted if m in avail]
    out: dict = {"tool": "pagevet docs/bench/evals", "pagevet": __version__, "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                 "budget_ms": budget_ms, "models_skipped": skipped, "sets": {}}
    for path in sorted(sets_dir.glob("*.jsonl")):
        if only and path.stem not in only:
            continue
        cases = load_set(path)
        entry = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "cases": len(cases), "detectors": {}}
        for name in detectors:
            subset = cases[:limit] if name in BILLED and limit else cases
            report = dataset(path.stem, subset, budget_ms).evaluate_sync(task_for(name), name=f"{path.stem}-{name}",
                                                                          max_concurrency=1, progress=False)
            entry["detectors"][name] = summarize(report)
        out["sets"][path.stem] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_evals.py", description=__doc__.split("\n", 1)[0])
    parser.add_argument("sets_dir", nargs="?", type=Path, help="folder written by bench_sets.py build (default: build evasion and hiding now)")
    parser.add_argument("--sets", default="", help="comma-separated set names to run (default: all in the folder)")
    parser.add_argument("--budget-ms", type=float, default=50.0)
    parser.add_argument("--models", default="", help="model second opinions to add: auto, or names such as llm,jev,ollama")
    parser.add_argument("--limit", type=int, default=50, help="cases per set for billed models (0 = all)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    models = [m.strip() for m in args.models.split(",") if m.strip()] or None
    with tempfile.TemporaryDirectory() as t:
        sets_dir = args.sets_dir
        if sets_dir is None:
            import bench_sets

            sets_dir = Path(t)
            bench_sets.build(sets_dir)
        result = run(sets_dir, args.budget_ms, models, args.limit, [s for s in args.sets.split(",") if s] or None)
    text = json.dumps(result, indent=1) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Freeze PageVet's benchmark sets as labelled cases, one JSONL file per benchmark, and track them in Langfuse.

    uv run python docs/bench/scripts/bench_sets.py build OUT_DIR                     # evasion and hiding (always in the repo)
    uv run python docs/bench/scripts/bench_sets.py build OUT_DIR --bipia BIPIA/benchmark --deepset deepset.jsonl \\
        --saved-pages pages.jsonl.gz [--agentdojo]                                   # the sets whose data lives elsewhere
    uv run python docs/bench/scripts/bench_sets.py langfuse OUT_DIR                  # one Langfuse experiment per built set

Each line is ``{"id", "text", "label", "group", "format"}``, the format ``pagevet-bench`` reads. ``label`` is 1 for a
case that carries an injected instruction and 0 for a clean one. ``format`` says how a case is judged, the same way
the benchmark's own published run judged it: ``"html"`` is scanned with ``pagevet.scan.scan_text`` (a page counts as
caught when it gets any finding), ``"text"`` with the patterns detector, as ``pagevet-bench`` always has.

Sets and where their cases come from:

- ``evasion``: ``evasion_run.py``'s cases (seed instructions with invented brands, disguised); all label 1.
- ``hiding``: ``hiding_run.py``'s cases (the same seeds, hidden in small pages); all label 1.
- ``bipia``: ``bipia_build.py`` from a checkout of microsoft/BIPIA's ``benchmark`` folder (``--bipia``).
- ``deepset``: a file built by ``deepset_build.py`` (``--deepset``); it needs the network, so it is built separately.
- ``false-alarms``: the saved pages of the 1,052-page false-alarm re-scan (``--saved-pages``, the gzipped JSON lines
  written by ``pages_12_languages.py fetch``: one ``{"url", "html", "set" or "lang"}`` per page). All label 0. The
  pages are never committed; rows from the privately supplied sample (``set`` ``"joe"``) are marked ``private`` so
  their text is never sent anywhere.
- ``agentdojo-offline``: AgentDojo's own tool outputs from its ground-truth tool calls (``--agentdojo``, needs
  ``agentdojo`` installed; about 25 minutes): clean outputs label 0, outputs that carry an attack label 1, grouped by
  attack. Uses only AgentDojo's tasks and attacks.

Sets whose data is not supplied are skipped and listed as skipped; nothing is fetched to fill them in. Nothing here
creates or varies an injection: the sets are the benchmarks' own cases.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PRIVATE_SETS = {"joe"}  # the privately supplied sample: counted, never uploaded


def evasion_cases() -> list[dict]:
    import evasion_run

    return [{"id": f"evasion-{i}", "text": evasion_run.page(inner), "label": 1, "group": technique, "format": "html"}
            for i, (_, technique, _, _, inner) in enumerate(evasion_run.iter_cases())]


def hiding_cases() -> list[dict]:
    import hiding_run

    return [{"id": f"hiding-{i}", "text": page, "label": 1, "group": f"{method} ({label})", "format": "html"}
            for i, (method, label, _, _, page) in enumerate(hiding_run.iter_pages())]


def bipia_cases(bipia: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "bipia.jsonl"
        subprocess.run([sys.executable, str(HERE / "bipia_build.py"), str(bipia), str(out)], check=True, capture_output=True)  # noqa: S603
        return [{**json.loads(line), "format": "text"} for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]


def jsonl_cases(path: Path, fmt: str = "text") -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [{**r, "format": r.get("format", fmt)} for r in rows]


def saved_page_cases(path: Path) -> list[dict]:
    out = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if "html" not in row:  # not read when the pages were saved: never counted as clean
                continue
            group = row.get("set") or row.get("lang") or ""
            case = {"id": "page-" + hashlib.sha256(row["url"].encode()).hexdigest()[:16], "text": row["html"], "label": 0,
                    "group": group, "format": "html"}
            if group in PRIVATE_SETS:
                case["private"] = True
            else:
                case["url"] = row["url"]
            out.append(case)
    return out


def agentdojo_cases() -> list[dict]:  # pragma: no cover - needs agentdojo
    import agentdojo_guard as ad

    BasePipelineElement, _, load_attack, _, get_suites, _ = ad._ad()

    class Target(BasePipelineElement):
        name = "local"

        def query(self, *args, **kwargs):
            raise NotImplementedError

    out: list[dict] = []
    for name, suite in sorted(get_suites(ad.VERSION).items()):
        for task in suite.user_tasks.values():
            for k, text in enumerate(ad.tool_outputs(suite, task, {})):
                out.append({"id": f"agentdojo-{name}-{task.ID}-clean-{k}", "text": text, "label": 0, "group": f"{name}: clean", "format": "html"})
        for attack_name in ad.ATTACKS:
            attack = load_attack(attack_name, suite, Target())
            for task in suite.user_tasks.values():
                for inj in suite.injection_tasks.values():
                    injections = attack.attack(task, inj)
                    payloads = [v for v in injections.values() if v]
                    outputs = [o for o in ad.tool_outputs(suite, task, injections) if any(ad._norm(p)[:60] in ad._norm(o) for p in payloads)]
                    for k, text in enumerate(outputs):
                        out.append({"id": f"agentdojo-{name}-{attack_name}-{task.ID}-{inj.ID}-{k}", "text": text, "label": 1,
                                    "group": attack_name, "format": "html"})
    return out


def write(cases: list[dict], path: Path) -> str:
    path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out: Path, bipia: Path | None = None, deepset: Path | None = None, saved_pages: Path | None = None,
          agentdojo: bool = False) -> dict:
    """Write one JSONL file per available set into ``out``; return {set: {"cases", "sha256"} or {"skipped": why}}."""
    out.mkdir(parents=True, exist_ok=True)
    sources = {
        "evasion": evasion_cases,
        "hiding": hiding_cases,
        "bipia": (lambda: bipia_cases(bipia)) if bipia else "no --bipia folder",
        "deepset": (lambda: jsonl_cases(deepset)) if deepset else "no --deepset file (build it with deepset_build.py)",
        "false-alarms": (lambda: saved_page_cases(saved_pages)) if saved_pages else "no --saved-pages file (the pages are not committed)",
        "agentdojo-offline": agentdojo_cases if agentdojo else "no --agentdojo",
    }
    summary: dict = {}
    for name, source in sources.items():
        if isinstance(source, str):
            summary[name] = {"skipped": source}
            continue
        cases = source()
        summary[name] = {"cases": len(cases), "attacks": sum(c["label"] for c in cases), "sha256": write(cases, out / f"{name}.jsonl")}
    (out / "sets.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def langfuse(out: Path) -> int:
    """Run ``pagevet-bench --langfuse-dataset`` once per built set; each set is its own dataset."""
    from pagevet.bench import main as bench

    worst = 0
    for path in sorted(out.glob("*.jsonl")):
        worst = max(worst, bench([str(path), "--langfuse-dataset", path.stem]))
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_sets.py", description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write the frozen sets")
    b.add_argument("out", type=Path)
    b.add_argument("--bipia", type=Path, metavar="DIR")
    b.add_argument("--deepset", type=Path, metavar="FILE")
    b.add_argument("--saved-pages", type=Path, metavar="FILE")
    b.add_argument("--agentdojo", action="store_true")
    lf = sub.add_parser("langfuse", help="one Langfuse experiment per built set")
    lf.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "langfuse":
        return langfuse(args.out)
    summary = build(args.out, args.bipia, args.deepset, args.saved_pages, args.agentdojo)
    for name, s in summary.items():
        line = f"skipped: {s['skipped']}" if "skipped" in s else f"{s['cases']} cases ({s['attacks']} attacks), sha256 {s['sha256'][:16]}…"
        sys.stdout.write(f"{name:18} {line}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

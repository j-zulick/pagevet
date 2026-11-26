"""Regenerate PageVet's published offline numbers with one command, and say whether they still match (0.4.0).

    uv run pagevet-reproduce                     # from a checkout of the repository
    uv run pagevet-reproduce --bipia BIPIA/benchmark
    uv run --with agentdojo pagevet-reproduce --agentdojo     # also the guard on AgentDojo (about 25 minutes)

Checks, each against the committed result it reproduces:
- the evasion report (every technique's caught count): docs/bench/2026-11-19-evasion/, newest result;
- the hiding-method report (every method's counts): docs/bench/2026-11-19-hiding/, newest result;
- the rules file: docs/rules/pagevet-rules.json;
- with ``--bipia DIR`` (a checkout of microsoft/BIPIA's ``benchmark`` folder): the BIPIA catch and false-alarm counts;
- with ``--agentdojo`` (needs ``agentdojo`` installed): the guard's counts on AgentDojo's tool outputs (1.2.0), without
  a model: docs/bench/2026-11-25-agentdojo-guard/results-offline.json. Timing is not compared.
Numbers that need the network (real-page false alarms, field studies) are reproduced with the scripts named in
each result folder's README; their saved pages are not committed. Exit code 0 when everything matches.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pagevet import __version__


def _newest(folder: Path, pattern: str) -> Path:
    def key(p: Path) -> tuple:
        nums = re.findall(r"\d+", p.stem)
        return (("public" in p.stem), tuple(int(n) for n in nums))
    files = sorted(folder.glob(pattern), key=key)
    if not files:
        raise FileNotFoundError(f"no {pattern} in {folder}")
    return files[-1]


def _run(root: Path, *args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=root, check=True, capture_output=True)  # noqa: S603


def check_evasion(root: Path, tmp: Path) -> tuple[bool, str]:
    committed = _newest(root / "docs/bench/2026-11-19-evasion", "results-*.json")
    _run(root, "docs/bench/evasion_run.py", str(tmp), "evasion.json")
    want = {r["technique"]: r["caught"] for r in json.loads(committed.read_text())["by_technique"]}
    got = {r["technique"]: r["caught"] for r in json.loads((tmp / "evasion.json").read_text())["by_technique"]}
    diff = sorted(k for k in want.keys() | got.keys() if want.get(k) != got.get(k))
    return not diff, f"evasion vs {committed.name}: " + ("match" if not diff else f"differs on {', '.join(diff[:5])}")


def check_hiding(root: Path, tmp: Path) -> tuple[bool, str]:
    committed = _newest(root / "docs/bench/2026-11-19-hiding", "results-*.json")
    _run(root, "docs/bench/hiding_run.py", str(tmp / "hiding.json"))
    same = json.loads(committed.read_text())["methods"] == json.loads((tmp / "hiding.json").read_text())["methods"]
    return same, f"hiding vs {committed.name}: " + ("match" if same else "differs")


def check_rules(root: Path) -> tuple[bool, str]:
    from pagevet.rules import render

    same = (root / "docs/rules/pagevet-rules.json").read_text(encoding="utf-8") == render()
    return same, "rules file: " + ("match" if same else "differs (run pagevet-rules --out docs/rules/pagevet-rules.json)")


def check_bipia(root: Path, tmp: Path, bipia: Path) -> tuple[bool, str]:
    _run(root, "docs/bench/bipia_build.py", str(bipia), str(tmp / "bipia.jsonl"))
    out = subprocess.run([sys.executable, "-m", "pagevet.bench", str(tmp / "bipia.jsonl"), "--out", str(tmp / "bipia.json")],  # noqa: S603
                         cwd=root, capture_output=True, text=True)
    if out.returncode not in (0, 1):
        return False, f"BIPIA: bench failed: {out.stderr.strip()[-200:]}"
    got = json.loads((tmp / "bipia.json").read_text())
    want = json.loads((root / "docs/bench/2026-11-19-bipia/results-0.24.0.json").read_text())
    keys = ("catch_rate", "false_alarm_rate")
    same = all(got[k].get("hits") == want[k].get("hits") and got[k].get("n") == want[k].get("n") for k in keys)
    return same, f"BIPIA: {got['catch_rate'].get('hits')}/{got['catch_rate'].get('n')} caught, " \
                 f"{got['false_alarm_rate'].get('hits')}/{got['false_alarm_rate'].get('n')} false alarms: " + ("match" if same else "differs")


AGENTDOJO = "docs/bench/2026-11-25-agentdojo-guard/results-offline.json"


def _agentdojo_counts(data: dict) -> dict:
    return {suite: {"clean": {k: v for k, v in s["clean"].items() if k != "examples"}, "attacks": s["attacks"]}
            for suite, s in data["suites"].items()}


def check_agentdojo(root: Path, tmp: Path) -> tuple[bool, str]:
    import importlib.util

    if importlib.util.find_spec("agentdojo") is None:
        return False, "AgentDojo: not installed (uv run --with agentdojo pagevet-reproduce --agentdojo)"
    want = json.loads((root / AGENTDOJO).read_text())
    _run(root, "docs/bench/agentdojo_guard.py", "offline", str(tmp / "agentdojo.json"), "--version", want["benchmark"].split()[-1])
    got = json.loads((tmp / "agentdojo.json").read_text())
    same = _agentdojo_counts(got) == _agentdojo_counts(want)
    return same, f"AgentDojo guard ({want['benchmark']}): " + ("match" if same else "counts differ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-reproduce", description="Regenerate PageVet's published offline numbers.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", default=".", help="the repository checkout (default: current folder)")
    parser.add_argument("--bipia", metavar="DIR", help="microsoft/BIPIA benchmark folder, to reproduce the BIPIA counts too")
    parser.add_argument("--agentdojo", action="store_true", help="also the guard's counts on AgentDojo (needs agentdojo installed)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / "docs/bench/evasion_run.py").exists():
        parser.error(f"{root} is not a PageVet checkout (docs/bench/ not found)")
    results = []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for check in (lambda: check_evasion(root, tmp), lambda: check_hiding(root, tmp), lambda: check_rules(root)):
            results.append(check())
        if args.bipia:
            results.append(check_bipia(root, tmp, Path(args.bipia).resolve()))
        if args.agentdojo:
            results.append(check_agentdojo(root, tmp))
    for ok, line in results:
        sys.stdout.write(("✓ " if ok else "✗ ") + line + "\n")
    return 0 if all(ok for ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

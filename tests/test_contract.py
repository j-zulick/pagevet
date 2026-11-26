"""Public interface: the documented commands, formats and Python names exist (docs/API.md, Stability)."""

import dataclasses
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {"pagevet", "pagevet-access", "pagevet-bench", "pagevet-discover", "pagevet-study", "pagevet-mcp", "pagevet-rules",
            "pagevet-view", "pagevet-reproduce", "pagevet-guard", "pagevet-serve", "pagevet-replay"}


def test_commands_match_the_documented_set():
    scripts = set(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"])
    assert scripts == COMMANDS
    api = (ROOT / "docs/API.md").read_text()
    assert all(f"`{c}`" in api for c in COMMANDS)


def test_schema_ids():
    assert json.loads((ROOT / "docs/schema/report.schema.json").read_text())["$id"] == "pagevet-report-1"
    assert json.loads((ROOT / "docs/schema/receipt.schema.json").read_text())["$id"] == "pagevet-receipt-1"
    from pagevet.rules import rules_data

    assert rules_data()["schema"] == "pagevet-rules-1"


def test_finding_and_result_fields():
    from pagevet.scan import Finding, PageResult

    assert [f.name for f in dataclasses.fields(Finding)] == ["channel", "kinds", "excerpt", "severity", "advice", "opinions", "taxonomy", "intent"]
    # ai_share_links is an optional field appended after them; the first four stay in place (docs/API.md: new optional fields)
    assert [f.name for f in dataclasses.fields(PageResult)] == ["source", "findings", "error", "evidence", "ai_share_links"]


def test_documented_python_names_exist():
    from pagevet import detectors, guard, replay, rules, scan, serve, view

    for mod, names in ((scan, ["scan_text", "scan_channels", "render", "render_json", "render_csv", "render_html", "render_sarif",
                               "render_receipt", "taxonomy"]),
                       (guard, ["guard", "GuardResult"]), (replay, ["replay", "Replay"]), (rules, ["rules_data"]),
                       (view, ["render_view"]), (serve, ["handle"]), (detectors, ["build", "REGISTRY"])):
        assert all(hasattr(mod, n) for n in names), mod.__name__

"""PageVet's detection rules as open data (0.3.0).

    pagevet-rules                 # JSON on stdout
    pagevet-rules --out rules.json

The same rules the scanner runs, exported so other tools can read, audit or reuse them: every instruction
pattern (regular expression source and flags), the hidden-text hints, the commercial-manipulation vocabulary,
the channels and how each is rated, and the framework IDs attached to findings. The committed copy is
docs/rules/pagevet-rules.json; a test keeps it identical to this output. Same license as the code (MIT).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pagevet import __version__, detect
from pagevet import scan as scan_mod


def _flags(rx: re.Pattern[str]) -> str:
    return "".join(c for c, f in (("i", re.I), ("m", re.M), ("s", re.S), ("x", re.X)) if rx.flags & f)


def _pattern(rx: re.Pattern[str]) -> dict:
    return {"regex": rx.pattern, "flags": _flags(rx), "dialect": "python-re"}


def rules_data() -> dict:
    """Return the rules as a JSON-serializable dict."""
    return {
        "schema": "pagevet-rules-1",
        "pagevet_version": __version__,
        "license": "MIT",
        "instruction_patterns": {k: _pattern(rx) for k, rx in detect.INSTRUCTION_PATTERNS.items()},
        "hidden_text_hints": {k: _pattern(rx) for k, rx in detect.HIDDEN_PATTERNS.items()},
        "commercial": {**_pattern(detect.COMMERCIAL), "window": {"before": 60, "after": detect.COMMERCIAL_WINDOW}},
        "disguises_undone": ["invisible characters", "look-alike letters", "letter spacing", "ROT13", "reversed text",
                             "split sentences", "Unicode tag characters", "base64"],
        "reader_channels": sorted(scan_mod.READER_CHANNELS),
        "severity": {
            "high": "an instruction in a channel readers can't see, an encoded or disguised one, or one served only to AI crawlers",
            "medium": "an instruction in visible or user-submitted text, with no sign the page is discussing injection",
            "low": "visible text that reads as discussion or a quoted example, a reply command alone, a repetitive page, "
                   "or llms.txt text addressed to AI systems",
        },
        "taxonomy": {
            "owasp": {"all_injection_findings": scan_mod.OWASP_LLM01},
            "atlas": {"all_injection_findings": scan_mod.ATLAS_INDIRECT, "role_change": scan_mod.ATLAS_JAILBREAK,
                      "hidden_or_disguised": scan_mod.ATLAS_OBFUSCATION},
        },
    }


def render() -> str:
    return json.dumps(rules_data(), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-rules", description="Print PageVet's detection rules as JSON.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--out", metavar="FILE", help="write to FILE instead of stdout")
    args = parser.parse_args(argv)
    text = render()
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

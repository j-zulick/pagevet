"""Build labelled cases from deepset/prompt-injections (Apache-2.0), test split, for pagevet-bench.

    uv run python docs/bench/scripts/deepset_build.py cases.jsonl

Rows come from the Hugging Face datasets server at run time; the data is not copied into this repository.
The SHA-256 of the built file is recorded with the results. Label 1 = injection, 0 = ordinary prompt.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx

URL = "https://datasets-server.huggingface.co/rows"


def main() -> int:
    out = Path(sys.argv[1])
    rows, offset = [], 0
    with httpx.Client(timeout=30) as client:
        while True:
            r = client.get(URL, params={"dataset": "deepset/prompt-injections", "config": "default", "split": "test",
                                        "offset": offset, "length": 100})
            r.raise_for_status()
            batch = r.json()["rows"]
            rows += [x["row"] for x in batch]
            if len(batch) < 100:
                break
            offset += 100
    with out.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(rows):
            fh.write(json.dumps({"id": f"deepset-test-{i}", "text": row["text"], "label": int(row["label"]),
                                 "group": "injection" if row["label"] else "clean"}, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    sys.stdout.write(f"{len(rows)} cases ({sum(r['label'] for r in rows)} injections) -> {out}  sha256 {sha}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

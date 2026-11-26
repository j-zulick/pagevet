"""Build labelled cases from a checkout of Microsoft's BIPIA benchmark (MIT), EmailQA contexts.

    git clone https://github.com/microsoft/BIPIA
    python docs/bench/scripts/bipia_build.py BIPIA/benchmark cases.jsonl

Clean cases are the test emails as shipped. Injected cases put each of the 75 test text attacks
into each email at the end, middle or start (cycling), as BIPIA's own builder positions them.
BIPIA's data is not copied into this repository; the build is deterministic, and the SHA-256 of
the built file is recorded with the results.
"""
import json
import sys
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[2])
emails = [json.loads(line)["context"] for line in (root / "email/test.jsonl").read_text().splitlines() if line.strip()]
attacks = json.loads((root / "text_attack_test.json").read_text())


def insert(context: str, attack: str, where: int) -> str:
    if where == 0:
        return f"{context}\n{attack}"
    if where == 1:
        cut = context.rfind(" ", 0, len(context) // 2) + 1
        return f"{context[:cut]}\n{attack}\n{context[cut:]}"
    return f"{attack}\n{context}"


rows = [{"id": f"clean-{i}", "text": e, "label": 0, "group": "clean"} for i, e in enumerate(emails)]
n = 0
for category, items in attacks.items():
    for a, attack in enumerate(items):
        for i, e in enumerate(emails):
            rows.append({"id": f"{category}-{a}-email{i}", "text": insert(e, attack, n % 3), "label": 1, "group": category})
            n += 1
out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
sys.stdout.write(f"{len(emails)} clean, {n} injected -> {out}\n")

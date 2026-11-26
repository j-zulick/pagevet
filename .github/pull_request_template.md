## What this changes
<!-- One or two sentences. Link the issue if there is one. -->

## Checks
- [ ] `uv run pytest -q` and `uv run ruff check .` pass (tests are offline)
- [ ] README and docs match the code in this change
- [ ] Any new detection-rate or false-alarm claim comes with its data, script and date in `docs/bench/`
- [ ] Pattern changes are recorded in CHANGELOG.md, developed on hand-written or training cases, never on a held-out set
- [ ] Detection only: nothing here generates injections or targets other detectors

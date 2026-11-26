# Working on PageVet

For coding agents and people.

## What this is
A scanner that finds text in web pages aimed at AI models. Deterministic, no model, no API key. `src/pagevet/detect.py` holds the patterns; `src/pagevet/scan.py` holds channels, severity, crawler comparison, reports and the command line; `sources.py` the Firecrawl and crawlee-server sources (the rendering path: no browser is bundled); `access.py` the AI-crawler access check; `explore.py` (and `explore_assets/`) the field-study explorer (docs/EXPLORER.md); `bench.py` the measurement command. Python API: `docs/API.md`.

## Commands
```bash
uv sync
uv run pytest -q          # offline; must pass before any commit
uv run ruff check .       # must pass
uv run pagevet tests/fixtures/sample.html
```

## Rules
- Tests are offline. Pass `fetcher=` / `agent_fetch=` to `main` instead of using the network.
- Detection only. Never add code that generates injections for use on real pages.
- Every README claim must match the code and tests in the same commit. No detection-rate claim without a published run (data, script, date).
- Record every pattern change in the CHANGELOG, with the measured effect.
- A pattern is developed on a train split or hand-written cases, never tuned on the test cases it is reported against; say so in the results if a test set was seen.
- Never read, print or commit `.env` or any key. Every setting is an environment variable listed in `.env.example` (empty values) and the Configuration table in `docs/USAGE.md`; a new one goes in both, with a test.
- Releases need the maintainer's approval. A version change merged to `main` releases itself (`.github/workflows/release.yml`).
- Versions: only release numbers (0.1.0 onward) appear in docs and code comments. Results from development builds before 0.1.0 (2026-11-19 to 2026-11-25) are labelled by date, for example "pre-release (2026-11-24)"; result files keep the build string they were written with, as recorded.
- Pin third-party actions to a full commit SHA with the version in a comment; Dependabot keeps them current.

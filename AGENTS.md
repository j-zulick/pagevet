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
- `detect.py` began as a copy of Crossvet's `injection_check.py` and has moved well ahead of it (see the CHANGELOG). Crossvet's copy is not changed from here. Record any pattern change in the CHANGELOG so it can be offered to Crossvet.
- A pattern is developed on a train split or hand-written cases, never tuned on the test cases it is reported against; say so in the results if a test set was seen.
- Never read, print or commit `.env` or any key. Every setting is an environment variable listed in `.env.example` (empty values) and the README's Configuration table; a new one goes in both, with a test.
- Publishing (releases, PyPI, the Marketplace listing) needs the maintainer's approval. A version change merged to `main` releases itself (`.github/workflows/release.yml`); the PyPI upload runs only when the repository variable `PYPI_PUBLISH` is `true`.
- Versions: public releases count up from 0.1.0 to 1.0. Development builds before 0.1.0 are "internal 0.x.y" in every doc; never write a bare internal number where it could be read as a public one.
- Pin third-party actions to a full commit SHA with the version in a comment; Dependabot keeps them current.

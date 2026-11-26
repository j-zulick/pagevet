# Contributing

Thanks for helping. PageVet is small on purpose: deterministic detection, no model needed, every claim backed by a test or a published run.

## Set up
```bash
git clone https://github.com/j-zulick/pagevet && cd pagevet
uv sync --all-extras
uv run pytest -q          # offline: no network, no keys
uv run ruff check .
```

## The rules (also in [AGENTS.md](AGENTS.md))
- **Detection only.** No code that generates injections for use on real pages. Test cases use invented brands.
- **Tests stay offline.** Pass `fetcher=` / `agent_fetch=` to `main` instead of using the network.
- **No claim without evidence.** A README statement needs code and a test in the same change; a detection rate needs a published run (data, script, date) under `docs/bench/`.
- **Never tune on a reported test set.** Develop patterns on hand-written cases or a train split; the evasion report's held-out seeds stay untouched.
- **Settings are environment variables**, listed in `.env.example` and the Configuration table in `docs/USAGE.md`, with a test. Never commit `.env` or a key.

## Reporting a missed injection or a false alarm
Use the **Missed injection or false alarm** issue form. The most useful report has the smallest HTML that reproduces it, the channel it was in (visible text, hidden element, comment, attribute, JSON-LD, PDF...), and what you expected. Please don't paste live malicious pages; a minimal copy with the brand replaced is enough.

## Pull requests
Small and focused, with a CHANGELOG line under `[Unreleased]`. CI runs the tests on Python 3.11 and 3.13 and runs the GitHub Action on a sample page.

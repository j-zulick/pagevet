"""Offline tests for the .env loader."""

import os

from pagevet.config import load_env_file


def test_loads_unset_variables_and_keeps_set_ones(tmp_path, monkeypatch):
    monkeypatch.delenv("PV_A", raising=False)
    monkeypatch.delenv("PV_B", raising=False)
    monkeypatch.delenv("PV_C", raising=False)
    monkeypatch.setenv("PV_KEEP", "from-env")
    f = tmp_path / ".env"
    f.write_text('# comment\n\nPV_A=plain # note\nexport PV_B="quoted # kept"\nPV_C=\'single\'\nPV_KEEP=from-file\nnot a line\n')
    assert load_env_file(f) == ["PV_A", "PV_B", "PV_C"]
    assert (os.environ["PV_A"], os.environ["PV_B"], os.environ["PV_C"]) == ("plain", "quoted # kept", "single")
    assert os.environ["PV_KEEP"] == "from-env"


def test_missing_file_is_fine(tmp_path):
    assert load_env_file(tmp_path / "nope.env") == []


def test_example_lists_every_setting_with_no_secret_values():
    from pathlib import Path
    example = (Path(__file__).parent.parent / ".env.example").read_text()
    for name in ("PAGEVET_FIRECRAWL_URL", "PAGEVET_FIRECRAWL_KEY", "PAGEVET_CRAWL_URL", "PAGEVET_CRAWL_TOKEN",
                 "HF_TOKEN", "PAGEVET_PROMPTGUARD_MODEL", "PAGEVET_SEARXNG_URL", "PAGEVET_SEARXNG_TOKEN", "TYPESAFE_API_KEY", "TYPESAFE_DEFAULT_MODEL",
                 "OPENROUTER_API_KEY", "PAGEVET_JEV_MODEL", "PAGEVET_LLM_MODEL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
                 "LANGFUSE_BASE_URL"):
        assert f"\n{name}=" in example
    for secret in ("KEY", "TOKEN"):
        for line in example.splitlines():
            if line.split("=")[0].endswith(secret):
                assert line.endswith("="), line


def test_every_setting_in_the_code_is_documented():
    import re
    from pathlib import Path

    root = Path(__file__).parent.parent
    used = set()
    for file in (root / "src" / "pagevet").glob("*.py"):
        used |= set(re.findall(r"(?:PAGEVET_[A-Z_]+|OPENROUTER_API_KEY|LANGFUSE_[A-Z_]+|TYPESAFE_[A-Z_]+|HF_TOKEN)", file.read_text()))
    example, readme = (root / ".env.example").read_text(), (root / "docs" / "USAGE.md").read_text()
    missing = sorted(n for n in used if f"\n{n}=" not in example or n not in readme)
    assert not missing, missing

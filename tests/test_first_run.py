"""What a new user meets first after installing PageVet from GitHub."""

from __future__ import annotations

import pytest

import pagevet
from pagevet import bench, discover, install_hint, mcp_server, scan, study


@pytest.mark.parametrize("main, prog", [
    (scan.main, "pagevet"),
    (bench.main, "pagevet-bench"),
    (discover.main, "pagevet-discover"),
    (study.main, "pagevet-study"),
    (mcp_server.main, "pagevet-mcp"),
])
def test_every_command_prints_its_version(main, prog, capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.strip() == f"{prog} {pagevet.__version__}"


def test_bare_pagevet_prints_the_full_help(capsys):
    with pytest.raises(SystemExit) as stop:
        scan.main([])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert "Check pages for text aimed at AI models" in err
    assert "--compare-agents" in err


def test_version_matches_the_package_metadata():
    text = open("pyproject.toml", encoding="utf-8").read()
    assert f'version = "{pagevet.__version__}"' in text


def test_install_hint_works_without_pypi():
    """Extras are installed from the tagged GitHub release, since PageVet is not on PyPI."""
    hint = install_hint("pdf")
    assert hint == f'pip install "pagevet[pdf] @ git+https://github.com/j-zulick/pagevet@v{pagevet.__version__}"'


def test_missing_extra_names_the_working_install_line(monkeypatch):
    """The error for a missing optional extra gives a command that works without PyPI."""
    import builtins

    real = builtins.__import__

    def no_pypdf(name, *args, **kwargs):
        if name == "pypdf" or name.startswith("pypdf."):
            raise ImportError("no pypdf")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pypdf)
    with pytest.raises(RuntimeError) as err:
        scan.pdf_channels(b"%PDF-1.4")
    assert "@ git+https://github.com/j-zulick/pagevet@v" in str(err.value)


def test_readme_install_lines_point_at_this_version():
    """Every pinned install or Action line in the README and docs/USAGE.md names the current version, and none needs PyPI."""
    import re

    readme = open("README.md", encoding="utf-8").read() + open("docs/USAGE.md", encoding="utf-8").read()
    pins = set(re.findall(r"j-zulick/pagevet@(v[\d.]+)", readme))
    assert pins == {f"v{pagevet.__version__}"}
    assert 'pip install "pagevet[' not in readme
    assert "pip install pagevet" not in readme
    containers = set(re.findall(r"ghcr\.io/j-zulick/pagevet:(\d+\.\d+\.\d+)", readme))
    assert containers <= {pagevet.__version__}

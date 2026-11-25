"""PageVet: find text in web pages that is aimed at AI models rather than readers."""

__version__ = "0.6.0"

REPOSITORY = "https://github.com/j-zulick/pagevet"


def install_hint(extra: str) -> str:
    """The command that adds an optional extra to this version (installed from GitHub, not PyPI)."""
    return f'pip install "pagevet[{extra}] @ git+{REPOSITORY}@v{__version__}"'

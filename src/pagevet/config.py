"""Settings from the environment, with an optional ``.env`` file in the current folder.

Every setting is an environment variable (listed in ``.env.example``). ``load_env_file`` reads
``KEY=value`` lines from ``.env`` so the commands work without exporting anything; a variable that
is already set in the environment always wins. Values are never printed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_env_file(path: str | os.PathLike[str] = ".env") -> list[str]:
    """Set variables from ``path`` that are not already set; return their names (not values).

    Blank lines and ``#`` comments are skipped; a value may be wrapped in single or double quotes;
    an unquoted value ends at `` #``. A missing file is not an error.
    """
    file = Path(path)
    if not file.is_file():
        return []
    loaded = []
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE.match(raw)
        if not m or raw.lstrip().startswith("#"):
            continue
        name, value = m.group(1), m.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded

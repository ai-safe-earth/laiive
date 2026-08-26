"""PostToolUse hook: run `ruff format` on edited Python files under services/.

Reads the hook payload on stdin, extracts the edited file path, and formats it
if it is a .py file under services/.

Formatting only -- deliberately NOT `ruff check --fix`. Autofix deletes an
import the instant it is momentarily unused, which mid-edit means before its
first use has been written. That has cost real time here; lint fixes belong at
commit time, where the whole change is visible at once.

Written as a script rather than a shell one-liner because `jq` is not installed
on this machine and the hook shell differs between platforms. Always exits 0 --
formatting is best-effort and must never block a tool call.
"""

import json
import re
import shutil
import subprocess
import sys

TARGET = re.compile(r"services[\\/].*\.py$")


def _get(obj: object, key: str) -> object:
    return obj.get(key) if isinstance(obj, dict) else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = _get(_get(payload, "tool_response"), "filePath") or _get(
        _get(payload, "tool_input"), "file_path"
    )
    if not isinstance(path, str) or not TARGET.search(path):
        return 0

    ruff = shutil.which("ruff")
    if not ruff:
        return 0

    try:
        subprocess.run([ruff, "format", path], capture_output=True, timeout=30)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

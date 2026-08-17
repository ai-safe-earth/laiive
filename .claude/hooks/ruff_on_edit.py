"""PostToolUse hook: run ruff on edited Python files under services/.

Reads the hook payload on stdin, extracts the edited file path, and runs
`ruff check --fix` then `ruff format` on it if it is a .py file under services/.

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

    for args in (["check", "--fix", path], ["format", path]):
        try:
            subprocess.run([ruff, *args], capture_output=True, timeout=30)
        except Exception:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

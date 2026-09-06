# ai-safety-audit bootstrap: run `aisg audit` through a pinned install chain (PowerShell mirror of audit.sh).
# aisg-audit: ignore-file
$AISG_VERSION = "0.1.0"   # pinned; test_skill_package.py asserts this equals pyproject.toml [project].version
if (Get-Command aisg -ErrorAction SilentlyContinue) {
    & aisg audit @args
} elseif (Get-Command uvx -ErrorAction SilentlyContinue) {
    & uvx --from "aisguard==$AISG_VERSION" aisg audit @args
} elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    & pipx run --spec "aisguard==$AISG_VERSION" aisg audit @args
} else {
    [Console]::Error.WriteLine("aisg not found. Install one of:")
    [Console]::Error.WriteLine("  uv tool install 'aisguard==$AISG_VERSION'   (uv works without a pre-installed Python)")
    if ((Get-Command python3 -ErrorAction SilentlyContinue) -or (Get-Command python -ErrorAction SilentlyContinue)) {
        [Console]::Error.WriteLine("  pipx install 'aisguard==$AISG_VERSION'")
        [Console]::Error.WriteLine("  pip install 'aisguard==$AISG_VERSION'")
    } else {
        [Console]::Error.WriteLine("  (no python3/python on PATH: install uv first, e.g. https://docs.astral.sh/uv/getting-started/installation/)")
    }
    exit 2
}
exit $LASTEXITCODE

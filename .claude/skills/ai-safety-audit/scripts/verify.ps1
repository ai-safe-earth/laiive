# ai-safety-audit verify step (phase 5), PowerShell mirror of verify.sh.
# aisg-audit: ignore-file
# Detects the project's test command and prints it, then resolves `aisg` through the same
# pinned bootstrap chain as audit.ps1 for `aisg measure` and, when AISG_PROBE_URL is set,
# `aisg probe`. Nothing runs unless AISG_VERIFY_RUN=1: tests, measure and probe may call
# model providers. This script never adds --i-have-authorization.
$AISG_VERSION = "0.1.0"   # pinned; test_skill_package.py asserts this equals pyproject.toml [project].version
$run = if ($env:AISG_VERIFY_RUN) { $env:AISG_VERIFY_RUN } else { "0" }
$status = 0

# --- 1. Test command, from manifests (first match wins) ---------------------
$testCmd = $null
if ((Test-Path pyproject.toml) -or (Test-Path pytest.ini) -or (Test-Path setup.cfg)) {
    $testCmd = @("pytest")
} elseif ((Test-Path package.json) -and (Select-String -Path package.json -Pattern '"test"\s*:' -Quiet)) {
    $testCmd = @("npm", "test")
} elseif (Test-Path go.mod) {
    $testCmd = @("go", "test", "./...")
} elseif (Test-Path Cargo.toml) {
    $testCmd = @("cargo", "test")
}

if ($null -eq $testCmd) {
    Write-Output "tests: no test command detected (looked for pyproject.toml/pytest.ini/setup.cfg, package.json test script, go.mod, Cargo.toml)"
} else {
    Write-Output "tests: $($testCmd -join ' ')"
    if ($run -eq "1") {
        $testArgs = @($testCmd | Select-Object -Skip 1)
        & $testCmd[0] @testArgs
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine("tests: FAILED ($($testCmd -join ' ') exited non-zero)")
            $status = 1
        }
    } else {
        Write-Output "tests: not run (set AISG_VERIFY_RUN=1 to run)"
    }
}

# --- 2. aisg through the same bootstrap chain as audit.ps1 ------------------
function Test-Aisg {
    return [bool]((Get-Command aisg -ErrorAction SilentlyContinue) -or
                  (Get-Command uvx -ErrorAction SilentlyContinue) -or
                  (Get-Command pipx -ErrorAction SilentlyContinue))
}

function Invoke-Aisg {
    if (Get-Command aisg -ErrorAction SilentlyContinue) {
        & aisg @args
    } elseif (Get-Command uvx -ErrorAction SilentlyContinue) {
        & uvx --from "aisguard==$AISG_VERSION" aisg @args
    } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        & pipx run --spec "aisguard==$AISG_VERSION" aisg @args
    } else {
        $global:LASTEXITCODE = 127
    }
}

# Summary counts from a probe report. Only `passed` means passed; the other five
# are never folded into it.
function Write-ProbeSummary($path) {
    $text = Get-Content -Raw $path
    foreach ($key in @("sent", "passed", "failed", "errors", "skipped", "inconclusive")) {
        $m = [regex]::Match($text, "`"$key`"\s*:\s*([0-9]+)")
        $value = if ($m.Success) { $m.Groups[1].Value } else { "?" }
        Write-Output "probe ${key}: $value"
    }
    Write-Output "probe: only 'passed' means passed; failed, errors, skipped and inconclusive are separate"
}

if (-not (Test-Aisg)) {
    [Console]::Error.WriteLine("measure skipped: aisg not importable in target")
    if ($env:AISG_PROBE_URL) {
        [Console]::Error.WriteLine("probe skipped: aisg not importable in target")
    }
    exit $status
}

# --- 3. aisg measure, when a pipeline config exists -------------------------
$pipelineCfg = $null
$candidates = @("guardrails.yaml", "aisg.yaml")
if (Test-Path config) {
    $candidates += Get-ChildItem -Path config -File -Include *.yaml, *.yml -Recurse:$false -Name |
        ForEach-Object { "config/$_" }
}
foreach ($candidate in $candidates) {
    if (-not (Test-Path $candidate -PathType Leaf)) { continue }
    if (Select-String -Path $candidate -Pattern '^(pipeline|guards):' -Quiet) {
        $pipelineCfg = $candidate
        break
    }
}

if ($null -eq $pipelineCfg) {
    Write-Output "measure: no pipeline config found (looked for guardrails.yaml, aisg.yaml, config/*.yaml with a top-level pipeline: or guards: key)"
} else {
    Write-Output "measure: aisg measure --config $pipelineCfg -o measure-report.json"
    if ($run -eq "1") {
        Invoke-Aisg measure --config $pipelineCfg -o measure-report.json
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine("measure: FAILED (aisg measure exited non-zero)")
            $status = 1
        }
    } else {
        Write-Output "measure: not run (set AISG_VERIFY_RUN=1 to run)"
    }
}

# --- 4. aisg probe, only when AISG_PROBE_URL is set --------------------------
if ($env:AISG_PROBE_URL) {
    Write-Output "probe: aisg probe $($env:AISG_PROBE_URL) -o probe-report.json"
    Write-Output "probe: a non-loopback target needs --i-have-authorization; this script never adds it"
    if ($run -eq "1") {
        Invoke-Aisg probe $env:AISG_PROBE_URL -o probe-report.json
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine("probe: exited non-zero (1 = a case got through, 2 = errors/skipped/inconclusive present)")
            $status = 1
        }
        if (Test-Path probe-report.json) {
            Write-ProbeSummary probe-report.json
        }
    } else {
        Write-Output "probe: not run (set AISG_VERIFY_RUN=1 to run)"
    }
}

exit $status

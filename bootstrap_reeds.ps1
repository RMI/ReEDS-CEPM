<#
Bootstrap script for ReEDS run setup.

What this script does:
1) Verifies GAMS is on PATH, checks GAMS license status, and prints a detected version string.
2) Verifies Julia is on PATH and exactly version 1.12.1.
3) Sets ReEDS-required CONDA-style environment variables in the current PowerShell session.
4) Checks the project Python pin and runs `uv python pin 3.11` when not pinned to 3.11.
5) Runs `uv sync --extra dev` to ensure the Python environment matches project dependencies (unless bypass mode is enabled).
6) Runs `julia --project=. instantiate.jl` to ensure Julia dependencies are installed (unless bypass mode is enabled).
7) Starts runbatch.py and forwards any arguments passed to this script.


Bypass option:
    -y, -Bypass, or --bypass
    Skips Step 5 (`uv sync --extra dev`) and Step 6 (`julia --project=. instantiate.jl`).
    Other checks and setup steps still run, and remaining args are forwarded to runbatch.py.

Usage examples:
    .\bootstrap_reeds.ps1
    .\bootstrap_reeds.ps1 -b v20260625_test -c test
    .\bootstrap_reeds.ps1 -y -b v20260625_test -c test
    .\bootstrap_reeds.ps1 --bypass -b v20260625_test -c test
#>

# Accept and forward all remaining command-line args to runbatch.py.
param(
    [Alias('y')]
    [switch]$Bypass,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunbatchArgs
)

# Copy forwarded args and handle explicit --bypass token if provided.
$ForwardArgs = @($RunbatchArgs)
if ($ForwardArgs -contains '--bypass') {
    $Bypass = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--bypass' })
}

# Fail immediately on PowerShell errors so setup issues do not get masked.
$ErrorActionPreference = 'Stop'

# Run a named step, print progress, and throw on non-zero process exit code.
function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    Write-Host "[run] $Description"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Description"
    }
}

# Script is located at repository root, so use script directory as repo root.
$repoRoot = (Resolve-Path $PSScriptRoot).Path

Write-Host "Using repository root: $repoRoot"

# Step 1: Verify GAMS is available on PATH, check license status, and print version.
$gamsCmd = Get-Command gams -ErrorAction SilentlyContinue
if (-not $gamsCmd) {
    throw 'GAMS executable was not found on PATH. Install GAMS and add it to PATH before running ReEDS.'
}

$gamsVersionOutput = (& gams 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "GAMS command failed while checking version. Output:`n$gamsVersionOutput"
}

$gamsVersion = $null
if ($gamsVersionOutput -match '(?im)\bGAMS\b[^0-9]*([0-9]+(?:\.[0-9]+)+)') {
    $gamsVersion = $matches[1]
}

# Check for the standard GAMS success message that confirms installed license validity.
$gamsLicenseValid = ($gamsVersionOutput -match '(?im)The installed license is valid\.')
if (-not $gamsLicenseValid) {
    Write-Warning "GAMS is on PATH, but license validity was not confirmed. Output:`n$gamsVersionOutput"
}

if ($gamsVersion) {
    if ($gamsLicenseValid) {
        Write-Host "[ok] GAMS detected on PATH, license valid. Version: $gamsVersion"
    } else {
        Write-Warning "GAMS detected on PATH. License validity could not be confirmed. Version: $gamsVersion"
    }
} else {
    $gamsVersionFirstLine = ($gamsVersionOutput -split "`r?`n")[0]
    if ($gamsLicenseValid) {
        Write-Warning "GAMS detected on PATH with valid license, but version could not be parsed. Output: $gamsVersionFirstLine"
    } else {
        Write-Warning "GAMS detected on PATH, but license validity and version parsing were not confirmed. Output: $gamsVersionFirstLine"
    }
}

# Step 2: Verify Julia is available on PATH and exactly version 1.12.1.
$expectedJuliaVersion = '1.12.1'
$juliaCmd = Get-Command julia -ErrorAction SilentlyContinue
if (-not $juliaCmd) {
    throw 'Julia executable was not found on PATH. Install Julia 1.12.1 and add it to PATH before running ReEDS.'
}

$juliaVersionOutput = (& julia --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Julia command failed while checking version. Output:`n$juliaVersionOutput"
}

if (-not ($juliaVersionOutput -match '(?i)julia version\s+([0-9]+(?:\.[0-9]+){2})')) {
    throw "Unable to parse Julia version from output: $juliaVersionOutput"
}

$juliaVersion = $matches[1]
if ($juliaVersion -ne $expectedJuliaVersion) {
    throw "Julia version $juliaVersion detected, but ReEDS expects $expectedJuliaVersion."
}

Write-Host "[ok] Julia detected on PATH. Version: $juliaVersion"

# Step 3: Set expected ReEDS env vars in the current shell session.
# These values persist for this shell after script completion.

# Use the expected top-level virtual environment path.
# On a fresh clone this folder may not exist yet; `uv sync` below will create it.
$venvPath = Join-Path $repoRoot '.venv'
$env:CONDA_DEFAULT_ENV = 'reeds2'
$env:CONDA_PREFIX = $venvPath
Write-Host "[ok] Set CONDA_DEFAULT_ENV=$($env:CONDA_DEFAULT_ENV)"
Write-Host "[ok] Set CONDA_PREFIX=$($env:CONDA_PREFIX)"

# Step 4: Check whether this repo is pinned to Python 3.11 via .python-version.
$pythonVersionFile = Join-Path $repoRoot '.python-version'
$hasPinned311 = $false
$pinnedPython = $null
if (Test-Path $pythonVersionFile) {
    $pinnedPython = (Get-Content $pythonVersionFile -TotalCount 1).Trim()
    if ($pinnedPython -match '^3\.11(\.|$)') {
        $hasPinned311 = $true
    }
}

# If not already pinned to 3.11, pin it now.
if (-not $hasPinned311) {
    if ([string]::IsNullOrWhiteSpace($pinnedPython)) {
        Write-Warning 'Python was not already pinned to 3.11 (no .python-version pin found). Pinning now.'
    } else {
        Write-Warning "Python was pinned to '$pinnedPython' instead of 3.11. Re-pinning now."
    }
    Invoke-Step -Description 'uv python pin 3.11' -Action {
        Set-Location $repoRoot
        uv python pin 3.11
    }
} else {
    Write-Host '[ok] Python is already pinned to 3.11 in .python-version.'
}

# Step 5: Run uv sync unless bypass mode is enabled.
if ($Bypass) {
    Write-Warning 'Bypass mode enabled: skipping uv sync --extra dev and julia --project=. instantiate.jl.'
} else {
    # This is safe and ensures Python deps match lock/project files.
    Invoke-Step -Description 'uv sync --extra dev' -Action {
        # Run from repo root so uv uses the intended project files.
        Set-Location $repoRoot
        uv sync --extra dev
    }

    # Step 6: Run Julia instantiate every time.
    # This is safe and ensures deps match project files.
    Invoke-Step -Description 'julia --project=. instantiate.jl' -Action {
        Set-Location $repoRoot
        julia --project=. instantiate.jl
    }
}

# Step 7: Start ReEDS with any arguments passed to this bootstrap script.
Write-Host '[run] uv run python runbatch.py ...'
Set-Location $repoRoot
uv run python runbatch.py @ForwardArgs
if ($LASTEXITCODE -ne 0) {
    throw 'runbatch.py failed.'
}

Write-Host 'Bootstrap complete.'

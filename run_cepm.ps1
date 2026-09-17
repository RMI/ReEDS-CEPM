<#
run_cepm.ps1 -- set up the ReEDS environment and launch a ReEDS run (RMI/CEPM).

What this script does:
1) Verifies GAMS is on PATH, checks GAMS license status, and prints a detected version string.
2) Verifies Julia is on PATH and exactly version 1.12.1.
3) Sets ReEDS-required CONDA-style environment variables in the current PowerShell session.
4) Checks the project Python pin and runs `uv python pin 3.11` when not pinned to 3.11.
5) Runs `uv sync --extra dev` to ensure the Python environment matches project dependencies (unless bypass mode is enabled).
6) Instantiates Julia dependencies only when needed: a fast offline instantiate checks/heals the environment, falling back to the full `julia --project=. instantiate.jl` (which updates the registry) only if that can't satisfy the project (unless bypass mode is enabled).
7) Checks environment.yml against pyproject.toml and warns (non-fatal) on dependency drift beyond the known-accepted allowlist in CEPM/scripts/check_env_sync.py.
8) Starts runreeds.py and forwards any arguments passed to this script.
   Skipped entirely when -o/--compare-only is given (see below) -- along
   with Steps 1-7, since those only matter for an actual ReEDS run.
   With -m/--multistep <stem> this becomes a two-phase sequence instead
   (baseline -> harvest a capacity ceiling -> limitre + optimized); see
   -m below and CEPM/guidance/two-step-re-limited-runs.md.
9) When -x/--compare-cases is given and runreeds.py succeeds, OR when
   -o/--compare-only is given (regardless of -x), runs
   postprocessing/compare_cases.py against all completed cases in the batch
   (skipped automatically for -s/--single or -t/--dryrun runs when Step 8
   actually ran, since there's nothing meaningful to compare -- this check
   does not apply in -o/--compare-only mode, since Step 8 didn't run). No
   base case is specified, so compare_cases.py defaults to the first
   alphabetically-sorted completed case as the base -- not necessarily the
   leftmost case in the cases file. compare_cases.py's --startyear is set
   from the first 4 digits of the `yearset` switch for the first
   non-ignored case (left to right) in the cases file used for this batch,
   via CEPM/scripts/get_batch_info.py; if that can't be determined,
   compare_cases.py's own default (2020) is used instead.
10) Sends an ntfy.sh notification (topic: rmi-cepm-runs) before runreeds.py launches and once it returns. Best-effort: a failed or offline notification is ignored. Disabled with -q/--quiet; -u/--user adds a username to the message; the batch name and cases suffix (see below) are always included.
11) Saves the full console output of this script (Steps 1-10, including all
    forwarded native command output) as bootstraplog.txt in the run folder of
    the first non-ignored case (left to right) in the cases file used for
    this batch -- runs/<BatchName>_<first case>, via
    CEPM/scripts/get_batch_info.py (same script as Step 9). Runs even if an
    earlier step throws, so a failed bootstrap or run still leaves a log
    behind; best-effort throughout (a missing run folder, or any other
    logging failure, is only warned). Under -m/--multistep the destination is
    the <stem>_baseline run folder instead, since -s overrides `ignore` and
    the leftmost non-ignored case may not be one of the three that ran; the
    per-batch files -m generated are also deleted here, unconditionally.


BOOTSTRAP-ONLY OPTIONS (consumed here; everything else is forwarded to runreeds.py):
    -y, --bypass, --skip-setup
        Bypass mode: skip Step 5 (`uv sync --extra dev`) and Step 6 (Julia
        instantiation). Other checks/setup steps still run.
    -q, --quiet
        Disable the ntfy.sh notifications (both the pre-launch ping and Step 10).
    -u, --user <name>   (also --user=<name>)
        Include <name> as the username in the ntfy messages. When omitted, no
        username is shown.
    -x, --compare-cases
        After runreeds.py finishes successfully, run postprocessing/compare_cases.py
        against all completed cases in this batch (glob on runs/<BatchName>_*).
        Skipped automatically when -s/--single or -t/--dryrun is also given. Failures
        are non-fatal (warned, not thrown) since the ReEDS run itself already
        succeeded. Assumes BatchName is unique to this invocation (never reused
        across separate runreeds.py calls) -- if a batch name IS reused, folders left
        over from an earlier call under the same name will be picked up too, since
        this script only scopes by the runs/<BatchName>_* glob, not by run recency.
    -m, --multistep <stem>   (also --multistep=<stem>)
        Two-phase baseline-constrained run. Instead of one runreeds.py call,
        Step 8 becomes: run <stem>_baseline; harvest a capacity ceiling from its
        outputs with CEPM/scripts/make_tg_cap.py; generate a cases file pointing
        <stem>_limitre at that ceiling; then run <stem>_limitre and
        <stem>_optimized. All three share one batch name, so the existing -x
        comparison picks up all three with no extra flags.

        The cases file must define all three columns, with GSw_CEPM_TgCap=1 for
        _limitre and 0 for the other two; this is checked up front (in seconds)
        by CEPM/scripts/multistep_cases.py before phase A starts. Phase A must
        also produce outputs/outputs.h5 -- runreeds.py returns 0 even when a
        case's solve aborts, so the exit code alone is not trusted here.

        Cannot be combined with -o/--compare-only, or with your own -s/--single
        (each phase supplies its own). With -t/--dryrun, both phases' switches
        are validated and the generated cases file is written and cleaned up,
        but nothing runs and nothing is harvested.

        The generated cap CSVs and cases file are named after the batch and
        deleted in a finally, so an interrupted or failed run leaves the working
        tree clean. See CEPM/guidance/two-step-re-limited-runs.md.

        KEEP cleanup_level=0 IN THE CASES FILE. runreeds.py:959-967 prints an R2X
        warning and blocks on `input('Proceed? y/[n]: ')` (defaulting to "n", so
        it quits) whenever ANY case has cleanup_level >= 1 and --skip_checks was
        not passed. Two things make this bite here specifically: the check runs
        at launch, before anything starts; and because -m always uses -s, the
        ignored cases are NOT dropped from df_cases first (runreeds.py:899-905),
        so the check scans EVERY column in the cases file, including the ten or
        so this batch isn't running. One stray cleanup_level=2 anywhere in
        cases_cepm.csv therefore hangs a background/CI -m run that never shows
        the prompt. Keeping the whole column at 0 is the simple guard; -f/--skip_checks
        would also bypass it, at the cost of skipping every other pre-flight check.
    --harvest-args "<args>"   (also --harvest-args=<args>)
        Multistep only: extra arguments passed verbatim to make_tg_cap.py, e.g.
        --harvest-args "--scope both --headroom 0.95". The script's own defaults
        already encode the documented choices (system scope, headroom 1.00,
        2026-2032, the six-group list), so this is only for deviating from them.
    -o, --compare-only
        Skip Steps 1-8 entirely (the GAMS/Julia/uv/Julia-instantiate checks and
        runreeds.py itself) and go straight to running
        postprocessing/compare_cases.py against all completed cases already in
        runs/<BatchName>_* for the given -b/-c. Implies -x (compare_cases.py always
        runs; the -s/--single and -t/--dryrun skip-check does not apply, since no
        run occurred to check). Use this to re-run or fix up the comparison plots
        for a batch that already finished, without re-running ReEDS. Still prompts
        for/forwards -b/--BatchName and -c/--cases_suffix exactly as normal, since
        they're needed to locate the batch's run folders. Any other forwarded args
        (that would normally go to runreeds.py) are ignored in this mode.

INTERCEPTED-AND-FORWARDED OPTIONS:
    -b, --BatchName <name>   (also --BatchName=<name>)
        Same option runreeds.py defines for the batch prefix. This script reads
        it (prompting interactively if omitted, and expanding '0' to a
        timestamped name) using the same logic as runreeds.py's own prompt, so
        that the resolved batch name can be included in the ntfy messages. The
        resolved value is then forwarded to runreeds.py as -b, so runreeds.py is
        never left to prompt for it itself.
    -c, --cases_suffix <suffix>   (also --cases_suffix=<suffix>)
        Same option runreeds.py defines for the cases_suffix.csv file. Handled
        the same way as -b/--BatchName above: prompted for here if omitted
        (using runreeds.py's own prompt text; a blank value is valid and means
        cases.csv), included in the ntfy messages, and forwarded to runreeds.py
        as -c.

RESERVED OPTIONS (do NOT add a bootstrap-only flag that reuses these):
    All args other than the options above are forwarded verbatim to runreeds.py,
    so any short/long option runreeds.py defines is off-limits for this script to
    claim for itself. As of this writing runreeds.py uses:
        -b/--BatchName   -c/--cases_suffix  -s/--single      -r/--simult_runs
        -l/--forcelocal  -f/--skip_checks   -d/--debug       -n/--debugnode
        -p/--cases_per_node                 -t/--dryrun
    (plus -h/--help from argparse). The bootstrap-only options above (-y, -q, -u, -x, -o, -m)
    were chosen to avoid these; -b/--BatchName and -c/--cases_suffix are
    deliberately intercepted (see above) rather than avoided. If you add a new
    bootstrap-only switch, pick a letter outside that set (and re-check against
    runreeds.py, which may change).

Usage examples:
    .\run_cepm.ps1
    .\run_cepm.ps1 -b v20260625_test -c test
    .\run_cepm.ps1 -y -b v20260625_test -c test
    .\run_cepm.ps1 --bypass -b v20260625_test -c test
    .\run_cepm.ps1 -q -b v20260625_test -c test
    .\run_cepm.ps1 -u "Tyler Fitch" -b v20260625_test -c test
    .\run_cepm.ps1 -x -b v20260625_test -c test
    .\run_cepm.ps1 -o -b v20260625_test -c test
    .\run_cepm.ps1 -y -x -b v20260625_ms -c cepm -m WECC-SW
    .\run_cepm.ps1 -y -x -b v20260625_ms -c cepm -m WECC-SW --harvest-args "--scope both"
    .\run_cepm.ps1 -y -q -b v20260625_ms -c cepm -m WECC-SW -t
#>

# Initializing functions and variables for this script.

# Accept and forward all remaining command-line args to runreeds.py.
param(
    [switch]$y, # Bypass mode for skipping uv sync and Julia instantiate. We use y to prevent collision with runreeds options.
    [switch]$q, # Quiet: disable the ntfy.sh notifications. -q is free of runreeds options.
    [string]$u = '', # Username string to include in ntfy messages. -u is free of runreeds options.
    [switch]$x, # Compare-cases mode: run compare_cases.py on the batch after runreeds.py succeeds. -x is free of runreeds options.
    [switch]$o, # Compare-only mode: skip runreeds.py (and its preflight checks) entirely and just run compare_cases.py against the existing batch. -o is free of runreeds options.
    [string]$m = '', # Multistep mode: case stem for a two-phase baseline -> limitre+optimized run. -m is free of runreeds options.
    [string]$b = '', # BatchName: same short flag as runreeds.py's -b/--BatchName. Intercepted here so
                      # we can resolve it (prompting if needed) and echo it in ntfy messages, then
                      # forwarded back to runreeds.py explicitly (see below).
    [string]$c = '', # cases_suffix: same short flag as runreeds.py's -c/--cases_suffix. Intercepted
                      # the same way as -b above.

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunbatchArgs
)

# Copy forwarded args and pull out our long-form tokens. PowerShell binds the short
# switches (-y/-q/-u) natively; the double-dash long forms are not real PowerShell
# parameters, so we strip them from the forwarded args by hand. Everything left is
# forwarded verbatim to runreeds.py.
$ForwardArgs = @($RunbatchArgs)
if ($ForwardArgs -contains '--bypass') {
    $y = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--bypass' })
}
if ($ForwardArgs -contains '--skip-setup') {
    $y = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--skip-setup' })
}
if ($ForwardArgs -contains '--quiet') {
    $q = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--quiet' })
}
if ($ForwardArgs -contains '--compare-cases') {
    $x = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--compare-cases' })
}
if ($ForwardArgs -contains '--compare-only') {
    $o = $true
    $ForwardArgs = @($ForwardArgs | Where-Object { $_ -ne '--compare-only' })
}
# --user NAME and --user=NAME take a value; pull them (and the value) out by hand.
# --BatchName NAME/--BatchName=NAME and --cases_suffix NAME/--cases_suffix=NAME (runreeds.py's
# long forms of -b and -c) are pulled out the same way, so both are recognized regardless of
# which form is used.
$remainingArgs = @()
$HarvestArgsRaw = ''
for ($i = 0; $i -lt $ForwardArgs.Count; $i++) {
    $arg = $ForwardArgs[$i]
    if ($arg -eq '--user') {
        if ($i + 1 -lt $ForwardArgs.Count) { $u = $ForwardArgs[$i + 1]; $i++ }
        continue
    }
    if ($arg -like '--user=*') {
        $u = $arg.Substring('--user='.Length)
        continue
    }
    if ($arg -eq '--BatchName') {
        if ($i + 1 -lt $ForwardArgs.Count) { $b = $ForwardArgs[$i + 1]; $i++ }
        continue
    }
    if ($arg -like '--BatchName=*') {
        $b = $arg.Substring('--BatchName='.Length)
        continue
    }
    if ($arg -eq '--cases_suffix') {
        if ($i + 1 -lt $ForwardArgs.Count) { $c = $ForwardArgs[$i + 1]; $i++ }
        continue
    }
    if ($arg -like '--cases_suffix=*') {
        $c = $arg.Substring('--cases_suffix='.Length)
        continue
    }
    if ($arg -eq '--multistep') {
        if ($i + 1 -lt $ForwardArgs.Count) { $m = $ForwardArgs[$i + 1]; $i++ }
        continue
    }
    if ($arg -like '--multistep=*') {
        $m = $arg.Substring('--multistep='.Length)
        continue
    }
    if ($arg -eq '--harvest-args') {
        if ($i + 1 -lt $ForwardArgs.Count) { $HarvestArgsRaw = $ForwardArgs[$i + 1]; $i++ }
        continue
    }
    if ($arg -like '--harvest-args=*') {
        $HarvestArgsRaw = $arg.Substring('--harvest-args='.Length)
        continue
    }
    $remainingArgs += $arg
}
$ForwardArgs = @($remainingArgs)

# Everything the caller passed that is meant for runreeds.py, before -b/-c are
# prepended below. Multistep mode (-m) needs this separately, because it makes two
# runreeds.py calls with a DIFFERENT -c each time (phase B uses a generated cases
# file), so it cannot reuse the single $ForwardArgs the normal path builds.
$ExtraArgs = @($ForwardArgs)

# Extra arguments for CEPM/scripts/make_tg_cap.py in multistep mode, e.g.
# --harvest-args '--scope both --headroom 0.95'. Split on whitespace; the script's
# own defaults already encode the documented decisions (system scope, headroom 1.00,
# 2026-2032, the six-group list), so this is only for deviating from them.
$MultistepHarvestArgs = @()
if (-not [string]::IsNullOrWhiteSpace($HarvestArgsRaw)) {
    $MultistepHarvestArgs = @($HarvestArgsRaw -split '\s+' | Where-Object { $_ -ne '' })
}

# Reject flag combinations -m cannot honor, here rather than inside Step 8m. Two
# reasons: these are knowable from the arguments alone, so failing before the GAMS/
# Julia/uv preflight (and before any prompt) is friendlier; and -o skips Step 8
# entirely, so a guard placed inside it would never run in the one case that needs
# it most -- `-m` with `-o` would silently ignore the -m.
if (-not [string]::IsNullOrWhiteSpace($m)) {
    # -o skips runreeds.py altogether; -m is nothing but two runreeds.py calls.
    if ($o) {
        throw '-m/--multistep and -o/--compare-only are mutually exclusive.'
    }
    # A caller-supplied -s/--single would fight with the -s each phase supplies for
    # itself, and silently run the wrong cases. Refuse rather than guess.
    if (($ExtraArgs -contains '-s') -or ($ExtraArgs -contains '--single') -or
        [bool]($ExtraArgs | Where-Object { $_ -like '--single=*' })) {
        throw '-m/--multistep supplies its own -s/--single for each phase; remove the -s you passed.'
    }
}

# Optional ntfy username fragment: empty unless -u/--user was given.
$ntfyUser = if ([string]::IsNullOrWhiteSpace($u)) { '' } else { " by $u" }

# Resolve the batch name using the same logic as runreeds.py's setupEnvironment():
# prompt interactively if it was not supplied, expand '0' to a timestamped name, and
# replace '.' with '_'. Resolving it here (rather than letting runreeds.py prompt for
# it) lets the ntfy messages include it, and avoids leaving runreeds.py to prompt
# again since we forward the resolved value explicitly via -b below.
if ([string]::IsNullOrEmpty($b)) {
    Write-Host ' '
    Write-Host '------------- '
    Write-Host ' '
    Write-Host '-- Specify the batch prefix --'
    Write-Host ' '
    Write-Host "The batch prefix is attached to the beginning of all cases' outputs files"
    Write-Host 'Note - it must start with a letter and not a number or symbol'
    Write-Host ' '
    Write-Host 'A value of 0 will assign the date and time as the batch name (e.g. v20190520_072310)'
    Write-Host ' '
    $b = Read-Host -Prompt 'Batch Prefix'
}
if ($b -eq '0') {
    $b = 'v' + (Get-Date -Format 'yyyyMMdd_HHmmss')
}
# Check for period in batch name and replace with underscore, matching runreeds.py.
$BatchName = $b.Replace('.', '_')

# Forward the resolved batch name to runreeds.py explicitly so it is never left to
# prompt for it itself.
$ForwardArgs = @('-b', $BatchName) + $ForwardArgs

# ntfy fragment naming the batch, included in every notification below.
$ntfyBatch = " for batch '$BatchName'"

# Resolve the cases suffix using the same logic as runreeds.py's setupEnvironment(): prompt
# interactively if it was not supplied. Unlike BatchName, a blank value is valid here (it means
# "use cases.csv" -- see runreeds.py's cases_filename derivation below), so no re-prompt loop.
if ([string]::IsNullOrEmpty($c)) {
    Write-Host ' '
    Write-Host 'Specify the suffix for the cases_suffix.csv file'
    Write-Host 'A blank input will default to the cases.csv file'
    Write-Host ' '
    $c = Read-Host -Prompt 'Case Suffix'
}
$CasesSuffix = $c

# Forward the resolved cases suffix to runreeds.py explicitly so it is never left to prompt
# for it itself.
$ForwardArgs = @('-c', $CasesSuffix) + $ForwardArgs

# ntfy fragment naming the cases file, included in every notification below. Mirrors
# runreeds.py's own cases_filename derivation ('' or 'default' -> cases.csv).
$casesFilename = if ($CasesSuffix -in @('', 'default')) { 'cases.csv' } else { "cases_$CasesSuffix.csv" }
$ntfyCases = " ($casesFilename)"

# Fail immediately on PowerShell (cmdlet) errors so setup issues do not get masked.
$ErrorActionPreference = 'Stop'

# Run a native command with stderr-as-error suppressed. Tools like uv and julia
# write normal progress to stderr; when that stderr is merged into the pipeline
# (e.g. a caller wraps this script with 2>&1, or a CI/host captures combined
# output), Windows PowerShell 5.1 turns each stderr line into a terminating
# NativeCommandError under $ErrorActionPreference='Stop' -- aborting the script
# even though the command actually succeeded (exit code 0). We relax the
# preference only around the native call; real failures are still detected by
# the caller via $LASTEXITCODE.
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Action
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

# Run a named step, print progress, and throw on non-zero process exit code.
function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    Write-Host "[run] $Description"
    Invoke-Native $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Description"
    }
}

# Script is located at repository root, so use script directory as repo root.
$repoRoot = (Resolve-Path $PSScriptRoot).Path

# Capture the full bootstrap+run console output (every Write-Host/Write-Warning line
# below, plus all native command output) to a staging file, then copy it into the
# first scenario's run folder as bootstraplog.txt (Step 11) once everything else has
# run. Staged under $env:TEMP because the target run folder doesn't exist yet when
# logging starts. The whole rest of the script runs inside the try below so the log
# is still saved (best-effort) even if a step throws.
$bootstrapLogPath = Join-Path $env:TEMP "reeds_bootstraplog_$([guid]::NewGuid().ToString('N')).txt"
try {
    Start-Transcript -Path $bootstrapLogPath -Force | Out-Null
} catch {
    Write-Warning "Could not start bootstrap log transcript (bootstraplog.txt will not be saved): $_"
}

try {

Write-Host "Using repository root: $repoRoot"

if ($o) {
    Write-Host "[note] Compare-only mode (-o/--compare-only): skipping Steps 1-8 (GAMS/Julia checks, uv sync, Julia instantiate, and runreeds.py) for batch '$BatchName'."
} else {

# Step 1: Verify GAMS is available on PATH, check license status, and print version.
$gamsCmd = Get-Command gams -ErrorAction SilentlyContinue
if (-not $gamsCmd) {
    throw 'GAMS executable was not found on PATH. Install GAMS and add it to PATH before running ReEDS.'
}

$gamsVersionOutput = (Invoke-Native { & gams 2>&1 | Out-String }).Trim()
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

$juliaVersionOutput = (Invoke-Native { & julia --version 2>&1 | Out-String }).Trim()
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
if ($y) {
    Write-Warning 'Bypass mode enabled: skipping uv sync --extra dev and julia --project=. instantiate.jl.'
} else {
    # This is safe and ensures Python deps match lock/project files.
    Invoke-Step -Description 'uv sync --extra dev' -Action {
        # Run from repo root so uv uses the intended project files.
        Set-Location $repoRoot
        uv sync --extra dev
    }

    # Step 6: Instantiate Julia deps only when needed. A fast, offline instantiate
    # (no registry update) both checks and cheaply self-heals the environment. If
    # it can't satisfy the project from the local registry cache (e.g. the Manifest
    # changed to a version not cached, or a fresh Julia depot), fall back to the
    # full instantiate.jl, which updates the registry. Every Project.toml dependency
    # (including Random123, PRAS, TimeZones) is covered by instantiate, so the fast
    # path loses nothing when the environment is already current.
    Write-Host '[run] checking whether Julia dependencies need instantiation'
    Set-Location $repoRoot
    Invoke-Native { julia --project=. -e "using Pkg; try; Pkg.instantiate(; update_registry=false); exit(0); catch; exit(1); end" }
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[ok] Julia dependencies already instantiated (skipping full instantiate.jl).'
    } else {
        Write-Warning 'Julia dependencies changed or missing; running full instantiate.jl (updates registry).'
        Invoke-Step -Description 'julia --project=. instantiate.jl' -Action {
            Set-Location $repoRoot
            julia --project=. instantiate.jl
        }
    }
}

# Step 7: Warn (non-fatal) if environment.yml and pyproject.toml have drifted
# beyond the known-accepted exceptions. This always runs -- it only reads two
# text files -- so it is not gated by bypass mode. It must never abort the
# bootstrap, so a non-zero result becomes a warning rather than a throw.
Write-Host '[run] CEPM/scripts/check_env_sync.py (environment.yml vs pyproject.toml)'
Set-Location $repoRoot
Invoke-Native { uv run python CEPM/scripts/check_env_sync.py }
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'environment.yml and pyproject.toml have drifted (see output above). Update both files, or adjust the allowlist in CEPM/scripts/check_env_sync.py. Continuing.'
} else {
    Write-Host '[ok] environment.yml and pyproject.toml are aligned (within known exceptions).'
}

Write-Host 'Bootstrap complete. Starting ReEDS runreeds.py with forwarded arguments...'

if (-not $q) {
    try {
        Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
            -Body "ReEDS run batch started on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
    } catch {}
}

# Step 8: Start ReEDS with any arguments passed to this bootstrap script.
if ([string]::IsNullOrWhiteSpace($m)) {

    Write-Host '[run] uv run python runreeds.py ...'
    Set-Location $repoRoot
    Invoke-Native { uv run python runreeds.py @ForwardArgs }

    # Send a NTFY message on failure and exit if runreeds fails.
    if ($LASTEXITCODE -ne 0) {
        if (-not $q) {
            try {
                Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                    -Body "ReEDS run batch failed to finish on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
            } catch {}
        }
        throw 'runreeds.py failed.'
    }

} else {

    # ---------------------------------------------------------------------------
    # Step 8m: Multistep (-m/--multistep) -- two-phase baseline-constrained run.
    # See CEPM/guidance/two-step-re-limited-runs.md.
    #
    #   Phase A   <stem>_baseline                      (no load, no ceiling)
    #   Harvest   make_tg_cap.py reads phase A's outputs -> cap CSVs for this batch
    #   Generate  a cases file pointing <stem>_limitre at those CSVs
    #   Phase B   <stem>_limitre, <stem>_optimized     (load; capped / uncapped)
    #
    # Both phases share one batch name, so runs/<Batch>_* holds all three cases and
    # Step 9's existing comparison picks them all up with no changes.
    # ---------------------------------------------------------------------------
    $stem = $m.Trim()
    $caseBaseline  = "${stem}_baseline"
    $caseLimitre   = "${stem}_limitre"
    $caseOptimized = "${stem}_optimized"

    # runreeds.py's --dryrun quits right after switch validation, so no run folder,
    # no outputs.h5 and nothing to harvest. Validate both phases' switches and
    # exercise the generated-file lifecycle, but skip the parts that need a
    # completed run. This is what test T6 checks.
    $isMultistepDryRun = ($ExtraArgs -contains '-t') -or ($ExtraArgs -contains '--dryrun')

    Write-Host ''
    Write-Host "===== Multistep run for stem '$stem' (batch '$BatchName') ====="
    if ($isMultistepDryRun) {
        Write-Host '[note] --dryrun: switches will be validated for both phases; no run, no harvest.'
    }

    # --- Step 8m.1: refuse to start unless the cases file can support all three cases.
    # Cheap, and it fires in seconds rather than after phase A has burned an hour.
    Write-Host "[run] CEPM/scripts/multistep_cases.py --mode validate ($casesFilename, stem $stem)"
    Set-Location $repoRoot
    $multistepInfo = @(Invoke-Native {
        uv run python CEPM/scripts/multistep_cases.py --mode validate `
            --cases-filename $casesFilename --stem $stem
    })
    if ($LASTEXITCODE -ne 0) {
        if (-not $q) {
            try {
                Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                    -Body "ReEDS multistep batch could not start on $(hostname)$ntfyUser$ntfyBatch$ntfyCases (cases file validation failed) at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
            } catch {}
        }
        throw "Multistep validation failed for stem '$stem' in $casesFilename (see output above)."
    }
    # stdout line 1 is the baseline case name, line 2 (optional) its start year. Both
    # are used below instead of get_batch_info.py's leftmost-non-ignored-case rule,
    # which is wrong here: -s overrides `ignore`, so the leftmost non-ignored case may
    # not be one of the three that actually ran.
    if ($multistepInfo.Count -ge 2 -and $multistepInfo[1].Trim() -match '^\d{4}$') {
        $MultistepStartYear = $multistepInfo[1].Trim()
    } else {
        $MultistepStartYear = ''
    }

    # --- Step 8m.2: Phase A -- the baseline, which the ceiling is harvested from.
    Write-Host ''
    Write-Host "[run] PHASE A: $caseBaseline"
    if (-not $q) {
        try {
            Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                -Body "ReEDS multistep PHASE A ($caseBaseline) started on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
        } catch {}
    }
    $phaseAArgs = @('-b', $BatchName, '-c', $CasesSuffix, '-s', $caseBaseline) + $ExtraArgs
    Set-Location $repoRoot
    Invoke-Native { uv run python runreeds.py @phaseAArgs }
    $phaseAExit = $LASTEXITCODE

    # runreeds.py returns 0 even when a case's solve aborted (confirmed during test
    # T0: an infeasible final year left no outputs.h5, yet the batch reported
    # success). So the exit code is necessary but NOT sufficient -- the real check is
    # that phase A produced the outputs the harvest reads. A ceiling harvested from a
    # partial run is worse than no run at all.
    $baselineRunDir = Join-Path $repoRoot "runs\${BatchName}_${caseBaseline}"
    $baselineOutputsH5 = Join-Path $baselineRunDir 'outputs\outputs.h5'
    if ($phaseAExit -ne 0) {
        if (-not $q) {
            try {
                Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                    -Body "ReEDS multistep PHASE A ($caseBaseline) FAILED on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
            } catch {}
        }
        throw "Phase A ($caseBaseline) failed: runreeds.py returned $phaseAExit."
    }
    if (-not $isMultistepDryRun) {
        if (-not (Test-Path $baselineOutputsH5)) {
            if (-not $q) {
                try {
                    Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                        -Body "ReEDS multistep PHASE A ($caseBaseline) produced no outputs.h5 on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
                } catch {}
            }
            throw ("Phase A ($caseBaseline) reported success but produced no outputs.h5 at " +
                   "$baselineOutputsH5. runreeds.py exits 0 even when a solve aborts, so this " +
                   "is the check that matters. Not harvesting a ceiling from a partial run.")
        }
        Write-Host "[ok] PHASE A complete; found $baselineOutputsH5"
    }

    # --- Step 8m.3: harvest the ceiling from phase A.
    # Written to inputs/growth_constraints/cepm_tg_cap_{sys,reg}_<BatchName>.csv, and
    # removed again in the finally block at the bottom of this script.
    $MultistepCapToken = $BatchName
    $capSysPath = Join-Path $repoRoot "inputs\growth_constraints\cepm_tg_cap_sys_${MultistepCapToken}.csv"
    $capRegPath = Join-Path $repoRoot "inputs\growth_constraints\cepm_tg_cap_reg_${MultistepCapToken}.csv"
    if ($isMultistepDryRun) {
        Write-Host "[note] --dryrun: skipping the harvest (no phase A outputs to read)."
    } else {
        Write-Host ''
        Write-Host "[run] CEPM/scripts/make_tg_cap.py (harvesting ceiling from $caseBaseline)"
        Set-Location $repoRoot
        Invoke-Native {
            uv run python CEPM/scripts/make_tg_cap.py `
                --baseline-case "runs/${BatchName}_${caseBaseline}" `
                --token $MultistepCapToken @MultistepHarvestArgs
        }
        if ($LASTEXITCODE -ne 0) {
            throw "make_tg_cap.py failed while harvesting the ceiling from $caseBaseline."
        }
        if (-not (Test-Path $capSysPath) -or -not (Test-Path $capRegPath)) {
            throw ("make_tg_cap.py reported success but did not write both cap files " +
                   "($capSysPath, $capRegPath). Phase B would run silently uncapped.")
        }
        Write-Host "[ok] Ceiling harvested to cepm_tg_cap_{sys,reg}_${MultistepCapToken}.csv"
    }

    # --- Step 8m.4: generate the per-batch cases file pointing _limitre at that ceiling.
    # A generated file rather than a fixed token, so two batches can run phase B
    # concurrently from one clone without clobbering each other (guidance doc 5.2b).
    $MultistepCasesSuffix = if ([string]::IsNullOrEmpty($CasesSuffix)) {
        "_${BatchName}"
    } else {
        "${CasesSuffix}__${BatchName}"
    }
    $MultistepCasesPath = Join-Path $repoRoot "cases_${MultistepCasesSuffix}.csv"
    Write-Host ''
    Write-Host "[run] CEPM/scripts/multistep_cases.py --mode generate -> cases_${MultistepCasesSuffix}.csv"
    Set-Location $repoRoot
    Invoke-Native {
        uv run python CEPM/scripts/multistep_cases.py --mode generate `
            --cases-filename $casesFilename --stem $stem `
            --token $MultistepCapToken --out "cases_${MultistepCasesSuffix}.csv"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Could not generate the phase B cases file (cases_${MultistepCasesSuffix}.csv)."
    }

    # --- Step 8m.5: Phase B -- both load cases, capped and uncapped.
    Write-Host ''
    Write-Host "[run] PHASE B: $caseLimitre, $caseOptimized"
    if (-not $q) {
        try {
            Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                -Body "ReEDS multistep PHASE B ($caseLimitre, $caseOptimized) started on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
        } catch {}
    }
    # Phase B runs TWO cases, and runreeds.py prompts interactively for the worker
    # count whenever len(caseList) > 1 and no --simult_runs was given -- which would
    # hang a background or CI invocation forever. Phase A never hits this (one case
    # short-circuits to WORKERS=1). So supply it explicitly, unless the caller already
    # did. Note this is passed as an element of an array we build ourselves, which is
    # why it works here: the known wrapper bug with -r/--simult_runs is in PowerShell's
    # binding of *caller-supplied* args, not in what we hand to runreeds.py directly.
    $phaseBWorkerArgs = @()
    $callerSetWorkers = ($ExtraArgs -contains '-r') -or ($ExtraArgs -contains '--simult_runs') -or
        [bool]($ExtraArgs | Where-Object { $_ -like '--simult_runs=*' })
    if (-not $callerSetWorkers) {
        $phaseBWorkerArgs = @('--simult_runs', '2')
        Write-Host '[note] Phase B: passing --simult_runs 2 (both cases run concurrently). Forward your own --simult_runs 1 to run them one at a time.'
    }
    $phaseBArgs = @('-b', $BatchName, '-c', $MultistepCasesSuffix,
                    '-s', "$caseLimitre,$caseOptimized") + $phaseBWorkerArgs + $ExtraArgs
    Set-Location $repoRoot
    Invoke-Native { uv run python runreeds.py @phaseBArgs }
    if ($LASTEXITCODE -ne 0) {
        if (-not $q) {
            try {
                Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                    -Body "ReEDS multistep PHASE B FAILED on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
            } catch {}
        }
        throw "Phase B ($caseLimitre, $caseOptimized) failed: runreeds.py returned $LASTEXITCODE."
    }

    # Same caveat as phase A: exit code 0 does not mean both cases finished. Warn
    # rather than throw, since by here the runs are done and Step 9's comparison is
    # still worth attempting on whatever completed.
    if (-not $isMultistepDryRun) {
        foreach ($caseName in @($caseLimitre, $caseOptimized)) {
            $h5 = Join-Path $repoRoot "runs\${BatchName}_${caseName}\outputs\outputs.h5"
            if (-not (Test-Path $h5)) {
                Write-Warning "Phase B case '$caseName' produced no outputs.h5 ($h5). It did not finish."
            }
        }
    }
    Write-Host "[ok] PHASE B complete."
}

} # end of "if ($o) { ... } else { ... }" (Steps 1-8, skipped in compare-only mode)

# Step 9: When -x/--compare-cases was given and runreeds.py succeeded, OR when
# -o/--compare-only was given (regardless of -x, and regardless of Step 8 --
# since it didn't run), run compare_cases.py against all completed cases in
# this batch. Skipped when -s/--single or -t/--dryrun was forwarded to
# runreeds.py (only relevant when Step 8 actually ran, i.e. not in
# -o/--compare-only mode), or when a quick folder count shows the batch only
# produced zero/one completed case (e.g. a cases file with just one
# non-ignored case, or a batch that hasn't actually run yet) -- in either case
# there's nothing to compare, so we note it and skip calling compare_cases.py
# rather than let it fail with a generic error. The folder count is a cheap
# local directory listing, not a subprocess call. Once we do call it, a
# single prefix argument (runs/<BatchName>_) is enough -- compare_cases.py
# globs it itself and filters to cases that actually finished (see
# reeds/report_utils.py's parse_caselist), so we don't need to enumerate or
# verify individual run folders ourselves. No base case (-b) is passed, so
# compare_cases.py defaults to the first alphabetically-sorted completed case
# -- not necessarily the leftmost case in the cases file. Non-fatal in normal
# mode (the ReEDS run itself already succeeded, so a comparison failure is
# only a warning); still non-fatal in -o/--compare-only mode since there is no
# run to protect the exit code of, but a failure there is the whole point of
# the invocation, so it's worth a clear warning either way.
if ($x -or $o) {
    # In multistep mode the -s flags are ours, one per phase, and three cases really
    # did run -- so the usual "-s means only one case, nothing to compare" shortcut
    # must not fire. A forwarded -t/--dryrun still skips, since nothing ran.
    $isMultistep = -not [string]::IsNullOrWhiteSpace($m)
    $isSingleRun = (-not $o) -and (-not $isMultistep) -and `
        (($ForwardArgs -contains '-s') -or ($ForwardArgs -contains '--single') -or `
        [bool]($ForwardArgs | Where-Object { $_ -like '--single=*' }))
    $isDryRun = (-not $o) -and (($ForwardArgs -contains '-t') -or ($ForwardArgs -contains '--dryrun'))
    if ($isSingleRun -or $isDryRun) {
        Write-Host "[note] Only a single case could have run for batch '$BatchName' (-s/--single or -t/--dryrun was forwarded); skipping compare_cases.py."
    } else {
        $runsDir = Join-Path $repoRoot 'runs'
        $completedCaseDirs = @(
            Get-ChildItem -Path $runsDir -Directory -Filter "${BatchName}_*" -ErrorAction SilentlyContinue |
                Where-Object { Test-Path (Join-Path $_.FullName 'outputs\outputs.h5') }
        )
        if ($completedCaseDirs.Count -le 1) {
            Write-Host "[note] Only $($completedCaseDirs.Count) completed case(s) found for batch '$BatchName'; skipping compare_cases.py (nothing to compare)."
        } else {
            Write-Host "[run] postprocessing/compare_cases.py for batch '$BatchName'"

            # Derive --startyear from the first non-ignored case in the cases file used
            # for this batch (first 4 digits of that case's `yearset` switch), so the
            # comparison plots start at the model's actual start year instead of
            # compare_cases.py's hardcoded default (2020). Best-effort: if this fails
            # (e.g. an unusual yearset format), warn and fall back to that default.
            Set-Location $repoRoot
            # Stderr (diagnostics/warnings from get_batch_info.py) streams straight to
            # the console; only stdout (case name on line 1, year on line 2 if valid)
            # is captured here.
            $compareStartYearArgs = @()
            if ($isMultistep -and $MultistepStartYear) {
                # Multistep already resolved this from the _baseline column during
                # validation, which is the right source here: get_batch_info.py returns
                # the leftmost NON-IGNORED case, but -m runs its three cases via -s,
                # which overrides `ignore` -- so that case may not be one that ran.
                $compareStartYearArgs = @('--startyear', $MultistepStartYear)
                Write-Host "[ok] Using --startyear $MultistepStartYear (from the ${m}_baseline column of $casesFilename)."
            } else {
                $batchInfo = @(Invoke-Native { uv run python CEPM/scripts/get_batch_info.py $casesFilename })
                if (($LASTEXITCODE -eq 0) -and ($batchInfo.Count -ge 2) -and ($batchInfo[1].Trim() -match '^\d{4}$')) {
                    $compareStartYearArgs = @('--startyear', $batchInfo[1].Trim())
                    Write-Host "[ok] Using --startyear $($batchInfo[1].Trim()) (from $casesFilename)."
                } else {
                    Write-Warning "Could not determine --startyear from $casesFilename (see output above, if any). Falling back to compare_cases.py's default."
                }
            }

            if (-not $q) {
                $startingCompareMsg = if ($o) {
                    "Compare-only run on $(hostname)$ntfyUser$ntfyBatch$ntfyCases; starting compare_cases.py at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
                } else {
                    "ReEDS run batch finished on $(hostname)$ntfyUser$ntfyBatch$ntfyCases; starting compare_cases.py at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
                }
                try {
                    Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                        -Body $startingCompareMsg | Out-Null
                } catch {}
            }
            Set-Location $repoRoot
            Invoke-Native { uv run python postprocessing/compare_cases.py "runs/${BatchName}_" @compareStartYearArgs }
            if ($LASTEXITCODE -ne 0) {
                Write-Warning 'compare_cases.py failed (see output above). Continuing.'
            } else {
                Write-Host '[ok] compare_cases.py completed.'
            }
            if (-not $q) {
                try {
                    Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
                        -Body "compare_cases.py finished on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
                } catch {}
            }
        }
    }
}

# Step 10: Notify ntfy.sh that the run (or, in -o/--compare-only mode, the
# comparison) has finished. Useful for long-running runs. Best-effort only --
# wrapped so a failed or offline notification never affects the run outcome;
# skipped entirely with -q/--quiet.
if (-not $q) {
    $finishedMsg = if ($o) {
        "Compare-only run finished on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    } else {
        "ReEDS run batch finished on $(hostname)$ntfyUser$ntfyBatch$ntfyCases at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    }
    try {
        Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/rmi-cepm-runs" -TimeoutSec 5 `
            -Body $finishedMsg | Out-Null
    } catch {}
}

} finally {
    # Step 11: Save the captured bootstrap+run log as bootstraplog.txt in the first
    # scenario's run folder. Uses the same leftmost-non-ignored-case convention as
    # the --startyear lookup above (CEPM/scripts/get_batch_info.py), since that case
    # folder is the one guaranteed to exist regardless of which cases in the batch
    # ran, succeeded, or failed. Runs even if an earlier step threw, so a failed
    # bootstrap/run still leaves a log behind; best-effort throughout so logging
    # itself can never fail the script or mask its real exit code.
    # Step 11a (multistep only): remove the per-batch files -m generated. Runs before
    # the transcript is saved so the cleanup is recorded in bootstraplog.txt, and
    # unconditionally -- a failed phase B must not leave a stale ceiling or a stray
    # cases file behind for the next batch to pick up (test T8). Best-effort by
    # design: a cleanup problem is warned, never thrown, so it can't mask the real
    # failure that got us here.
    if (-not [string]::IsNullOrWhiteSpace($m)) {
        foreach ($generated in @($capSysPath, $capRegPath, $MultistepCasesPath)) {
            if ($generated -and (Test-Path $generated)) {
                try {
                    Remove-Item -Path $generated -Force
                    Write-Host "[ok] Removed generated file $generated"
                } catch {
                    Write-Warning "Could not remove generated file ${generated}: $_"
                }
            }
        }
    }

    try { Stop-Transcript | Out-Null } catch {}

    try {
        Set-Location $repoRoot
        # In multistep mode the log belongs in the baseline's run folder: it is the one
        # folder guaranteed to exist if anything ran at all, and get_batch_info.py's
        # leftmost-non-ignored-case rule does not apply here (see Step 9).
        if ((-not [string]::IsNullOrWhiteSpace($m)) -and $multistepInfo -and $multistepInfo.Count -ge 1) {
            $firstCase = $multistepInfo[0].Trim()
            $batchInfoExit = 0
        } else {
            $batchInfo = @(Invoke-Native { uv run python CEPM/scripts/get_batch_info.py $casesFilename })
            $batchInfoExit = $LASTEXITCODE
            $firstCase = if ($batchInfo.Count -ge 1) { $batchInfo[0].Trim() } else { '' }
        }
        if (($batchInfoExit -eq 0) -and $firstCase) {
            $firstCaseDir = Join-Path $repoRoot "runs\${BatchName}_${firstCase}"
            if (Test-Path $firstCaseDir) {
                Copy-Item -Path $bootstrapLogPath -Destination (Join-Path $firstCaseDir 'bootstraplog.txt') -Force
                Write-Host "[ok] Saved bootstrap log to $(Join-Path $firstCaseDir 'bootstraplog.txt')"
            } else {
                Write-Warning "Could not save bootstraplog.txt: run folder not found at $firstCaseDir"
            }
        } else {
            Write-Warning "Could not save bootstraplog.txt: unable to determine the first non-ignored case in $casesFilename"
        }
    } catch {
        Write-Warning "Could not save bootstraplog.txt: $_"
    } finally {
        Remove-Item -Path $bootstrapLogPath -ErrorAction SilentlyContinue
    }
}


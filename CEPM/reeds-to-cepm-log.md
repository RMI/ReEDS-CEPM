# ReEDS-to-CEPM change log

Tracks how this repo diverges from upstream
[ReEDS](https://github.com/ReEDS-Model/ReEDS), including the location of every
upstream file that CEPM changed and what to re-check when we rebase onto a new
upstream release.

**Current ReEDS base:** upstream tag `2026.06.18`, plus upstream commits through
`62f6381e` (2026-06-23) — the merge base of this fork and `upstream/main`.

Most bug-fix entries below have a matching symptom-level entry in
[`known-issues.md`](known-issues.md); that file is the "my run failed, what is
this" index, while this file is the "what did we change, and what breaks on
rebase" index.

To regenerate the file-level inventory below:

```bash
git fetch upstream
git diff --stat $(git merge-base HEAD upstream/main) HEAD -- . ':!CEPM'
```

## Divergence inventory

Every upstream-owned path this fork has modified or added, as of the base above.
`CEPM/` itself is excluded — it is entirely new, and indexed by
[`CEPM/README.md`](README.md).

| Path | Change | Section |
|---|---|---|
| `reeds/input_processing/h5_to_gdx.py` | Modified | GAMS compatibility |
| `reeds/core/setup/b_inputs.gms` | Modified | GAMS compatibility |
| `reeds/input_processing/fuelcostprep.py` | Modified | Census divisions in fuelcostprep.py |
| `reeds/input_processing/recf.py` | Modified | recf.py when offshore wind is disabled |
| `reeds/resource_adequacy/reeds2pras/README.md` | Modified | Minor and cosmetic |
| `cases_small.csv` | Modified | Minor and cosmetic |
| `cases.csv` | Modified | Updated CAPEX for gas resources |
| `inputs/plant_characteristics/dollaryear.csv` | Modified | Updated CAPEX for gas resources |
| `inputs/plant_characteristics/gas-ccgt_CEPM_{all,low,high}.csv` | Added | Updated CAPEX for gas resources |
| `inputs/load/loadsite_st_epri_{low,medium,high}_extended_to_2032.csv` | Added | Updated load forecasts for data centers |
| `inputs/load/loadsite_st_NMtest1.csv`, `loadsite_transreg_WCtest1.csv` | Added | Updated load forecasts for data centers |
| `.github/workflows/python-app.yaml` | Modified | ENABLE_GAMS_CI variable |
| `pyproject.toml`, `uv.lock`, `.python-version` | Added | Using uv instead of mamba |
| `hourlize/pyproject.toml`, `.gitignore` | Modified | Using uv instead of mamba |
| `run_cepm.ps1` | Added | run_cepm helper script |
| `README.md` | Modified | CEPM documentation |
| `AGENTS.md` | Added | CEPM documentation |
| `cases_cepm.csv` | Added | cases_cepm.csv file |

# Changes to base ReEDS files

In some cases, we change base ReEDS files to fix bugs, ensure compatibility,
or adjust ReEDS functionality for CEPM's needs. Most of these are captured in
[`known-issues.md`](known-issues.md).

## GAMS compatibility

### Description of issue:

Our GAMS install is pinned to **44.4.0**. Upstream's h5-to-GDX pipeline generates
GAMS code that declares *every* set (`b_declare_sets.gms`) before `$loadDCR`-ing
*any* set (`b_load_sets.gms`). On 44.4.0 that ordering is illegal: once a set has
been referenced as another set's domain, GAMS refuses to load it, raising
`Error 579` ("Cannot clear a set used as a domain or used in lag/ord
operations"). The result was 16x Error 579 and `*** Status: Compilation error(s)`
in `a_createmodel.gms`, hitting **every** case that reached model compile,
regardless of switches. GAMS 45.6.0 lifted the restriction, so upstream does not
see this on its own toolchain.

### Files changed:

- `reeds/input_processing/h5_to_gdx.py` — new `write_sets_declare_and_load()`
  emits a single `autocode/b_sets.gms` that declares and loads each set one at a
  time (primary sets first, then domain-dependent subsets), replacing the
  separate `b_declare_sets.gms` / `b_load_sets.gms` pair.
- `reeds/core/setup/b_inputs.gms` — includes `autocode/b_sets.gms` inside the
  `$gdxin` block instead of the old declare-then-load pair, with a comment
  recording the version constraint.

### Reference:

[`guidance/GAMS_ERROR_579_INVESTIGATION.md`](guidance/GAMS_ERROR_579_INVESTIGATION.md),
[`known-issues.md`](known-issues.md)

### What to test in new releases:

- Does upstream's `h5_to_gdx.py` still generate `b_declare_sets.gms` +
  `b_load_sets.gms`? If upstream restructures that codegen, this patch will
  conflict and should be re-derived rather than merged.
- Has any new primary set or domain-dependent subset been added upstream? The
  fix orders sets by dependency, so a new set with an unnoticed domain
  dependency can reintroduce the error.
- If the GAMS install moves to **45.6.0 or newer**, this patch is no longer
  required — consider dropping it and returning to upstream's codegen to shrink
  the diff.

## Resolving census divisions in fuelcostprep.py

### Description of issue:

`cendivweights.csv` triggered `Error 170 — Domain violation for element` when
GAMS read it. `fuelcostprep.py` builds census-division weights by smearing zones
against `dfmap['cendiv']`, which is drawn from the **original national
hierarchy**. For a sub-national run, the smear can therefore pull in census
divisions that are not part of the run's own `cendiv` set — typically a border
region bleeding into a neighboring division — and GAMS rejects those elements.
Reproduced on both `transreg/WestConnect` and `interconnect/western` runs.

### Files changed:

- `reeds/input_processing/fuelcostprep.py` — restricts `dfmap['cendiv']` to
  `val_cendiv` (the divisions actually in this run's region set) before smearing.

### Reference: [`known-issues.md`](known-issues.md)

### What to test in new releases:

- Does `reeds.io.get_dfmap()` still return a national-scope `cendiv` frame, or
  has upstream started scoping it to the run's regions? If upstream scopes it,
  this patch becomes redundant.
- Is `val_cendiv` still defined and populated at that point in the script?
- Re-run at least one sub-national case (a `transreg/`, `nercr/`, or `st/`
  selection — not `country/USA`) through `copy_files.py`, since a national run
  cannot surface this bug.

## Resolving recf.py when offshore wind is disabled

### Description of issue:

With `GSw_OfsWind = 0`, `recf.py` raised
`UnboundLocalError: cannot access local variable 'df_windofs' where it is not
associated with a value`. `df_windofs` is only assigned inside
`if int(sw['GSw_OfsWind']) != 0:`, but the later concat referenced it
unconditionally — a code-path bug exposed by disabling offshore wind, not a bad
input file.

### Files changed:

- `reeds/input_processing/recf.py` — adds an `else` branch assigning an empty
  `pd.DataFrame(index=df_windons.index)` so the concat inputs stay consistent.

### Reference:

[`known-issues.md`](known-issues.md)

### What to test in new releases:

- Has upstream guarded the concat itself (making this patch redundant), or added
  further unconditional references to `df_windofs`?
- Run one case with `GSw_OfsWind = 0` through `recf.py`. Upstream's default is
  `GSw_OfsWind = 1`, so upstream CI does not exercise this path.
- Note the related trap in [`known-issues.md`](known-issues.md): disabling
  offshore wind via `techs_banned` instead of `GSw_OfsWind = 0` leaves the
  `eq_RPS_OFSWind` state mandate active and the model infeasible.

## Minor and cosmetic

### Description of issue:

Small changes with no effect on model results.

### Files changed:

- `reeds/resource_adequacy/reeds2pras/README.md` — corrects the test-run paths
  (`ReEDS/reeds2pras/test` to `ReEDS/reeds/resource_adequacy/reeds2pras/test`)
  after upstream relocated the vendored ReEDS2PRAS tree without updating its
  README.
- `cases_small.csv` — `endyear` 2030 to 2029.

### Reference:

n/a

### What to test in new releases:

- If upstream fixes its own reeds2pras README paths, drop our version to keep the
  vendored tree byte-identical to upstream. That tree is otherwise nearly
  pristine, which is what keeps future ReEDS2PRAS syncs cheap — see Issue 4 of
  [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md).

# Custom CEPM inputs and changes to ReEDS files

We also implement several custom inputs to our CEPM scenarios, which add new
input files and also change some underlying ReEDS files. These should all have
documentation in [`preprocessing/`](preprocessing/), and must meet the criteria
in [`preprocessing/input-requirements.md`](preprocessing/input-requirements.md).

## Updated CAPEX for gas resources

### Description:

Regression-based 2026-2032 capex forecast for CCGT and CT gas plants built from
the Halcyon Gas Power Plant Tracker (17 July 2026), replacing ATB's cost
trajectory with one drawn from the current project pipeline. `capcost` is
overwritten for `Gas-CC` and `Gas-CT` in 2026-2032 only; all other gas
technologies and years keep their ATB values, and `gas_ATB_2024_moderate.csv` is
left unmodified.

### Input files created:

- `inputs/plant_characteristics/gas-ccgt_CEPM_low.csv` — CCGT low-cost scenario
- `inputs/plant_characteristics/gas-ccgt_CEPM_high.csv` — CCGT high-cost scenario
- `inputs/plant_characteristics/gas-ccgt_CEPM_all.csv` — CCGT all-data (mid /
  reference) scenario

Gas-CT uses the same CT forecast in all three. Selected via `plantchar_gas`.

### Underlying ReEDS files changed:

- `cases.csv` — `plantchar_gas` description amended to note that upstream options
  start with `gas_` while RMI/CEPM options start with `gas-ccgt_`. The `Choices`
  pattern already admitted the new names, so no validation change was needed.
- `inputs/plant_characteristics/dollaryear.csv` — three new rows registering all
  three files as `2022` dollars.

`runfiles.csv` needed no change: its
`inputs/plant_characteristics/{plantchar_gas}.csv` template resolves these by
name.

### Reference:

[`preprocessing/gas_capex_forecast/`](preprocessing/gas_capex_forecast/)

### What to test in new releases

- Does `dollaryear.csv` still exist in the same location and format, and are our
  three rows still present after the rebase? A dropped row stays silent until
  costs come out wrong by an inflation factor.
- Has the `Choices` pattern for `plantchar_gas` in `cases.csv` become stricter
  (an explicit list rather than a prefix pattern)? If so, our filenames must be
  added to it.
- Has upstream changed the ATB vintage, or the columns/units in
  `gas_ATB_2024_moderate.csv`? Our files are derived from that shape, so a schema
  change means regenerating them.
- Confirm the notebooks still run and reproduce the committed CSVs.

## Updated load forecasts for data centers

### Description:

State-level data center load-site inputs for all 48 contiguous states, built from
EPRI Powering Intelligence projections in three scenarios (Low / Medium / High),
extended to 2032. These are the load-site inputs the national CEPM cases actually
run with — `cases_cepm.csv` currently selects
`st_epri_medium_extended_to_2032`.

### Input files created:

- `inputs/load/loadsite_st_epri_low_extended_to_2032.csv`
- `inputs/load/loadsite_st_epri_medium_extended_to_2032.csv`
- `inputs/load/loadsite_st_epri_high_extended_to_2032.csv`

Long format (`*loadsitereg,t,MW`), 48 states, 2026-2032. Selected via
`GSw_LoadSiteTrajectory`, and only staged when `GSw_LoadSiteCF > 0`.

Also added as reference fixtures for the large-load-site feature:
`inputs/load/loadsite_st_NMtest1.csv` and
`inputs/load/loadsite_transreg_WCtest1.csv` (single-region test cases for
optimized large-load placement).

A New-Mexico-only variant exists in
[`preprocessing/dc_load_nm/`](preprocessing/dc_load_nm/) but is superseded by the
all-states pipeline; its output is not committed and no case selects it.

### Underlying ReEDS files changed:

None. `runfiles.csv`'s existing `loadsite_{GSw_LoadSiteTrajectory}.csv` template
picks these up by name, and that switch's `Choices` entry is a generic pattern
(`^(nercr|transreg|transgrp|cendiv|st|interconnect|country|usda_region)_.*$`)
that already admits any `st_*` identifier. No `dollaryear.csv` entry is needed —
load sites are MW, not monetary values.

### Reference:

[`preprocessing/datacenter_load_forecast/`](preprocessing/datacenter_load_forecast/)

### What to test in new releases:

- Has loadsite's compatibility changed? Specifically: is the
  `loadsite_{GSw_LoadSiteTrajectory}.csv` template still in `runfiles.csv`, is
  the `Choices` pattern still permissive, and does `GSw_LoadSiteCF` still gate
  staging?
- Are we changing the underlying load forecast / would that double-count data
  center loads? Check whether upstream's default load projection has absorbed
  data center growth, which would double-count against our load sites.
- Is the expected long-format schema (`*loadsitereg,t,MW`) unchanged?

# CEPM documentation and functionality

## GitHub repo-level ENABLE_GAMS_CI variable

### Description:

The `run-ReEDS` and `run-R2X` CI jobs need a GAMS license, which GitHub-hosted
runners do not have. Both jobs are gated on a repo-level **configuration
variable** so they can be toggled without a commit; those checks are instead
reproduced on-prem per
[`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md).

The gate reads `vars.ENABLE_GAMS_CI`, which is populated **only** from
GitHub-side configuration (Settings → Secrets and variables → Actions →
Variables, or `gh variable set`) — never from anything declared in the workflow
file. It is currently `false`, so both jobs skip on every push and PR.

Two footguns worth knowing. An unset variable evaluates to an empty string rather
than erroring, so deleting it silently skips both jobs while still reporting a
green check. And the comparison is a case-sensitive string match against
`'true'`, so `True`, `TRUE`, or `1` will not enable it.

### Files included:

- `.github/workflows/python-app.yaml` — `if:` conditions on the `run-ReEDS` and
  `run-R2X` jobs, plus a comment in the workflow-level `env:` block recording
  where the variable actually lives. (An earlier revision also set
  `ENABLE_GAMS_CI: 'false'` as a workflow `env:` value; that had no effect,
  since `env:` populates the `env` context and not `vars`, and it has been
  replaced by the comment.)

### Reference:

[`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md); current
value via `gh variable list --repo RMI/ReEDS-CEPM`

### What to test in new releases:

- Did upstream rename, split, or add GAMS-dependent jobs? Any new job needing
  GAMS must get the same `vars.ENABLE_GAMS_CI` gate, or it will fail on every PR.
- Do the existing `if:` conditions survive the rebase? A merge that takes
  upstream's side restores unconditional execution and turns CI red.
- Does the variable still exist at the repo level? It is not version-controlled,
  so it can be deleted without leaving any trace in the repo.

## Using uv instead of mamba for environment/package management

### Description:

CEPM manages the Python environment with [uv](https://docs.astral.sh/uv/) rather
than conda/mamba. Upstream ships `environment.yml`; we keep that file for
reference and upstream parity but resolve dependencies from `pyproject.toml` /
`uv.lock`, pinned to Python 3.11. Because ReEDS itself expects conda-style
environment variables, `run_cepm.ps1` sets `CONDA_DEFAULT_ENV=reeds2` and
`CONDA_PREFIX` to the uv venv path so the model's own checks pass.

`environment.yml` and `pyproject.toml` are kept in sync **by hand**, with drift
reported by [`scripts/check_env_sync.py`](scripts/check_env_sync.py) against a
known-accepted allowlist.

### Files included:

- `pyproject.toml` — project metadata and dependencies
  (`requires-python = "==3.11.*"`)
- `uv.lock` — resolved lockfile
- `.python-version` — `3.11`, written by `uv python pin`. Note this file is both
  committed *and* listed in `.gitignore`; because it is tracked, the ignore rule
  has no effect. Worth reconciling one way or the other.
- `hourlize/pyproject.toml` — trailing-whitespace cleanup only
- `.gitignore` — ignores `.python-version` and `ReEDS.egg-info/`
- [`scripts/check_env_sync.py`](scripts/check_env_sync.py) — drift checker
- [`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md) — the sync procedure
  and accepted-drift list

### Reference:

[`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md),
[`scripts/check_env_sync.py`](scripts/check_env_sync.py)

### What to test in new releases:

- Does the environment still resolve? Run `uv sync --extra dev` on a clean
  checkout.
- Did Python version expectations change? If upstream's `environment.yml` moves
  off 3.11, update `requires-python` and re-pin.
- Did upstream add, remove, or re-pin any dependency in `environment.yml`? Each
  change has to be mirrored into `pyproject.toml` by hand; run
  `check_env_sync.py` and reconcile anything not on the allowlist.
- Has upstream adopted its own root `pyproject.toml`? If so, ours conflicts
  directly and needs merging rather than overwriting.
- Does ReEDS still read `CONDA_DEFAULT_ENV` / `CONDA_PREFIX`? If upstream drops
  those checks, the shims in `run_cepm.ps1` can go.

## run_cepm helper script

### Description:

A PowerShell wrapper that runs the whole CEPM setup-and-launch sequence in one
command: verifies GAMS is on `PATH` and licensed, verifies Julia is exactly
1.12.1, sets the conda-style environment variables ReEDS expects, pins Python
3.11 and runs `uv sync --extra dev`, instantiates Julia dependencies (offline
fast path first, full instantiate as fallback), warns on `environment.yml` to
`pyproject.toml` drift, then launches `runreeds.py` forwarding all remaining
arguments. It also sends best-effort ntfy.sh notifications (topic
`rmi-cepm-runs`) before and after the run.

It intercepts `-b/--BatchName` and `-c/--cases_suffix` so it can name them in
notifications, then forwards them to `runreeds.py` unchanged. Bootstrap-only
flags: `-y/--bypass` (skip `uv sync` and Julia instantiate), `-q/--quiet` (no
notifications), and `-u/--user <name>`.

### Files included:

- [`../run_cepm.ps1`](../run_cepm.ps1) — the script; lives at the repo root so it
  is callable as `.\run_cepm.ps1`
- [`scripts/check_env_sync.py`](scripts/check_env_sync.py) — invoked at step 7

### Reference:

[`../run_cepm.ps1`](../run_cepm.ps1), [`scripts/`](scripts/), and the quick-start
section of the [root README](../README.md)

### What to test in new releases:

- Does the environment still resolve? Did Python version expectations change? Do
  we need to change the environment variables that the script automatically
  sets?
- Has the required Julia version moved off 1.12.1? The script hard-fails on any
  other version; check `JULIA_VERSION` in `.github/workflows/python-app.yaml`
  and upstream's install docs.
- Have `runreeds.py`'s flags changed — particularly `-b/--BatchName` and
  `-c/--cases_suffix`, which the script parses itself, and any new short flag
  that could collide with `-y`, `-q`, or `-u`?
- Is `runreeds.py` still the entry point, still at the repo root, still under
  that name?

## CEPM documentation

### Description:

CEPM-specific documentation is collected under [`CEPM/`](README.md) rather than
scattered through the upstream tree, so the fork's surface area stays reviewable
against upstream. Two documentation files nonetheless live in upstream locations,
because that is where readers and tools look for them.

### Files included:

- `README.md` (repo root) — rewritten as "ReEDS for CEPM": what CEPM is and how
  it differs from ReEDS, a CEPM quick-start (uv/Python, GAMS, Julia, environment
  setup, large input files, PowerShell runtime, running the model), and a
  troubleshooting section.
- `AGENTS.md` (repo root) — coding-agent guide: project structure, environment,
  build/run commands, testing, run flow, code style, debugging notes, key
  subsystems, data handling, and git workflow.
- [`CEPM/`](README.md) — everything else, indexed by
  [`CEPM/README.md`](README.md).

### Reference:

[`CEPM/README.md`](README.md)

### What to test in new releases:

- Did upstream substantially rewrite the root `README.md`? It will conflict every
  time; decide deliberately whether to re-apply the CEPM version or merge
  upstream's new content into it.
- Has upstream added its own `AGENTS.md` or `CLAUDE.md`? If so, merge rather than
  overwrite.
- Do the quick-start steps still work end to end on a clean clone — particularly
  the install commands, the Julia version, and the large-input-file instructions?
- Do the CEPM docs still describe reality? On a rebase, re-check
  [`known-issues.md`](known-issues.md)'s "Fixed upstream?" verdicts, which are
  pinned to a specific upstream tag.

## cases_cepm.csv file

### Description:

CEPM's own case definitions, kept in a separate file rather than as edits to
upstream's `cases.csv`. `runreeds.py` already supports this through its
`cases_{suffix}.csv` convention, so the file is picked up with `-c cepm` /
`--cases_suffix cepm` and needs **no upstream code change** — `cases.csv` stays
as the untouched switch-defaults reference.

Current cases: `WECC_SW-test`, `NM_optimized_2yrs`, `NM_optimized_3yrs`,
`NM_optimized_LLtest`, `USA_gas_mvp` (deprecated), and `USA_optimized_mvp`. Set
a case's `ignore` row to `1` to skip it.

### Files included:

- `cases_cepm.csv` — the case definitions
- `cases.csv` — unchanged apart from the `plantchar_gas` description noted above

### Reference:

[`preprocessing/`](preprocessing/) for the inputs these cases select;
[`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md) for how a
switch value becomes an input file path

### What to test in new releases:

- Did any switch we set get **renamed, removed, or have its `Choices`
  tightened**? `runreeds.py` validates every requested case's switches up front,
  so one stale switch name blocks the entire launch batch.
- Did upstream change a switch's **default**? Blank cells in `cases_cepm.csv`
  inherit from `cases.csv`, so an upstream default change silently changes our
  cases.
- Is the `cases_{suffix}.csv` convention still supported by `runreeds.py`?
- Re-run at least one case through `copy_files.py` to confirm the switch
  combination still initializes; see
  [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md)
  for which `GSw_ZoneSet`/`GSw_Region` combinations are known to work.

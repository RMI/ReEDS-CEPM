# `CEPM/` — RMI/CEPM-specific documentation and tooling

This folder holds the documentation and helper scripts that exist only in
RMI's CEPM fork and have no counterpart in the upstream
[ReEDS](https://github.com/ReEDS-Model/ReEDS) repository. To the extent
practical, CEPM-specific additions are collected here rather than scattered
through the upstream source tree, so that the fork's surface area stays easy to
review against upstream.

Some CEPM changes unavoidably live in upstream file locations (GAMS
compatibility fixes, `cases_cepm.csv`, `pyproject.toml`, `run_cepm.ps1`, and
similar). Those are catalogued in
[`reeds-to-cepm-log.md`](reeds-to-cepm-log.md) rather than moved here.

## Start here

- **A run just failed** → [`known-issues.md`](known-issues.md). Symptom → cause →
  status for every error seen in a CEPM run so far, including whether it is fixed
  upstream. Check it before debugging anything.
- **Adding a new custom input** → [`preprocessing/input-requirements.md`](preprocessing/input-requirements.md)
  for the rules, then [`preprocessing/README_TEMPLATE.md`](preprocessing/README_TEMPLATE.md)
  to document it.
- **Wondering what we changed vs. upstream** → [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md).

## Top-level

| File | Summary |
|---|---|
| [`README.md`](README.md) | This file — an index of everything in `CEPM/`. |
| [`known-issues.md`](known-issues.md) | Running log of every error hit in a CEPM run: symptom, root cause, current status, and a **Fixed upstream?** verdict checked against upstream tag `2026.08.03`. Covers the `Error 579` GAMS compile failure, the `eq_RPS_OFSWind` and DE hydrogen infeasibilities, `z134`/`z90` zoneset gaps, the `startyear` hydro-CF constraint currently blocking `USA_optimized_mvp`, postprocessing and `reeds_to_rev` failures, and a list of cosmetic warnings that are safe to ignore. Deeper investigations get their own doc under `guidance/` and are linked from the relevant entry. |
| [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md) | Change log of how this fork diverges from upstream ReEDS — per change: description, files changed, reference, and what to re-test on each new upstream release. Sectioned into GAMS-compatibility fixes, helper scripts, and custom CEPM inputs. Skeleton is in place; most sections are not yet filled in. |

## `guidance/` — how-to and investigation write-ups

Ordered roughly from most general to most situational, with closed
investigations at the end.

| File | Summary |
|---|---|
| [`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md) | How `runfiles.csv` and `copy_files.py` turn a switch value into an input file path, and why bespoke CEPM inputs belong in `inputs/` if we want to keep access to upstream defaults. |
| [`guidance/tech-limit-options.md`](guidance/tech-limit-options.md) | The mechanisms available for restricting a technology's capacity — `ban`/`bannew`, resource supply curve edits, the interconnection-queue cumulative cap, growth-rate constraints, cost multipliers, and customizing `tg` — with the implications of each. |
| [`guidance/managing-pras.md`](guidance/managing-pras.md) | Which switches actually control whether PRAS runs, how often, and how expensive it is — and which ones people expect to control it but don't. Key finding: `GSw_PRM_CapCredit` does not disable PRAS; only `pras_samples=0` reliably skips its Monte Carlo compute. Includes a "get as close as possible to no PRAS" recipe. |
| [`guidance/loadsite-mechanism.md`](guidance/loadsite-mechanism.md) | How `GSw_LoadSiteCF`/`GSw_LoadSiteRA`/`GSw_LoadSiteTrajectory` wire into the "optimally sited load" (data-center) feature — Python and GAMS call sites for each, how the trajectory file/hierarchy level is selected, and why a trajectory file's regions don't need to match the run's own `GSw_Region`/`GSw_ZoneSet` (out-of-scope regions are silently dropped, not an error). |
| [`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md) | How to keep `environment.yml` (conda/mamba) and `pyproject.toml`/`uv.lock` (uv) in sync by hand, plus the list of known-accepted drift between them. |
| [`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md) | Runbook for reproducing the GitHub PR CI checks on an on-prem machine, for the CI jobs that cannot run on GitHub-hosted runners because of GAMS licensing. |
| [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md) | Audit of which `GSw_ZoneSet`/`GSw_Region` combinations actually initialize: the `techs_banned.csv` region-mapping bug (fixed), the `z90` missing-file gap, the `z134` `writecapdat.py` `ba`-key bug, and a PRAS single-zone crash, with candidate fixes and upstream comparisons for the three still open. |
| [`guidance/GAMS_ERROR_579_INVESTIGATION.md`](guidance/GAMS_ERROR_579_INVESTIGATION.md) | Investigation and fix for the 16x `Error 579` model-compile failure on GAMS 44.4.0, caused by declaring every set before loading any of them in the h5-to-gdx pipeline. |

## `preprocessing/` — custom CEPM input pipelines

Each pipeline folder keeps its raw source data and notebooks here but writes its
generated outputs into the repo's top-level `inputs/` tree, not into `CEPM/`.
See [`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md) for why a
bespoke input has to sit alongside the upstream file it is an alternative to.

Every folder has its own README with source, outputs, switches, ReEDS files
touched, and whether a run has confirmed it — see `README_TEMPLATE.md` for that
structure.

| Path | Summary |
|---|---|
| [`preprocessing/input-requirements.md`](preprocessing/input-requirements.md) | The criteria a custom CEPM input has to meet: its own descriptive folder, an orienting README or `main` notebook, traceable raw source data, `CEPM` in output filenames, validation against the ReEDS input it replaces, outputs written straight to their final repo location, and a record of every ReEDS file edited (`cases.csv`, `runfiles.csv`, `dollaryear.csv`, …). Read this before adding an input. |
| [`preprocessing/README_TEMPLATE.md`](preprocessing/README_TEMPLATE.md) | Template for the per-folder READMEs below: the sections each pipeline should document, including source, what it produces, the switches and ReEDS files it touches, and known issues. |
| [`preprocessing/datacenter_load_forecast/`](preprocessing/datacenter_load_forecast/) | Notebook and EPRI Powering Intelligence export that build state-level data center load-site inputs for all 48 contiguous states in Low/Medium/High scenarios, written to `inputs/load/`. This is the load-site input the national CEPM cases currently select (`GSw_LoadSiteTrajectory`) — see [`guidance/loadsite-mechanism.md`](guidance/loadsite-mechanism.md) for how that switch and its siblings actually work. |
| [`preprocessing/gas_capex_forecast/`](preprocessing/gas_capex_forecast/) | Four notebooks and the Halcyon Gas Power Plant Tracker exports behind the 2026-2032 CCGT and CT gas capex regression forecast, producing the `gas-ccgt_CEPM_{low,high,all}.csv` variants in `inputs/plant_characteristics/` selected by `plantchar_gas`. Its [README](preprocessing/gas_capex_forecast/README.md) documents the notebook run order. |
| [`preprocessing/dc_load_nm/`](preprocessing/dc_load_nm/) | New-Mexico-only variant of the same EPRI data, using annual energy converted to a flat hourly MW load. Superseded by `datacenter_load_forecast/` and kept for posterity — its output is not committed and no case selects it. |

## `scripts/`

| File | Summary |
|---|---|
| [`scripts/check_env_sync.py`](scripts/check_env_sync.py) | Stdlib-only script that reports dependency drift between `environment.yml` and `pyproject.toml`, warning only on differences that are not on its known-accepted allowlist. |

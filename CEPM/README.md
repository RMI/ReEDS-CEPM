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

## Contents

Ordered roughly from most general to most situational, with closed
investigations near the end.

| File | Summary |
|---|---|
| [`README.md`](README.md) | This file — a one-line summary of everything in `CEPM/`. |
| [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md) | Tracks how this repo diverges from upstream ReEDS, including which upstream files CEPM changed. Currently a placeholder. |
| [`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md) | How `runfiles.csv` and `copy_files.py` turn a switch value into an input file path, and why bespoke CEPM inputs belong in `inputs/` if we want to keep access to upstream defaults. |
| [`guidance/tech-limit-options.md`](guidance/tech-limit-options.md) | The mechanisms available for restricting a technology's capacity — `ban`/`bannew`, resource supply curve edits, the interconnection-queue cumulative cap, growth-rate constraints, cost multipliers, and customizing `tg` — with the implications of each. |
| [`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md) | How to keep `environment.yml` (conda/mamba) and `pyproject.toml`/`uv.lock` (uv) in sync by hand, plus the list of known-accepted drift between them. |
| [`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md) | Runbook for reproducing the GitHub PR CI checks on an on-prem machine, for the CI jobs that cannot run on GitHub-hosted runners because of GAMS licensing. |
| [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md) | Audit of which `GSw_ZoneSet`/`GSw_Region` combinations actually initialize: the `techs_banned.csv` region-mapping bug (fixed), the z90 missing-file gap, the z134 `writecapdat.py` `ba`-key bug, and a PRAS single-zone crash, with candidate fixes written up for the three still open. |
| [`guidance/GAMS_ERROR_579_INVESTIGATION.md`](guidance/GAMS_ERROR_579_INVESTIGATION.md) | Investigation and fix for the 16x `Error 579` model-compile failure on GAMS 44.4.0, caused by declaring every set before loading any of them in the h5-to-gdx pipeline. |
| [`scripts/check_env_sync.py`](scripts/check_env_sync.py) | Stdlib-only script that reports dependency drift between `environment.yml` and `pyproject.toml`, warning only on differences that are not on its known-accepted allowlist. |
| [`preprocessing/README_TEMPLATE.md`](preprocessing/README_TEMPLATE.md) | Template for the per-folder READMEs under `preprocessing/`: the sections each input pipeline should document, including its source, what it produces, the switches and ReEDS files it touches, and known issues. |
| [`preprocessing/datacenter_load_forecast/`](preprocessing/datacenter_load_forecast/) | Notebook and EPRI Powering Intelligence export that build the state-level data center load-site inputs for all 48 contiguous states in Low/Medium/High scenarios, written to `inputs/load/`. This is the load-site input the national CEPM cases currently select. |
| [`preprocessing/dc_load_nm/`](preprocessing/dc_load_nm/) | New-Mexico-only variant of the same EPRI data, using annual energy converted to a flat hourly MW load with a linear 2031-2032 extrapolation. Not committed and not selected by any case — see its README for how it differs from `datacenter_load_forecast/`. |
| [`preprocessing/gas_capex_forecast/`](preprocessing/gas_capex_forecast/) | Notebooks and Halcyon Gas Power Plant Tracker data behind the 2026-2032 CCGT and CT gas capex regression forecast, which produces the CEPM gas cost variants in `inputs/plant_characteristics/`. Has its own [README](preprocessing/gas_capex_forecast/README.md) documenting the notebook run order. |

Both `preprocessing/` directories keep their source data and notebooks here but
write their generated outputs into the repo's top-level `inputs/` tree, not into
`CEPM/`. See [`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md)
for why a bespoke input has to sit alongside the upstream file it is an
alternative to.

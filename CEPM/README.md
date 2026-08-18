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
| [`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md) | How to keep `environment.yml` (conda/mamba) and `pyproject.toml`/`uv.lock` (uv) in sync by hand, plus the list of known-accepted drift between them. |
| [`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md) | Runbook for reproducing the GitHub PR CI checks on an on-prem machine, for the CI jobs that cannot run on GitHub-hosted runners because of GAMS licensing. |
| [`guidance/tech-limit-options.md`](guidance/tech-limit-options.md) | The mechanisms available for restricting a technology's capacity — `ban`/`bannew`, resource supply curve edits, the interconnection-queue cumulative cap, growth-rate constraints, cost multipliers, and customizing `tg` — with the implications of each. |
| [`guidance/GAMS_ERROR_579_INVESTIGATION.md`](guidance/GAMS_ERROR_579_INVESTIGATION.md) | Investigation and fix for the 16x `Error 579` model-compile failure on GAMS 44.4.0, caused by declaring every set before loading any of them in the h5-to-gdx pipeline. |
| [`scripts/check_env_sync.py`](scripts/check_env_sync.py) | Stdlib-only script that reports dependency drift between `environment.yml` and `pyproject.toml`, warning only on differences that are not on its known-accepted allowlist. |

## Related, but outside this folder

- `run_cepm.ps1` (repo root) — the CEPM setup-and-run helper: verifies GAMS,
  Julia, and Python, syncs the uv environment, runs
  [`scripts/check_env_sync.py`](scripts/check_env_sync.py) as a non-fatal step,
  then forwards its arguments to `runreeds.py`. It lives at the repo root
  because it is the entry point users invoke directly.
- `cases_cepm.csv` (repo root) — the CEPM scenario definitions, alongside the
  other `cases_*.csv` files it has to sit with to be discovered by
  `runreeds.py -c cepm`.

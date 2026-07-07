# ReEDS Agent Guide

ReEDS is a capacity planning and dispatch model for the U.S. electricity system.
The repository is a mixed Python, GAMS, and Julia codebase: Python prepares inputs,
orchestrates runs, and postprocesses outputs; GAMS contains the optimization model;
Julia translates solved ReEDS systems into PRAS resource adequacy systems.

This repo was restructured upstream so that most Python and GAMS source now lives
inside the `reeds/` package (the old flat repo-root layout is gone). The main
orchestrator is `runreeds.py` (formerly `runbatch.py`).

Use this file as the first stop for agent orientation. Deeper references:

- @README.md: repository overview, installation entry points, and basic run
  instructions.
- @docs/source/setup.md: user-facing setup, dependency, and environment
  instructions.
- @docs/source/user_guide.md: scenario configuration, run options, switches,
  outputs, and common workflows.
- @docs/source/developer_best_practices.md: coding conventions, testing
  expectations, and GAMS development guidance.
- @sources_documentation.md: data-source documentation expectations and input
  provenance notes.

## Project Structure

- `runreeds.py`: main run orchestrator (repo root). Reads `cases*.csv`, creates
  `runs/{BatchName}_{case}/`, writes per-case run scripts, copies needed
  code/data into the case folder, and launches local or HPC (SLURM) runs.
- `cases.csv`: canonical case/switch catalog, with descriptions, allowed values,
  and defaults. Scenario files such as `cases_test.csv`, `cases_small.csv`,
  `cases_cepm.csv`, and study-specific `cases_{suffix}.csv` override defaults by
  case column.
- `reeds/`: the main Python package. Top-level modules include `reeds.io`,
  `reeds.inputs`, `reeds.spatial`, `reeds.techs`, `reeds.log`, `reeds.checks`,
  `reeds.financials`, `reeds.results`, `reeds.timeseries`, `reeds.units`,
  `reeds.remote`, and plotting modules (`reeds.plots`, `reeds.reedsplots`,
  `reeds.prasplots`).
- `reeds/core/`: the GAMS model and its solve orchestration, grouped by stage:
  - `reeds/core/setup/`: model assembly. `a_createmodel.gms` is the top-level
    assembler and `$include`s, in order, `b_inputs.gms` (GAMS-readable inputs) →
    `c_model.gms` (variables/equations) → `d_objective.gms` (objective) →
    `d_mga.gms` → `e_solveprep.gms`.
  - `reeds/core/solve/`: solve drivers. `solve.py` is the Python solve wrapper;
    `3_solve_oneyear.gms`, `3_solve_allyears.gms`, and `3_solve_window.gms`
    correspond to `timetype` `seq`, `int`, and `win`. Also `1_tc_phaseout.py`,
    `2_financials.gms`, `2_temporal_params.gms`, `4_post_solve_adjustments.gms`,
    `5_varfix.gms`, `6_data_dump.gms`.
  - `reeds/core/solve_pcm/`: production-cost-model solve (`solve_pcm.gms`,
    `unfix_op.gms`).
  - `reeds/core/terminus/`: reporting. `report.gms` is the main report,
    `report_dump.py` dumps report parameters, `report_params.csv` lists the
    reported parameters, plus `dump_alldata.gms`, `powfrac_calc.gms`,
    `get_last_iter.py`.
- `reeds/input_processing/`: scripts run during case setup to create files under
  `runs/{case}/inputs_case/`. `copy_files.py` is the broad data copier/filter;
  scripts such as `recf.py`, `hourly_repperiods.py`, `hourly_load.py`,
  `writecapdat.py`, `plantcostprep.py`, `transmission.py`, and `check_inputs.py`
  derive key inputs. `runfiles.csv` (the input-file inventory: how each file is
  copied, filtered, aggregated, or transformed into `inputs_case/`) lives here.
- `reeds/resource_adequacy/`: capacity credit, PRAS, and stress-period logic that
  runs between solve years when enabled. `ra_calcs.py` (formerly `Augur.py`) is
  the entry point; also `capacity_credit.py`, `stress_periods.py`, `prep_data.py`,
  `diagnostic_plots.py`, `run_pras.jl`, and `ra_switches.csv`. The Julia
  translation package lives at `reeds/resource_adequacy/reeds2pras/`.
- `reeds/hpc/`: HPC helpers (`aws_setup.sh`, `srun_template.sh`).
- `reeds/solver/`: solver option files (`cplex.opt`, `cplex.op2`, `cbc.opt`,
  `gurobi.opt`).
- `hourlize/`: preprocessing for resource and load profiles. Main wrapper is
  `hourlize/run_hourlize.py`; `hourlize/reeds_to_rev.py` disaggregates ReEDS
  investments back to reV supply curve sites.
- `postprocessing/`: reports, diagnostics, plots, run comparison, retail rates,
  reValue, bokehpivot, Tableau, air-quality, land-use, R2X (`run_r2x.py`), and
  output cleanup.
- `preprocessing/`: tools for preparing repository inputs before ReEDS runs.
- `helpers/`: operational helpers — `runstatus.py`, `restart_runs.py`,
  `interim_report.py`, `interim_report_batch.py`.
- `inputs/`: checked-in model inputs plus pointers to large remote inputs.
  `inputs/remote_files.csv` catalogs remote data; large files are normally
  downloaded into `inputs/remote/` and linked or copied as needed.
- `runs/`: generated run folders. Treat contents as user/generated artifacts and
  do not edit or delete them unless the task explicitly targets a run.
- `tests/` and `hourlize/tests/`: pytest tests. Some tests are lightweight unit
  tests; `tests/test_outputs.py` requires a completed ReEDS case.
- `.github/workflows/`: CI, docs, and workflow-quality automation.
- `CEPM/`: RMI/CEPM-specific docs kept separate from upstream docs —
  `UV_MAMBA_GUIDE.md` (uv/mamba dependency mapping) and `internal-ci-testing.md`
  (on-prem CI runbook). The CEPM run bootstrap is `bootstrap_CEPM.ps1` at repo root.

## Environment

- Python is pinned to `3.11` via `.python-version` and `pyproject.toml`.
- Python dependencies are managed with `uv` and locked in `uv.lock`.
  `environment.yml` is kept as an upstream-compatible conda/mamba fallback; see
  @CEPM/UV_MAMBA_GUIDE.md for keeping the two in sync.
- Julia `1.12.1` is the tested version for ReEDS2PRAS and stress-period flows.
- GAMS is required for model solves. CPLEX is the normal solver; small cases may
  work with other solvers, but CPLEX-oriented settings are the maintained path.
- Several large inputs are remote. `reeds/remote.py` downloads them based on
  `inputs/remote_files.csv`; network access may be needed.
- ReEDS still expects Conda-style environment variables even when using `uv`.

PowerShell setup used by local agents on Windows:

```powershell
uv sync --extra dev
julia --project=. instantiate.jl
$env:CONDA_DEFAULT_ENV = "reeds2"
$env:CONDA_PREFIX = (Resolve-Path .venv).Path
```

Optional remote data preload:

```powershell
uv run python reeds/remote.py
```

## Build And Run Commands

- Show runreeds options: `uv run python runreeds.py -h`
- Interactive run setup: `uv run python runreeds.py`
- Typical test batch: `uv run python runreeds.py -b vYYYYMMDD_label -c test`
- One or more named cases from a cases file:
  `uv run python runreeds.py -b vYYYYMMDD_label -c test -s caseA,caseB`
- Dry run case setup without launch: `uv run python runreeds.py -b label -c test -t`
- Check run status: `uv run python helpers/runstatus.py <batch_prefix>`
- Restart failed HPC runs: `uv run python helpers/restart_runs.py <batch_prefix>`
- Run a completed-case output check:
  `uv run python -m pytest tests/test_outputs.py --casepath runs/<case>`
- Build docs when docs dependencies are installed:
  `uv run sphinx-build docs/source docs/build/`

`runreeds.py` command-line arguments (from its argparse): `-b/--BatchName`,
`-c/--cases_suffix`, `-s/--single` (a single case or comma-delimited list),
`-r/--simult_runs`, `-l/--forcelocal`, `-f/--skip_checks`, `-d/--debug`,
`-n/--debugnode`, `-p/--cases_per_node`, `-t/--dryrun`.

Be conservative with full model runs. They can be long, need licensed GAMS, may
download large files, and write substantial data under `runs/`.

## Testing

- Lightweight Python IO tests:
  `uv run python -m pytest tests/test_read_h5_files.py`
- Hourlize tests:
  `uv run python -m pytest hourlize/tests`
- Completed-run output validation:
  `uv run python -m pytest tests/test_outputs.py --casepath runs/<case>`
- Julia ReEDS2PRAS tests from `reeds/resource_adequacy/reeds2pras/test/`:
  `julia --project runtests.jl`
- CI runs a test ReEDS scenario with `python runreeds.py -b "$batch" -c test -s "$SCENARIO"`
  (scenarios `github_Pacific`, `github_Everything`, `github_MA_county_CC`) and
  then validates outputs with `tests/test_outputs.py`. A later CI job exercises
  R2X translation via `postprocessing/run_r2x.py`.

`tests/test_outputs.py` is a completed-case artifact check, not a guarantee that
every bokehpivot report section rendered cleanly. For report health, inspect
`runs/<case>/outputs/reeds-report/report.log` and the generated HTML directly.

When changing GAMS objective-function inputs, check
`tests/objective_function_params.yaml`; it documents parameters that
`reeds/input_processing/check_inputs.py` validates for missing values.

## Architecture And Run Flow

1. A cases file is parsed by `reeds.inputs.parse_cases()`.
2. `runreeds.py` expands cases, checks switch consistency, and creates
   `runs/{BatchName}_{case}/`.
3. Case setup writes `inputs_case/`, `switches.csv`, `gswitches.csv`,
   `modeledyears.csv`, run metadata, and generated shell/batch scripts.
4. `reeds/input_processing/copy_files.py` and related scripts copy, filter,
   aggregate, and derive inputs. Many output CSV names intentionally match GAMS
   parameter names read by `reeds/core/setup/b_inputs.gms`.
5. GAMS assembles the model via `reeds/core/setup/a_createmodel.gms`, creates
   `inputs.gdx`, solves according to the chosen `timetype` (`seq` →
   `3_solve_oneyear.gms`, `int` → `3_solve_allyears.gms`, `win` →
   `3_solve_window.gms`, all under `reeds/core/solve/`), and writes GDX/CSV
   outputs.
6. `reeds/resource_adequacy/ra_calcs.py` may run between solve years to prepare
   PRAS data, run Julia PRAS (`run_pras.jl` + `reeds2pras/`), calculate capacity
   credit, and add stress periods.
7. `reeds/core/terminus/report.gms`, `report_dump.py`, bokehpivot, retail-rate,
   plots, Vizit, R2X, and other postprocessors write to `runs/{case}/outputs/`.

Useful run-folder files:

- `gamslog.txt`: first place to inspect failures; search for `ERROR`,
  `LP status`, `Status`, and `Cur_year`.
- `lstfiles/`: GAMS listing files. `1_Inputs.lst` catches input build errors;
  year-specific `.lst` files catch solve failures.
- `meta.csv`: process timing and repository metadata.
- `inputs_case/`: exact inputs seen by a case. This is usually better than
  guessing from repository defaults when debugging a completed run.
- `outputs/`: reported CSVs, figures, bokehpivot reports, retail outputs, etc.
- `handoff/reeds_data/`: resource-adequacy / capacity-credit intermediate data
  (GDX and CSV) passed between solve years.

## Code Style

Follow the current file's style first. This repository predates some current
guidelines, so nearby conventions matter.

Python:

- Prefer PEP 8 for new Python.
- Use `os.path.join()` or `pathlib` rather than hard-coded separators.
- Input-processing scripts should not change working directory; pass explicit
  paths such as `reeds_path` and `inputs_case`.
- Keep data transformations in Python when practical instead of adding complex
  calculations in GAMS.
- Use `reeds.io` helpers for reading outputs, switches, scalars, HDF5, maps, and
  case paths rather than duplicating parsing logic.
- Many scripts log through `reeds.log.makelog()` and append timings with
  `reeds.log.toc()`; keep that pattern for run-step scripts.
- Avoid broad formatting-only changes. The repo recommends Ruff linting, but
  does not yet enforce repo-wide autoformatting.

GAMS:

- Follow `docs/source/developer_best_practices.md`.
- New GAMS files use the category prefix convention, e.g. `d1_...`,
  `d2_...`, `e_...`.
- Switches are `GSw_...` in `cases.csv`; numeric GAMS versions usually become
  `Sw_...`. Off is `0`, on is `1`.
- Parameters are lowercase with underscores; variables are uppercase; equations
  are `eq_...`.
- GAMS declarations should include units first in comments, e.g. `"--MW-- ..."` .
- Prefer blocks of declarations over many one-line declarations.
- Use braces for GAMS functions such as `sum{...}`.
- In equations, terms generally start with `+` or `-`, parameters appear to the
  left of variables, and operators have surrounding spaces.
- Monetary values should be rounded to two decimal places; other plain-text
  parameters should generally use no more than three significant figures.
- Avoid hard-coded numbers in equations; name them as parameters when possible.

Inputs and CSVs:

- Files written to `inputs_case/` should generally share the GAMS parameter name
  that reads them.
- GAMS-readable CSV headers often start with `*` so GAMS treats the header as a
  comment.
- Raw inputs belong under topical `inputs/` subdirectories.
- Large or optional data should not be committed casually; use the remote-file
  mechanism and document sources in `sources.csv` / `sources_documentation.md`.
- Costs read into `reeds/core/setup/b_inputs.gms` should already be in 2004
  dollars unless the surrounding code clearly says otherwise; use `deflator.csv`
  rather than hard-coded conversions.

## Debugging Notes

- For run failures, start with `runs/<case>/gamslog.txt`, then the newest file
  in `runs/<case>/lstfiles/`.
- For input-processing failures, inspect `inputs_case/`, `1_Inputs.lst`, and
  the script call generated in `call_<case>.bat` or `call_<case>.sh`.
- For output/report failures, compare `outputs/`, `report_params.csv`, and
  `postprocessing/bokehpivot` report logs.
- When an expected output is missing, first check the effective run switches in
  `runs/<case>/inputs_case/switches.csv`; repository defaults in `cases.csv`
  may have been overridden by `cases_test.csv`, study cases, or the case column.
- Some report gaps are switch-driven and expected. For example, sequential
  `timetype=seq` runs do not produce `cap_iter`, and `land_use_analysis=0` skips
  `land_use_total.csv`.
- OpRes report failures can come from empty representative reserve periods:
  check `inputs_case/rep/opres_periods.csv`, `opRes_supply_h.csv`, `Sw_OpRes`,
  and the generated equation counts in `lstfiles/1_Inputs.lst` or solve `.lst`
  files before assuming `GSw_OpRes` itself is wrong.
- Current `health_damages_caused_r.csv` files use the air-quality postprocessor
  schema (`ba`, `pollutant`, `tons`, `md`, `damage_$`, `mortality`); bokehpivot
  normalizes this to legacy report display columns in `postprocessing/bokehpivot/reeds2.py`.
- `helpers/runstatus.py` summarizes running/failed/finished cases for a batch prefix.
- `postprocessing/check_error.py` reads the `error_check` output for solved
  cases.
- For GAMS data comparison, developer docs recommend targeted `execute unload`
  statements rather than broad dumps.
- Keep `cleanup_level` at `0` while developing or debugging, because higher
  cleanup levels remove files useful for restarts and diagnosis.

## Important Subsystems

- Remote data: `reeds.remote` reads `inputs/remote_files.csv` and manages
  downloads under `inputs/remote/`.
- Monte Carlo sampling: `reeds/input_processing/mcs_sampler.py` plus YAML
  distribution files described in the user guide.
- Temporal clustering and hourly data: `reeds/input_processing/hourly_repperiods.py`,
  `hourly_writetimeseries.py`, `hourly_load.py`, and `inputs_case/rep/`.
- Renewable capacity factors and resources: `reeds/input_processing/recf.py`,
  `writesupplycurves.py`, `hourlize/`, and `inputs_case/recf.h5`.
- Resource adequacy/stress periods: `reeds/resource_adequacy/` (`ra_calcs.py`,
  `capacity_credit.py`, `stress_periods.py`, `run_pras.jl`, `reeds2pras/`) and
  `GSw_PRM_*` switches.
- Standard reports: `reeds/core/terminus/report.gms`, `report_dump.py`,
  `postprocessing/bokehpivot/`, and `postprocessing/single_case_plots.py`.
- Run comparisons: `postprocessing/compare_cases.py`,
  `postprocessing/combine_runs/`, and `postprocessing/uncertainty_plots.py`.
- Retail rates: `postprocessing/retail_rate_module/`.
- R2X translation: `postprocessing/run_r2x.py` and CI's `r2x-reeds` invocation.

## Security And Data Handling

- Never commit secrets, credentials, GAMS license files, local machine paths that
  should remain private, or API tokens.
- Be careful with generated run folders. They may contain large files, local
  paths, logs, and intermediate model data.
- Do not delete, move, or overwrite run artifacts unless explicitly asked.
- Ask before downloading large remote inputs or launching long solves.
- Preserve source documentation when adding or changing data: update
  `sources.csv`, `sources_documentation.md`, and relevant docs when applicable.

## Git Workflow For Agents

- Expect a dirty worktree. Check `git status --short` before edits and preserve
  user changes.
- Keep edits scoped to the user's request. Do not reformat unrelated files.
- Prefer small, reviewable changes with targeted tests or validation commands.
- Before claiming a model change is safe, state what was and was not run. A
  Python unit test is not a substitute for a GAMS solve when model behavior is
  changed.
- Do not use destructive git commands or delete generated data unless the user
  asks for that specific action.

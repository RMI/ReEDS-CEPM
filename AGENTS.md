# ReEDS Agent Guide

ReEDS is a capacity planning and dispatch model for the U.S. electricity system.
The repository is a mixed Python, GAMS, and Julia codebase: Python prepares inputs,
orchestrates runs, and postprocesses outputs; GAMS contains the optimization model;
Julia translates solved ReEDS systems into PRAS resource adequacy systems.

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

- `runbatch.py`: main run orchestrator. Reads `cases*.csv`, creates
  `runs/{BatchName}_{case}/`, writes scripts, copies needed code/data into the
  case folder, and launches local, HPC, or AWS runs.
- `cases.csv`: canonical case/switch catalog, with descriptions, allowed values,
  and defaults. Scenario files such as `cases_test.csv`, `cases_small.csv`, and
  study-specific `cases_{suffix}.csv` override defaults by case column.
- `runfiles.csv`: inventory of input files and how they should be copied,
  filtered, aggregated, or transformed into each run's `inputs_case/`.
- Root `*.gms`: core GAMS model files. Important stages include `b_inputs.gms`
  for GAMS-readable inputs, `c_supplymodel.gms` and `c_supplyobjective.gms` for
  model equations/objective, `d_solveprep.gms`, `d_solveoneyear.gms`,
  `d_solveallyears.gms`, `d_solvewindow.gms`, and `e_report.gms`.
- `input_processing/`: scripts run during case setup to create files under
  `runs/{case}/inputs_case/`. `copy_files.py` is the broad data copier/filter;
  scripts such as `recf.py`, `hourly_repperiods.py`, `hourly_load.py`,
  `writecapdat.py`, `plantcostprep.py`, and `transmission.py` derive key inputs.
- `reeds/`: shared Python utilities. Common entry points are `reeds.io`,
  `reeds.inputs`, `reeds.spatial`, `reeds.techs`, `reeds.log`,
  `reeds.output_calc`, and plotting modules.
- `ReEDS_Augur/` and `Augur.py`: capacity credit, PRAS, and stress-period logic
  that runs between solve years when enabled.
- `reeds2pras/`: Julia package for translating ReEDS outputs to PRAS systems.
- `hourlize/`: preprocessing for resource and load profiles. Main wrapper is
  `hourlize/run_hourlize.py`; `hourlize/reeds_to_rev.py` disaggregates ReEDS
  investments back to reV supply curve sites.
- `postprocessing/`: reports, diagnostics, plots, run comparison, retail rates,
  reValue, bokehpivot, Tableau, combine-runs, and output cleanup.
- `preprocessing/`: tools for preparing repository inputs before ReEDS runs.
- `inputs/`: checked-in model inputs plus pointers to large remote inputs.
  Large files are normally downloaded into `inputs/remote/` and linked or copied
  as needed.
- `runs/`: generated run folders. Treat contents as user/generated artifacts and
  do not edit or delete them unless the task explicitly targets a run.
- `tests/` and `hourlize/tests/`: pytest tests. Some tests are lightweight unit
  tests; `tests/test_outputs.py` requires a completed ReEDS case.
- `.github/workflows/`: CI, docs, and workflow-quality automation.

## Environment

- Python is pinned to `3.11` via `.python-version` and `pyproject.toml`.
- Python dependencies are managed with `uv` and locked in `uv.lock`.
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

- Show runbatch options: `uv run python runbatch.py -h`
- Interactive run setup: `uv run python runbatch.py`
- Typical test batch: `uv run python runbatch.py -b vYYYYMMDD_label -c test`
- One or more named cases from a cases file:
  `uv run python runbatch.py -b vYYYYMMDD_label -c test -s caseA,caseB`
- Dry run case setup without launch: `uv run python runbatch.py -b label -c test -t`
- Check run status: `uv run python runstatus.py <batch_prefix>`
- Restart failed HPC runs: `uv run python restart_runs.py <batch_prefix>`
- Run a completed-case output check:
  `uv run python -m pytest tests/test_outputs.py --casepath runs/<case>`
- Build docs when docs dependencies are installed:
  `uv run sphinx-build docs/source docs/build/`

Be conservative with full model runs. They can be long, need licensed GAMS, may
download large files, and write substantial data under `runs/`.

## Testing

- Lightweight Python IO tests:
  `uv run python -m pytest tests/test_read_h5_files.py`
- Hourlize tests:
  `uv run python -m pytest hourlize/tests`
- Completed-run output validation:
  `uv run python -m pytest tests/test_outputs.py --casepath runs/<case>`
- Julia ReEDS2PRAS tests from `reeds2pras/test/`:
  `julia --project runtests.jl`
- CI runs a test ReEDS scenario with `python runbatch.py -b "$batch" -c test -s "$SCENARIO"`
  and then validates outputs with `tests/test_outputs.py`.

`tests/test_outputs.py` is a completed-case artifact check, not a guarantee that
every bokehpivot report section rendered cleanly. For report health, inspect
`runs/<case>/outputs/reeds-report/report.log` and the generated HTML directly.

When changing GAMS objective-function inputs, check
`tests/objective_function_params.yaml`; it documents parameters that
`input_processing/check_inputs.py` validates for missing values.

## Architecture And Run Flow

1. A cases file is parsed by `reeds.inputs.parse_cases()`.
2. `runbatch.py` expands cases, checks switch consistency, and creates
   `runs/{BatchName}_{case}/`.
3. Case setup writes `inputs_case/`, `switches.csv`, `gswitches.csv`,
   `modeledyears.csv`, run metadata, and generated shell/batch scripts.
4. `input_processing/copy_files.py` and related scripts copy, filter, aggregate,
   and derive inputs. Many output CSV names intentionally match GAMS parameter
   names read by `b_inputs.gms`.
5. GAMS reads `b_inputs.gms`, creates `inputs.gdx`, solves according to the
   chosen `timetype` (`seq`, `int`, or `win`), and writes GDX/CSV outputs.
6. `Augur.py` may run between solve years to prepare PRAS data, run Julia PRAS,
   calculate capacity credit, and add stress periods.
7. `e_report.gms`, `e_report_dump.py`, bokehpivot, retail-rate, plots, Vizit,
   R2X, and other postprocessors write to `runs/{case}/outputs/`.

Useful run-folder files:

- `gamslog.txt`: first place to inspect failures; search for `ERROR`,
  `LP status`, `Status`, and `Cur_year`.
- `lstfiles/`: GAMS listing files. `1_Inputs.lst` catches input build errors;
  year-specific `.lst` files catch solve failures.
- `meta.csv`: process timing and repository metadata.
- `inputs_case/`: exact inputs seen by a case. This is usually better than
  guessing from repository defaults when debugging a completed run.
- `outputs/`: reported CSVs, figures, bokehpivot reports, retail outputs, etc.
- `ReEDS_Augur/augur_data/`: PRAS and capacity-credit intermediate data.

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
- Costs read into `b_inputs.gms` should already be in 2004 dollars unless the
  surrounding code clearly says otherwise; use `deflator.csv` rather than
  hard-coded conversions.

## Debugging Notes

- For run failures, start with `runs/<case>/gamslog.txt`, then the newest file
  in `runs/<case>/lstfiles/`.
- For input-processing failures, inspect `inputs_case/`, `1_Inputs.lst`, and
  the script call generated in `call_<case>.bat` or `call_<case>.sh`.
- For output/report failures, compare `outputs/`, `e_report_params.csv`, and
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
- `runstatus.py` summarizes running/failed/finished cases for a batch prefix.
- `postprocessing/check_error.py` reads the `error_check` output for solved
  cases.
- For GAMS data comparison, developer docs recommend targeted `execute unload`
  statements rather than broad dumps.
- Keep `cleanup_level` at `0` while developing or debugging, because higher
  cleanup levels remove files useful for restarts and diagnosis.

## Important Subsystems

- Remote data: `reeds.remote` reads `inputs/remote_files.csv` and manages
  downloads under `inputs/remote/`.
- Monte Carlo sampling: `input_processing/mcs_sampler.py` plus YAML
  distribution files described in the user guide.
- Temporal clustering and hourly data: `input_processing/hourly_repperiods.py`,
  `hourly_writetimeseries.py`, `hourly_load.py`, and `inputs_case/rep/`.
- Renewable capacity factors and resources: `input_processing/recf.py`,
  `writesupplycurves.py`, `hourlize/`, and `inputs_case/recf.h5`.
- Resource adequacy/stress periods: `Augur.py`, `ReEDS_Augur/`,
  `reeds2pras/`, and `GSw_PRM_*` switches.
- Standard reports: `e_report.gms`, `e_report_dump.py`,
  `postprocessing/bokehpivot/`, and `postprocessing/single_case_plots.py`.
- Run comparisons: `postprocessing/compare_cases.py`,
  `postprocessing/combine_runs/`, and `postprocessing/uncertainty_plots.py`.
- Retail rates: `postprocessing/retail_rate_module/`.
- R2X translation: `scripts/run_r2x.py` and CI's `r2x-reeds` invocation.

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

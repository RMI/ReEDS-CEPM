# Testing ReEDS

This document collects the testing guidance that is currently spread across the
developer guide, PR template, CI workflows, and subsystem READMEs.

Primary references:

- `docs/source/developer_best_practices.md`, especially "Testing Guidelines"
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/python-app.yaml`
- `reeds2pras/README.md`
- `AGENT.md`

## Prerequisites

Most lightweight Python tests only need the Python environment. Model runs need
the full ReEDS stack.

- Python `3.11`
- `uv` for Python environment management
- GAMS on `PATH`, with an appropriate license and solver
- Julia `1.12.1` for ReEDS2PRAS, PRAS, and stress-period workflows
- Remote test data downloaded or available when running model cases that need it

Typical local setup:

```powershell
uv sync --extra dev
julia --project=. instantiate.jl
$env:CONDA_DEFAULT_ENV = "reeds2"
$env:CONDA_PREFIX = (Resolve-Path .venv).Path
```

Optional remote-data preload:

```powershell
uv run python reeds/remote.py
```

## Quick Checks

Run these when the change is Python-only and does not require a model solve:

```powershell
uv run python -m pytest tests/test_read_h5_files.py
uv run python -m pytest hourlize/tests
```

Run ReEDS2PRAS tests when changing `reeds2pras/`, `ReEDS_Augur/`, PRAS-related
inputs, or stress-period/resource-adequacy code:

```powershell
cd reeds2pras/test
julia --project runtests.jl
cd ../..
```

Build docs when changing documentation or doc configuration:

```powershell
uv run sphinx-build docs/source docs/build/
```

## Model Run Tests

The main model test path is to run one or more scenarios from `cases_test.csv`
and then validate the completed run folder.

Show runbatch options:

```powershell
uv run python runbatch.py -h
```

Run all non-ignored scenarios in `cases_test.csv`:

```powershell
uv run python runbatch.py -b vYYYYMMDD_test -c test
```

Run selected scenarios:

```powershell
uv run python runbatch.py -b vYYYYMMDD_test -c test -s USA_defaults
uv run python runbatch.py -b vYYYYMMDD_test -c test -s USA_defaults,USA_decarb
```

Validate outputs for a completed case:

```powershell
uv run python -m pytest tests/test_outputs.py --casepath runs/vYYYYMMDD_test_USA_defaults
```

`tests/test_outputs.py` checks that expected reported CSVs, bokehpivot reports,
retail outputs, and selected figures exist in the completed case's `outputs/`
folder. It is not a substitute for reviewing whether model results changed in
the expected way.

This output validation is aimed at standard `cases_test.csv` workflows. Very
small or custom smoke-test cases, such as runs based on `cases_small.csv`, can
solve successfully while still missing full-report deliverables. In that case,
`tests/test_outputs.py` may fail because a standard postprocessor did not write
one of its expected files, not because the GAMS solve failed or because model
results differ from a baseline.

When using a small smoke test, distinguish three outcomes:

- The model solve failed: inspect `gamslog.txt` and `lstfiles/` first.
- The solve completed but postprocessing failed: outputs exist, but report,
  retail, plotting, R2X, or other postprocessor files may be missing.
- The solve and postprocessing completed enough for the intended smoke test, but
  `tests/test_outputs.py` still fails because it expects standard-case
  deliverables that the small case does not produce.

## Change-Based Guidance

Use the smallest test that gives real confidence. For model behavior changes,
that usually means at least one solved ReEDS case plus comparison outputs.

### Post-Process Test

Use for changes that do not affect model code or data, such as report styling,
plotting changes, or helper scripts like `runstatus.py`.

- Run the changed post-processing workflow on outputs from a recent main-branch
  run.
- Include a short demonstration or output artifact in the PR.
- Verify GitHub runner tests pass.

### Light Test

Use for model-code changes that are not expected to meaningfully affect model
solutions, such as rounding an input parameter, improving runtime without
changing logic, changing code behind a default-off switch, or adding a missing
`runfiles.csv` entry.

- Compare a default test case from `cases_test.csv` against an equivalent run
  from main.
- Produce and review a comparison report.
- Verify GitHub runner tests pass.

### Regular Test

Use for most model or data changes.

- Run and compare either `USA_defaults` or `Mid_Case`, plus `USA_decarb`, from
  `cases_test.csv` against equivalent runs from main.
- Review capacity, generation, transmission capacity, bulk system electricity
  price, system cost, and runtime.
- Include the comparison report in the PR.
- Verify GitHub runner tests pass.

The developer guide notes that `USA_defaults` should be run for most PRs. When
the right level is unclear, prefer the regular test or ask reviewers.

### New Version Test

Use for tagged releases.

- Run the full set of scenarios in `cases_test.csv`.
- Note any failing cases in release notes.
- Create issues for output-processing failures and mention them in release
  notes.
- Create comparison reports for the USA scenario against the previous released
  version and attach them to release notes.

## CI Reference

The main CI workflow does the following:

- Sets up Python, GAMS, and Julia environments.
- Downloads or restores required remote/Zenodo test files.
- Runs:

```bash
python runbatch.py -b "$batch" -c test -s "$SCENARIO"
python -m pytest tests/test_outputs.py --casepath "$GITHUB_WORKSPACE/runs/${batch}_${SCENARIO}"
```

- Uploads failure diagnostics such as `gamslog.txt`, listing files, outputs, and
  case inputs.
- Runs R2X conversion for selected completed runs using `r2x-reeds`.

Workflow-quality CI also runs `zizmor` and `actionlint` on GitHub Actions files.

## Comparison Reports

The PR template asks for comparison reports commensurate with the change:

- No model or data changes: Pacific test case only.
- Model or data changes: full U.S. reference case and full U.S. decarb case.
- Model structure, spatial/temporal resolution, or other large changes: all
  cases in `cases_test.csv`.

`postprocessing/compare_cases.py` is the main comparison-report script. Include
additional plots when they help explain input data, methods, or expected output
differences.

## Debugging Failed Tests

For failed model runs, inspect the case folder first:

- `runs/<case>/gamslog.txt`: search for `ERROR`, `LP status`, `Status`, and
  `Cur_year`.
- `runs/<case>/lstfiles/`: inspect `1_Inputs.lst` for input build failures and
  year-specific `.lst` files for solve failures.
- `runs/<case>/inputs_case/`: exact inputs seen by the model.
- `runs/<case>/meta.csv`: process timing and repo metadata.
- `runs/<case>/outputs/`: reported outputs and generated reports.
- `runs/<case>/ReEDS_Augur/augur_data/`: PRAS and capacity-credit intermediate
  files.
- `runs/<case>/outputs/reeds-report/report.log`: bokehpivot report build log.
  The report builder intentionally catches individual section failures, marks
  them as red `ERROR!` sections in `report.html`, logs the traceback, and
  continues building later sections. This lets a report be partially useful, but
  a standard validation report should still be checked for unexpected failed
  sections.

Useful commands:

```powershell
uv run python runstatus.py <batch_prefix>
uv run python postprocessing/check_error.py runs/<case>
```

Keep `cleanup_level` at `0` while developing or debugging so run folders retain
the files needed for diagnosis and restarts.

## Adding Tests

- Prefer focused Python tests for reusable utility behavior in `reeds/`,
  `hourlize/`, and input/post-processing modules.
- Add or update `tests/objective_function_params.yaml` when adding general
  objective-function parameters that should be checked for missing input values.
- For ReEDS2PRAS, add new Julia test files under `reeds2pras/test/` named
  `test-*.jl`; `runtests.jl` automatically includes matching files.
- For model behavior changes, document the run scenarios and comparison results
  even when unit tests are also added.

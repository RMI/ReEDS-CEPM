# Internal CI Test Runbook (On-Prem, GAMS-Licensed)

This runbook reproduces the key checks from GitHub PR CI on an internal machine where a host-specific GAMS license is valid.

## Scope

This process is intended to replace CI jobs that currently fail on GitHub-hosted runners due to GAMS license constraints:

- `run ReEDS model matrix` (all scenario matrix entries)
- `run R2X compatibility matrix` (all scenario matrix entries)

It follows the same scenario set used in PR CI:

- `github_Pacific` (solve year 2029)
- `github_Everything` (solve year 2060)
- `github_MA_county_CC` (solve year 2026)

---

## Prerequisites

- Access to a licensed on-prem machine/VM where GAMS is valid.
- Repository checked out locally.
- Git LFS installed.
- Python environment matching project requirements.
- Julia installed if required by your local environment process.
- Network access to fetch Zenodo test files.

---

## 1) Sync code and LFS assets

```bash
git fetch --all --prune
git checkout <branch-under-test>
git pull
git lfs pull
```

---

## 2) Prepare environment

Set up the project Python/Julia environment according to internal standards (mirroring `.github/actions/setup-reeds-env` behavior as closely as practical).

Confirm GAMS is available and licensed in this environment.

Optional CI-parity variable:

```bash
export batch=test
```

---

## 3) Fetch Zenodo test inputs

Run the same script used by CI:

```bash
python .github/scripts/download_test_zenodo_files.py
```

Expected directories include:

- `inputs/remote/`
- `inputs/profiles_cf/`
- `inputs/profiles_demand/`
- `inputs/profiles_dr/`
- `inputs/profiles_temperature/`

---

## 4) Run ReEDS model matrix scenarios

Run each scenario exactly as CI does:

```bash
python runbatch.py -b test -c test -s github_Pacific
python runbatch.py -b test -c test -s github_Everything
python runbatch.py -b test -c test -s github_MA_county_CC
```

Run folders should be created at:

- `runs/test_github_Pacific`
- `runs/test_github_Everything`
- `runs/test_github_MA_county_CC`

---

## 5) Validate ReEDS outputs (same pytest check as CI)

```bash
python -m pytest tests/test_outputs.py --casepath "$PWD/runs/test_github_Pacific"
python -m pytest tests/test_outputs.py --casepath "$PWD/runs/test_github_Everything"
python -m pytest tests/test_outputs.py --casepath "$PWD/runs/test_github_MA_county_CC"
```

---

## 6) Apply CI-equivalent failure checks

CI treats missing `cap_ivrt.csv` as run failure. Verify for each scenario:

- `runs/test_<SCENARIO>/outputs/cap_ivrt.csv`

Also inspect diagnostics if needed:

- `runs/test_<SCENARIO>/gamslog.txt`
- `runs/test_<SCENARIO>/meta.csv`
- `runs/test_<SCENARIO>/lstfiles/`

---

## 7) Run R2X compatibility checks (optional but recommended parity)

CI executes `scripts/run_r2x.py` for each scenario. Reproduce locally after successful ReEDS runs.

If using `uvx` as in CI:

```bash
uvx --from "r2x-reeds>=0.3.5" python scripts/run_r2x.py \
  --reeds-run-path "github_Pacific-2029" \
  --scenario "github_Pacific" \
  --solve-year "2029" \
  --weather-year "2012" \
  --system-json "github_Pacific_system.json"
```

Repeat with:
- `github_Everything`, `2060`
- `github_MA_county_CC`, `2026`

> Note: Align `--reeds-run-path` to your local folder layout if different from CI artifact layout.

---

## 8) Record results for PR review

For each scenario, capture:

- ReEDS run status (pass/fail)
- `pytest tests/test_outputs.py` status
- R2X status (if run)
- Any relevant log excerpts (`gamslog.txt`, pytest failures)

Suggested summary table:

| Scenario | ReEDS Run | Output Pytest | R2X | Notes |
|---|---|---|---|---|
| github_Pacific |  |  |  |  |
| github_Everything |  |  |  |  |
| github_MA_county_CC |  |  |  |  |

---

## Troubleshooting

- **License errors**: verify GAMS license installation and environment pathing.
- **Missing input data**: rerun Zenodo download script and confirm folder contents.
- **LFS-related failures**: rerun `git lfs pull`.
- **Pytest output failures**: inspect run folder outputs and compare against expected test assumptions.

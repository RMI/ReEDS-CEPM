# ReEDS

**Regional Energy Deployment System (ReEDS) Model**

[![CI](https://github.com/ReEDS-Model/ReEDS/actions/workflows/python-app.yaml/badge.svg?branch=main)](https://github.com/ReEDS-Model/ReEDS/actions/workflows/python-app.yaml)
[![Documentation](https://img.shields.io/badge/Documentation-view%20online-0a7f5e?logo=readthedocs&logoColor=white&labelColor=555)](https://reeds-model.github.io/ReEDS)
![Static Badge](https://img.shields.io/badge/python-3.11-blue)
![GitHub License](https://img.shields.io/github/license/ReEDS-Model/ReEDS)
[![DOI](https://zenodo.org/badge/189060033.svg)](https://doi.org/10.5281/zenodo.16943302)

**Needs review:** this repo was recently rebased onto a restructured upstream
ReEDS base, and this README has not yet been fully verified against it. Known
stale reference: instructions below say `runbatch.py`, which has been renamed
to `runreeds.py` upstream. Treat setup/run instructions as unverified pending
review. Flagging for follow-up via issue/comment.

This GitHub repository contains the source code for NLR's ReEDS model.

The ReEDS model source code is available at no cost from the National Laboratory of the Rockies.

The ReEDS model can be downloaded or cloned from [https://github.com/ReEDS-Model/ReEDS](https://github.com/ReEDS-Model/ReEDS).

If you want to use the latest stable version of ReEDS, download or check out the latest stable release [here](https://github.com/ReEDS-Model/ReEDS/releases/latest).

**For more information about the model, see the [ReEDS Documentation](https://reeds-model.github.io/ReEDS).**

ReEDS training videos are available on the [NLR Learning YouTube channel](https://youtube.com/playlist?list=PLmIn8Hncs7bG558qNlmz2QbKhsv7QCKiC&si=NgGBaL_MxNcYiIEX).

## Introduction

[ReEDS](https://www.nlr.gov/analysis/reeds/) is a capacity planning and dispatch model for the U.S. electricity system.

As NLR's flagship long-term power sector model, ReEDS has served as the primary analytic tool for [many studies](https://reeds-model.github.io/ReEDS/publications.html) of electricity sector research questions.

Example model results are available in the [Scenario Viewer](https://scenarioviewer.nlr.gov/).

## Quick-start guide

The ReEDS model is written in [Python](https://www.python.org/), [GAMS](https://www.gams.com/), and [Julia](https://julialang.org/).

Python and Julia are free, open-source languages.

GAMS requires a software license from the vendor.

A step-by-step guide for getting started with ReEDS is available [here](https://reeds-model.github.io/ReEDS/setup.html), and a quick-start guide for advanced users is outlined below.

### 1. Install UV and Python

Install UV:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal, then install Python 3.11:

```bash
uv python install 3.11
```

### 2. Set up GAMS

1. Install GAMS: <https://www.gams.com/download/>
2. Obtain a combined GAMS/CPLEX license: <https://www.gams.com/sales/licensing/>

Small ReEDS systems have been solved using the open-source [COIN-OR](https://www.coin-or.org/) solver as described [here](https://www.nlr.gov/docs/fy21osti/77907.pdf), but this capability is not actively maintained.

Other commercial solvers have also been successfully applied to ReEDS, but setup details and some solver tuning are specific to the CPLEX solver.

Ensure the `gams` executable is available on your PATH:

```bash
gams
```

GAMS typically installs directly into the top level directory, with a version number. A typical way to add gams to your user PATH variable in powershell is:

```bash
$currentPath = [Environment]::GetEnvironmentVariable("Path","User") #This gets the PATH Environment variable at the user scope
$addPath = 'C:/GAMS/53' # or wherever your gams install is
[Environment]::SetEnvironmentVariable("Path","$addPath;$currentPath","User")
```

### 3. Install Julia

Install Julia using `juliaup`:

```bash
curl -fsSL https://install.julialang.org | sh
```

Install the required Julia version:

```bash
juliaup add 1.12.1
juliaup default 1.12.1
```

Verify:

```bash
julia --version
```

### 4. Set up the ReEDS environment

Clone the repository:

```bash
git clone https://github.com/ReEDS-Model/ReEDS.git
cd ReEDS
```

Pin Python 3.11 for the project:

```bash
uv python pin 3.11
```

Create the UV-managed Python environment:

```bash
uv sync --extra dev
```

Instantiate the Julia environment:

```bash
julia --project=. instantiate.jl
```

Link large data files from shared folder, so we each don't store separate instances of this ~95GB of input data. Note you cannot do this in git bash as 
there are some type of strange permission issues, so use powershell:

```powershell
New-Item -ItemType Junction -Path ".inputs\remote" -Target "C:\Users\Public\Documents\reeds_data\remote"
```

Several large data files are hosted remotely. These files are downloaded automatically as needed during a ReEDS run, but the command above finishes all internet-requiring steps up front.

Additional details on remote files and other topics can be found in the [user guide](https://reeds-model.github.io/ReEDS/user_guide.html#large-input-files).

### 4.5 Optional PowerShell bootstrap command

Once you've cloned the repository, you can use an optional PowerShell bootstrap helper to 
ensure supporting software is up to date and then immediately run runbatch.py:

```powershell
.\bootstrap_reeds.ps1
```

This script performs the following steps in order:
1. Verifies GAMS is on PATH, checks GAMS license status, and prints a detected version string.
2. Verifies Julia is on PATH and checks that the version is `1.12.1`.
3. Sets ReEDS environment variables for the current PowerShell session.
4. Checks that Python is pinned to 3.11 and runs `uv python pin 3.11` if needed.
5. Runs `uv sync --extra dev`.
6. Runs `julia --project=. instantiate.jl`.
7. Forwards all arguments to `runbatch.py`.

Passing `-y` (or `--skip-setup` / `--bypass`) skips Step 5 (`uv sync --extra dev`) and Step 6 (`julia --project=. instantiate.jl`).
All other checks and setup steps still run, and remaining arguments are still passed to `runbatch.py`

```powershell
.\bootstrap_reeds.ps1 -y -b v20250314_main -c test
.\bootstrap_reeds.ps1 --bypass -b v20250314_main -c test
```

### 5. Run ReEDS

ReEDS currently expects Conda-style environment variables. When using UV, set these variables before running ReEDS or ideally in your dotenv file, so you don't ahve to do this before every run.

```bash
export CONDA_DEFAULT_ENV=reeds2
export CONDA_PREFIX="$PWD/.venv"
```

For interactive setup:

```bash
uv run python runbatch.py
```

For one-line operation:

```bash
uv run python runbatch.py -b v20250314_main -c test
```

In this example, `v20250314_main` is the prefix for this batch of cases, and `test` is the suffix of the cases file, in this case `cases_test.csv`, located in the root of the repository. For the batch prefix, we should follow the convention `vYYYYMMDD_`, and note that the case ID from the cases file will be appended to the batch prefix for file naming purposes. Our cases are stored in the `cases_cepm.csv` file.

Run the following for information on other optional command-line arguments:

```bash
uv run python runbatch.py -h
```

PowerShell users can run setup + launch in one command with the bootstrap helper:

```powershell
.\bootstrap_reeds.ps1 -b v20250314_main -c test
```

## Troubleshooting

### GAMS is not found

Confirm that GAMS is available on your PATH:

```bash
gams
```

If this fails, update your shell PATH to include the GAMS installation directory.

### Julia setup fails

Re-run:

```bash
julia --project=. instantiate.jl
```

### Python environment issues

Recreate the UV environment:

```bash
rm -rf .venv uv.lock
uv sync --extra dev
```

### `CONDA_DEFAULT_ENV` error

When running with UV, set:

```bash
export CONDA_DEFAULT_ENV=reeds2
export CONDA_PREFIX="$PWD/.venv"
```

Then rerun the command with `uv run`.

## Contact Us

If you have comments and/or questions, contact the ReEDS team at [ReEDS.Inquiries@nlr.gov](mailto:ReEDS.Inquiries@nlr.gov) or post a question on the [discussion pages](https://github.com/ReEDS-Model/ReEDS/discussions).

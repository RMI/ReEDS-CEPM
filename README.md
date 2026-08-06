# ReEDS for CEPM

**NLR's Regional Energy Deployment System (ReEDS) Model, used for RMI's Clean Energy Portfolio Model**

<!--
The below are links and buttons that were created by the NLR team for their ReEDS repo -- we should re-design these before including them in our Readme.
[![CI](https://github.com/ReEDS-Model/ReEDS/actions/workflows/python-app.yaml/badge.svg?branch=main)](https://github.com/ReEDS-Model/ReEDS/actions/workflows/python-app.yaml)
[![Documentation](https://img.shields.io/badge/Documentation-view%20online-0a7f5e?logo=readthedocs&logoColor=white&labelColor=555)](https://reeds-model.github.io/ReEDS)
![Static Badge](https://img.shields.io/badge/python-3.11-blue)
![GitHub License](https://img.shields.io/github/license/ReEDS-Model/ReEDS)
[![DOI](https://zenodo.org/badge/189060033.svg)](https://doi.org/10.5281/zenodo.16943302)
-->

This GitHub repository contains the source code for a modified version of the National Laboratory of the Rockies' Regional Energy Deployment (ReEDS) model, customized for use for RMI's Clean Energy Portfolio Model (CEPM).

The ReEDS model source code is available at no cost from the National Laboratory of the Rockies. It can be downloaded or cloned from [https://github.com/ReEDS-Model/ReEDS](https://github.com/ReEDS-Model/ReEDS).

**For more information about NLR's ReEDS model, see their [ReEDS Documentation](https://reeds-model.github.io/ReEDS).**

## Introduction

[ReEDS](https://www.nlr.gov/analysis/reeds/) is a capacity planning and dispatch model for the U.S. electricity system.

As NLR's flagship long-term power sector model, ReEDS has served as the primary analytic tool for [many studies](https://reeds-model.github.io/ReEDS/publications.html) of electricity sector research questions.

Example model results are available in the [Scenario Viewer](https://scenarioviewer.nlr.gov/).

## The Clean Energy Portfolio Model and key differences with ReEDS.

RMI's Clean Energy Portfolio Model modifies NLR's ReEDS model, starting with its June 2026 release. 

CEPM is designed to answer the question "What's the most cost-effective way to serve the next increment of data center load across the United States?" We use a modified version of NLR's ReEDS model. A few of the key differnces are:

* Python package management in UV, instead of conda
* Some additional scripts to automate resolving the environment and running the model
* Customized cases_*.csv files that reflect CEPM scenarios.
* Additional minor changes throughout.

## Getting Started

The ReEDS model is written in [Python](https://www.python.org/), [GAMS](https://www.gams.com/), and [Julia](https://julialang.org/).

Python and Julia are free, open-source languages.

GAMS requires a software license from the vendor.

A step-by-step guide for getting started with ReEDS from NLR is available [here](https://reeds-model.github.io/ReEDS/setup.html).

## Quick-start guide for CEPM

We provide a guide for installing ReEDS' component software and resolving an operating environment for running ReEDS below.



### 1. Install UV and Python

Install UV:

For Mac or linux users, or users using Git Bash:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For Windows users, use:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal, then install Python 3.11:

```bash
uv python install 3.11
```

### 2. Set up GAMS

NOTE: If you're working on a shared virtual machine, GAMS may already be installed with a license. If it's a Windows shared machine, check C:/GAMS for an existing install. You can test whether gams is already installed by entering 'gams' into the terminal as described below.

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

Follow instructions for installing Julia on your machine from <https://julialang.org/downloads/>.

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

Navigate in terminal to the folder where you want to install ReEDS, then clone this repository:

```bash
git clone https://github.com/RMI/ReEDS-CEPM.git
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

### 5. Install large input files
Several large data files are hosted remotely. These files are downloaded automatically as needed during a ReEDS run, but the command above finishes all internet-requiring steps up front.

Additional details on remote files and other topics can be found in the [user guide](https://reeds-model.github.io/ReEDS/user_guide.html#large-input-files).

For CEPM, we link large data files from shared folder, so each user doesn't store separate instances of this ~95GB of input data. Note you cannot do this in git bash as there are some type of strange permission issues, so use powershell:

NOTE: This step may have already been completed if you're setting up a new user on an existing virtual machine.

```powershell
New-Item -ItemType Junction -Path ".\inputs\remote" -Target "C:\Users\Public\Documents\reeds_data\remote"
```

### 6. Set Powershell runtime environment
ReEDS currently expects Conda-style environment variables in order to sun successfully. When using UV, each instance of powershell will need to set these variables before running ReEDS. You can enter the below commands into the terminal before running ReEDS, set personal or VS Code workspace-level .env files, or use the below helper script to set these variables.

```bash
export CONDA_DEFAULT_ENV=reeds2
export CONDA_PREFIX="$PWD/.venv"
```

### 6.5 Optional PowerShell setup-and-run command (`run_cepm.ps1`)

Once you've cloned the repository, you can use the optional PowerShell helper `run_cepm.ps1` to 
ensure supporting software is up to date and then immediately run runreeds.py:

```powershell
.\run_cepm.ps1
```

This script performs the following steps in order:
1. Verifies GAMS is on PATH, checks GAMS license status, and prints a detected version string.
2. Verifies Julia is on PATH and checks that the version is `1.12.1`.
3. Sets ReEDS environment variables for the current PowerShell session.
4. Checks that Python is pinned to 3.11 and runs `uv python pin 3.11` if needed.
5. Runs `uv sync --extra dev`.
6. Instantiates Julia dependencies only when needed: a fast offline check (`Pkg.instantiate` without a registry update) skips the work when the environment is already current, and only falls back to the full `julia --project=. instantiate.jl` (which updates the registry) if dependencies changed or are missing.
7. Checks `environment.yml` against `pyproject.toml` and prints a non-fatal warning if they have drifted beyond the known-accepted allowlist (see `CEPM/UV_MAMBA_GUIDE.md`).
8. Forwards all arguments to `runreeds.py`.
9. Sends a best-effort [ntfy.sh](https://ntfy.sh) notification (topic `rmi-cepm-run-batch-finished`) before `runreeds.py` is launched and once it returns (on fail or success), so you can be alerted when a long-running batch finishes. Subscribe to the topic in the ntfy app or at <https://ntfy.sh/rmi-cepm-run-batch-finished>. A failed or offline notification is ignored. A failed or offline notification is ignored. Note: ntfy.sh topics are public; avoid including sensitive information in notifications.

Passing `-y` (or `--skip-setup` / `--bypass`) skips Step 5 (`uv sync --extra dev`) and Step 6 (Julia instantiation).
All other checks and setup steps still run, and remaining arguments are still passed to `runreeds.py`

Two more bootstrap-only options: `-q` (or `--quiet`) disables the ntfy.sh notifications, and `-u <name>` (or `--user <name>`) includes `<name>` as the username in the notification messages (omitted when not given). All other arguments are forwarded to `runreeds.py`.

```powershell
.\run_cepm.ps1 -y -b v20250314_main -c test
.\run_cepm.ps1 --bypass -b v20250314_main -c test
```

### 6. Run ReEDS



For interactive setup:

```bash
uv run python runreeds.py
```

For one-line operation:

```bash
uv run python runreeds.py -b v20260605 -c cepm
```

In this example, `v20260605` is the prefix for this batch of cases, and `cepm` is the suffix of the cases file, in this case `cases_cepm.csv`, located in the root of the repository. For the batch prefix, we should follow the convention `vYYYYMMDD`, and note that the case ID from the cases file will be appended to the batch prefix for file naming purposes (e.g., `WECC_county_100by2050`).

Run the following for information on other optional command-line arguments:

```bash
uv run python runreeds.py -h
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

# Data Center Load Forecast (all states)
## Last Updated: 2026-11-23

## Summary

Rebuilds the state-level data center load-site inputs for every contiguous US
state from EPRI Powering Intelligence projections, in three scenarios (Low /
Medium / High). This is the load-site input CEPM's national cases actually run
with.

## Key Info
| | |
|---|---|
| **Source data** | EPRI Powering Intelligence dashboard, <https://powering-intelligence.epri.com/dashboard/>. The raw export lives in this folder: `EPRI Powering Intelligence - All States and Total (2026-08-19).csv` — 1,275 rows covering 2021-2030, scenarios `Historical` / `Low` / `Medium` / `High`, 50 state codes plus a `US` national total, with `Nominal Capacity (GW)`, `Peak Load (GW)`, and `Annual Energy (TWh)`. |
| **Produces** | `inputs/load/loadsite_st_epri_{low,medium,high}_extended_to_2033.csv` — long format `*loadsitereg,t,MW`, 48 contiguous states, 2026-2033. All three are committed. The earlier `*_extended_to_2032.csv` files are kept so older runs can be reproduced; their 2026-2032 values are identical. |
| **Related switch(es)** | `GSw_LoadSiteTrajectory = st_epri_(low\|medium\|high)_extended_to_2033`, resolved by `runfiles.csv` through `inputs/load/loadsite_{GSw_LoadSiteTrajectory}.csv`. `cases_cepm.csv` currently sets `st_epri_medium_extended_to_2033` for the `_limitre` and `_optimized` cases. The file is only staged when `GSw_LoadSiteCF > 0`. **The file must cover every solve year up to `endyear`**: a year missing from the file is read as zero load-site MW, with no error (`forecast.py` only extends inputs when `endyear` > 2050). |
| **ReEDS files touched** | None. That switch's `Choices` entry is a generic pattern (`^(nercr\|transreg\|transgrp\|cendiv\|st\|interconnect\|country\|usda_region)_.*$`) which already admits any `st_*` identifier, so no `cases.csv` edit is required, and no `dollaryear.csv` entry is needed — load sites are MW, not monetary values. |
| **Confirmed run?** | Not yet on record. Note this is nevertheless the load-site input `cases_cepm.csv` currently selects, so it is wired up rather than speculative. |

## Files and run order

| File | Description |
|---|---|
| 1. `dc_loadsite_all.ipynb` | The whole pipeline in one notebook: reads the EPRI export, cleans and filters it, extrapolates 2031-2033 (the years in `EXTRAPOLATED_YEARS`), and writes all three loadsite CSVs, named after the last extrapolated year. |
| — `EPRI Powering Intelligence - All States and Total (2026-08-19).csv` | Raw EPRI export; input to step 1. |

### Method and assumptions

- Uses **`Peak Load (GW)` only**. `Nominal Capacity` and `Annual Energy` are
  present in the export but not used for this input. (Changed in 92db6386, which
  switched the metric from nominal capacity to peak load and regenerated all three
  outputs.) How that load is shaped across hours comes from `GSw_LoadSiteCF`, not
  from this file.
- Keeps EPRI years **2026-2030**; the `Historical` scenario and all pre-2026 rows
  are dropped.
- Drops `AK`, `HI`, and the `US` national-total row, leaving **48 states**. (EPRI's
  50 state codes are the 48 contiguous states plus AK and HI — DC is not in the
  source data at all.)
- Converts GW to MW by x1000.
- **2031-2033 are not EPRI forecasts.** For each state and scenario the last
  observed year-over-year growth rate is held constant and compounded:

  `rate = MW(2030) / MW(2029)`, then `MW(2031) = MW(2030) x rate`,
  `MW(2032) = MW(2031) x rate` and `MW(2033) = MW(2032) x rate`

  (2033 was added on 2026-11-23 for CEPM's 2033 solve year. To extend further,
  add years to `EXTRAPOLATED_YEARS`; the output file name follows.)

  A state with zero 2029 peak load has an undefined rate and is held flat at its
  2030 value instead — currently only `WV`, which is zero throughout.
- Writes one CSV per scenario in the `loadsitereg,t,MW` long format, with the
  standard three-line comment header ReEDS expects.

Paths in this notebook resolve from a `REPO_ROOT` walk, so it can be run from any
working directory.

**Reproduction check:** re-deriving all three outputs from the raw export by this
documented method (peak load x 1000, then the compounded 2029→2030 rate) matches
the committed files exactly — 48 states x 7 years, zero mismatches in Low,
Medium, and High. When the files were extended to 2033 (48 states x 8 years),
the 2026-2032 rows matched the `_extended_to_2032` files exactly and every 2033
value equals the 2032 value x the same rate. 2033 totals: Low 56,728 MW,
Medium 103,394 MW, High 147,637 MW (2032: 52,500 / 90,698 / 126,605).

## Issues

- **The 2031-2033 extrapolation rests on a single year-over-year step.** Because
  the 2029→2030 ratio is both the only input to the trend and then compounded
  three times, noise in that one pair propagates. The rates are large for several
  states: LA 31.7%/yr, MS 30.0%, MD 28.6%, IN 27.6% — carrying LA (Medium) from
  765 MW in 2030 to 1,326 MW in 2032 and 1,746 MW in 2033, and IN from 3,280 MW
  to 5,343 MW and 6,819 MW. A fit across all of 2026-2030 would be less sensitive
  to the endpoint. The switch to peak load made these rates steeper than they
  were under nominal capacity.

- **Two folders build load-site inputs by inconsistent methods.**
  `CEPM/preprocessing/dc_load_nm` produces a New-Mexico-only series from the same
  EPRI dashboard, but converts `Annual Energy (TWh)` to a flat MW load and
  extrapolates 2031-2032 linearly, where this folder uses `Peak Load (GW)` and
  compounds a growth rate. They disagree on NM: 273-540 MW for 2026-2030 there
  versus 284-562 MW here — close now that this folder uses peak load rather than
  nominal capacity, but still a different quantity. Only this folder's output is
  wired into `cases_cepm.csv`; the NM-only one is not committed and no case selects
  it. Worth deciding whether `dc_load_nm` is superseded.

- **The raw export filename is hardcoded, including its date.** `EPRI_CSV_PATH`
  embeds `EPRI Powering Intelligence - All States and Total (2026-08-19).csv`, so
  refreshing the EPRI data means editing the notebook rather than dropping in a new
  file. The spaces and parentheses in the name also make it awkward to handle in
  shell commands.

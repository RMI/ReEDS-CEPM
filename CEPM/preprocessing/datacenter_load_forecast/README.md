# Data Center Load Forecast (all states)
## Last Updated: 2026-08-19

## Summary

Rebuilds the state-level data center load-site inputs for every contiguous US
state from EPRI Powering Intelligence projections, in three scenarios (Low /
Medium / High). This is the load-site input CEPM's national cases actually run
with, and it reproduces a methodology previously applied by hand.

## Key Info
| | |
|---|---|
| **Source data** | EPRI Powering Intelligence dashboard, <https://powering-intelligence.epri.com/dashboard/>. The raw export lives in this folder: `EPRI Powering Intelligence - All States and Total (2026-08-19).csv` — 1,275 rows covering 2021-2030, scenarios `Historical` / `Low` / `Medium` / `High`, 50 state codes plus a `US` national total, with `Nominal Capacity (GW)`, `Peak Load (GW)`, and `Annual Energy (TWh)`. |
| **Produces** | `inputs/load/loadsite_st_epri_{low,medium,high}_extended_to_2032.csv` — long format `*loadsitereg,t,MW`, 48 contiguous states, 2026-2032. All three are committed. |
| **Related switch(es)** | `GSw_LoadSiteTrajectory = st_epri_(low\|medium\|high)_extended_to_2032`, resolved by `runfiles.csv` through `inputs/load/loadsite_{GSw_LoadSiteTrajectory}.csv`. `cases_cepm.csv` currently sets `st_epri_medium_extended_to_2032` for `USA_gas_mvp` and `USA_optimized_mvp`. The file is only staged when `GSw_LoadSiteCF > 0`. |
| **ReEDS files touched** | None. That switch's `Choices` entry is a generic pattern (`^(nercr\|transreg\|transgrp\|cendiv\|st\|interconnect\|country\|usda_region)_.*$`) which already admits any `st_*` identifier, so no `cases.csv` edit is required, and no `dollaryear.csv` entry is needed — load sites are MW, not monetary values. |
| **Confirmed run?** | Not yet on record. Note this is nevertheless the load-site input `cases_cepm.csv` currently selects, so it is wired up rather than speculative. |

## Files and run order

| File | Description |
|---|---|
| 1. `dc_loadsite_all.ipynb` | The whole pipeline in one notebook: reads the EPRI export, cleans and filters it, extrapolates 2031-2032, and writes all three loadsite CSVs. |
| — `EPRI Powering Intelligence - All States and Total (2026-08-19).csv` | Raw EPRI export; input to step 1. |

### Method and assumptions

- Uses **`Nominal Capacity (GW)` only**. `Peak Load` and `Annual Energy` are read
  but not used for this input. The MW written is nameplate capacity; the capacity
  factor is supplied separately by ReEDS via `GSw_LoadSiteCF`.
- Keeps EPRI years **2026-2030**; the `Historical` scenario and all pre-2026 rows
  are dropped.
- Drops `AK`, `HI`, and the `US` national-total row, leaving **48 states**. (EPRI's
  50 state codes are the 48 contiguous states plus AK and HI — DC is not in the
  source data at all.)
- Converts GW to MW by x1000.
- **2031-2032 are not EPRI forecasts.** For each state and scenario the last
  observed year-over-year growth rate is held constant and compounded:

  `rate = MW(2030) / MW(2029)`, then `MW(2031) = MW(2030) x rate` and
  `MW(2032) = MW(2031) x rate`

  A state with zero 2029 capacity has an undefined rate and is held flat at its
  2030 value instead — currently only `WV`, which is zero throughout.
- Writes one CSV per scenario in the `loadsitereg,t,MW` long format, with the
  standard three-line comment header ReEDS expects.

Paths in this notebook resolve from a `REPO_ROOT` walk, so it can be run from any
working directory.

**Reproduction check:** re-deriving all three outputs from the raw export by this
documented method matches the committed files exactly — 48 states x 7 years,
zero mismatches in Low, Medium, and High.

## Issues

- **The 2031-2032 extrapolation rests on a single year-over-year step.** Because
  the 2029→2030 ratio is both the only input to the trend and then compounded
  twice, noise in that one pair propagates. The rates are large for several
  states: MS 20.0%/yr, LA 19.8%, MD 19.7%, IN 18.8% — carrying MS from 1,320 MW in
  2030 to 1,901 MW in 2032 and IN from 5,240 MW to 7,398 MW. A fit across
  2026-2030 would be less sensitive to the endpoint, at the cost of departing from
  the method being reproduced.

- **The raw export filename is hardcoded, including its date.** `EPRI_CSV_PATH`
  embeds `EPRI Powering Intelligence - All States and Total (2026-08-19).csv`, so
  refreshing the EPRI data means editing the notebook rather than dropping in a new
  file. The spaces and parentheses in the name also make it awkward to handle in
  shell commands.

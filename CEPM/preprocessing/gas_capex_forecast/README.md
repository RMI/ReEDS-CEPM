# Gas Capex Forecast
## Last Updated: 2026-08-19

## Summary

Regression-based 2026-2032 capex forecast for CCGT and CT gas plants, built from
the Halcyon Gas Power Plant Tracker, and used to update the ATB gas cost input
for ReEDS. It gives CEPM gas build costs drawn from the current project pipeline
rather than ATB's trajectory.

## Key Info
| | |
|---|---|
| **Source data** | Halcyon Gas Power Plant Tracker (17 July 2026). Both raw exports live in this folder: `Halcyon_July_CCGT.csv`, filtered to Combined-Cycle Gas Turbine (CCGT) projects, and `Halcyon_July_CT.csv`, the same tracker filtered to Simple-Cycle Gas Turbine (CT) projects. Both are the tracker's raw export columns (`Planned / Operating Year`, `Cost ($/kW)`, etc.) — no pre-cleaning applied; each notebook does its own cleaning. |
| **Produces** | `inputs/plant_characteristics/gas-ccgt_CEPM_{low,high,all}.csv` — new files; the original `gas_ATB_2024_moderate.csv` is left unmodified. `capcost` is replaced for `Gas-CC` and `Gas-CT` in 2026-2032 only (other gas technologies and years are left untouched). `low` = CCGT low-cost scenario, `high` = CCGT high-cost scenario, `all` = CCGT all-data (mid/reference) scenario; Gas-CT = the CT forecast in all three. |
| **Related switch(es)** | `plantchar_gas = gas-ccgt_CEPM_(low\|high\|all)` |
| **ReEDS files touched** | These names must match the `plantchar_gas` switch values allowed by the `Choices` column in `cases.csv`, and be registered in `inputs/plant_characteristics/dollaryear.csv` (currently `2022`); renaming them requires updating both. `runfiles.csv` needs no change — its `inputs/plant_characteristics/{plantchar_gas}.csv` template already resolves these by name. |
| **Confirmed run?** | Not yet. |

## Files and run order

| File | Description |
|---|---|
| 1. **`CCGT_gas_capex.ipynb`** | Cleans the CCGT data, clusters it with DBSCAN into a low-cost and a high-cost group (DBSCAN was chosen after testing several methods, see `CCGT_clustering_methods.ipynb`), then fits a regression per cluster plus one on all the data combined. Exports `ccgt_regression_forecast.csv`. |
| 2. **`CT_gas_capex.ipynb`** | Same cleaning approach for CT, but fits a single regression on all the data (no clustering). Exports `ct_regression_forecast.csv`. |
| 3. **`gas_CAPEX_update.ipynb`** | Reads `ccgt_regression_forecast.csv` and `ct_regression_forecast.csv` and builds 3 new versions of the ATB gas cost input, replacing `capcost` for `Gas-CC` and `Gas-CT` in 2026-2032 only (other gas technologies and years are left untouched). |
| — **`CCGT_clustering_methods.ipynb`** | Side notebook comparing clustering methods (K-Means, hierarchical with ward/complete/average/single linkage, DBSCAN) on the CCGT data, to justify why DBSCAN is the one used in `CCGT_gas_capex.ipynb`. Not part of the main pipeline — exploratory only. |
| — `Halcyon_July_CCGT.csv`, `Halcyon_July_CT.csv` | Raw tracker exports; inputs to steps 1 and 2. |
| — `ccgt_regression_forecast.csv` | CCGT forecast 2026-2032: low-cost cluster, high-cost cluster, and all-data. Output of step 1, input to step 3. |
| — `ct_regression_forecast.csv` | CT forecast 2026-2032 (single scenario). Output of step 2, input to step 3. |

All paths in these notebooks resolve from a `REPO_ROOT` walk, so they can be run
from any working directory.

## Issues

- **The two Halcyon exports don't have matching columns.** `Halcyon_July_CCGT.csv`
  has 15 columns; `Halcyon_July_CT.csv` has 16, the extra one being an unnamed,
  always-empty trailing field created by a trailing comma on every line. In *both*
  files the last two headers also disagree with their contents: `EIA Status` holds
  what look like EIA plant IDs (`66918`, `201`) and `EIA Plant ID` holds owner
  names (`Clean Energy Future - Trumbull, LLC.`, `Arkansas Electric Coop Corp`),
  so the trailing fields are shifted one place relative to their labels. This does
  **not** currently affect the forecast — the notebooks read only
  `Planned / Operating Year` and `Cost ($/kW)`, both of which sit ahead of the
  shift — but the headers would need fixing before anyone used the location,
  status, or ID fields, and the two files can't be concatenated as-is.

- **Costs are never resolved to a common dollar year.** The tracker rows carry
  mixed `Dollar Year` values — mostly 2025/2026, some 2020-2024, and blank (`-`)
  for 12 of 33 CCGT and 14 of 38 CT rows — and no notebook in the pipeline reads
  that column or applies a deflator. Raw `Cost ($/kW)` values pass straight
  through the regression into `capcost`. Meanwhile `dollaryear.csv` registers all
  three outputs as `2022`, a label inherited from the `gas_ATB_2024_moderate` file
  they are copied from, so ReEDS deflates them as if they were already 2022
  dollars. Normalizing to **2022** before fitting is probably the easiest fix: it
  matches both the ATB base file and the existing `dollaryear.csv` entry, so the
  CEPM variants stay directly comparable to the upstream ATB input. Worth noting
  separately that fitting cost against *operating year* also folds some nominal
  escalation into the slope, which normalizing the inputs would not remove.

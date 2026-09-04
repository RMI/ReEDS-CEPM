# Gas Capex Forecast
## Last Updated: 2026-09-04

## Summary

Regression-based 2026-2032 capex forecast for CCGT and CT gas plants, built from the Halcyon Gas Power Plant Tracker, and used to update the ATB gas cost input for ReEDS. It gives CEPM gas build costs drawn from the current project pipeline
rather than ATB's trajectory.

## Key Info
| | |
|---|---|
| **Source data** | Halcyon Gas Power Plant Tracker (24 Aug 2026), `Halcyon Gas Power Plant Tracker - 24 Aug 2026 .xlsx` (sheet `Gas Plants`), 473 rows across all gas technologies and all US states. |
| **Produces** | `inputs/plant_characteristics/gas-ccgt_CEPM_all.csv` — a new file; the original `gas_ATB_2024_moderate.csv` is left unmodified. `capcost` is replaced for `Gas-CC` and `Gas-CT` in 2026-2032 only (other gas technologies and years are left untouched). A single scenario — see "Why no clustering" below. |
| **Related switch(es)** | `plantchar_gas = gas-ccgt_CEPM_all` |
| **ReEDS files touched** | The output name must match a `plantchar_gas` switch value allowed by the `Choices` column in `cases.csv`, and be registered in `inputs/plant_characteristics/dollaryear.csv` (currently `2022`, which matches the 2022$ normalization done here); renaming it requires updating both. `runfiles.csv` needs no change — its `inputs/plant_characteristics/{plantchar_gas}.csv` template already resolves this by name. `cases_cepm.csv` already points `plantchar_gas` at `gas-ccgt_CEPM_all`. |
| **Confirmed run?** | Not yet. |

## Files and run order

| File | Description |
|---|---|
| 1. **`data_cleaning_gas.ipynb`** | Loads the raw Halcyon Excel export, keeps only rows with a reported `Cost ($/kW)`, normalizes cost to **2022$** (see "Dollar-year normalization" below), and splits into `Halcyon_August_CCGT.csv` / `Halcyon_August_CT.csv` (Technology Type = Combined-Cycle / Simple-Cycle Gas Turbine). |
| 2. **`CCGT_gas_capex.ipynb`** | Cleans the CCGT data (drop year > 2032 or cost > $3000/kW) and fits a **single regression on all 27 plants**, using the normalized cost. No clustering — see `CCGT_clustering_methods.ipynb` for why. Exports `ccgt_regression_forecast.csv`. |
| 3. **`CT_gas_capex.ipynb`** | Same approach for CT: single regression on all 35 plants, normalized cost. Exports `ct_regression_forecast.csv`. |
| 4. **`gas_CAPEX_update.ipynb`** | Reads `ccgt_regression_forecast.csv` and `ct_regression_forecast.csv` and builds `gas-ccgt_CEPM_all.csv`, replacing `capcost` for `Gas-CC` and `Gas-CT` in 2026-2032 only. |
| — **`CCGT_clustering_methods.ipynb`** | Side notebook comparing clustering methods (K-Means, hierarchical with ward/complete/average/single linkage, DBSCAN) on the CCGT data. **Conclusion: none gives a robust, meaningful low/high cost-tier split** — the split is confounded with operating year, the "high" cluster isn't homogeneous, the "low" cluster's regression isn't significant, and the whole result flips (11/16 → 21/6) when a single plant's cost is revised between tracker updates. Not part of the main pipeline — exploratory only, informs the "no clustering" decision in step 2. |
| — `Halcyon Gas Power Plant Tracker - 24 Aug 2026 .xlsx` | Raw tracker export. Input to step 1. |
| — `Halcyon_August_CCGT.csv`, `Halcyon_August_CT.csv` | Cleaned, cost-normalized tracker exports. Output of step 1, input to steps 2-3. |
| — `ccgt_regression_forecast.csv` | CCGT forecast 2026-2032 (single scenario). Output of step 2, input to step 4. |
| — `ct_regression_forecast.csv` | CT forecast 2026-2032 (single scenario). Output of step 3, input to step 4. |

All paths in these notebooks resolve from a `REPO_ROOT` walk, so they can be run
from any working directory.

## Dollar-year normalization

Halcyon `Cost ($/kW)` values aren't all in the same dollar year (per the tracker's own `Methodology` sheet, `Dollar Year` is *"the reference year of reported capital cost values, if explicitly stated. If not provided, the dollar year defaults to the publication date of the filing."*). `data_cleaning_gas.ipynb` normalizes every cost to **2022$**, to match `inputs/plant_characteristics/dollaryear.csv`'s existing `2022` entry for `gas-ccgt_CEPM_all` (inherited from `gas_ATB_2024_moderate`).

Method: chain annual rates from `inputs/financials/inflation_default.csv` (1914-2200, flat 2.5%/yr from 2026 on — the same source `reeds/financials.py` uses elsewhere in the model; `inputs/financials/deflator.csv` isn't used here since it stops at 2025). Dollar year is taken from, in order: (1) the tracker's explicit `Dollar Year`, (2) the `Announcement Date`'s year as fallback, (3) if both are missing, the row is dropped (2 CCGT rows: *Smarr Combined Cycle Energy Facility*, *Westlake Power Station CA1/CT1*).

Normalizing dollar year only fixes the *reported cost basis* — it doesn't remove the real cost escalation the regression is trying to estimate by fitting cost against operating year; those are different things.

## Resolved issues (from the July tracker version)

- **Column mismatch between exports** — the old `Halcyon_July_CCGT.csv` / `Halcyon_July_CT.csv` had different column counts and shifted trailing headers. Fixed by `data_cleaning_gas.ipynb`, which reads directly from the source Excel and selects columns by name, rather than concatenating pre-exported CSVs.
- **Mixed dollar years** — fixed by the normalization step above.

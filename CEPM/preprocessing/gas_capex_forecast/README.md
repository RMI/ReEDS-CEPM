# Gas Capex Forecast

Regression-based 2026-2032 capex forecast for CCGT and CT gas plants, built from the Halcyon Gas Power Plant Tracker, and used to update the ATB gas cost input for ReEDS.

## Input data

- `Halcyon_July_CCGT.csv` — Halcyon tracker data (17 July 2026), filtered to Combined-Cycle Gas Turbine (CCGT) projects.
- `Halcyon_July_CT.csv` — same tracker, filtered to Simple-Cycle Gas Turbine (CT) projects.

Both are the Halcyon tracker's raw export columns (`Planned / Operating Year`, `Cost ($/kW)`, etc.) — no pre-cleaning applied; each notebook does its own cleaning.

## Notebooks (run in this order)

1. **`CCGT_gas_capex.ipynb`** — Cleans the CCGT data, clusters it with DBSCAN into a low-cost and a high-cost group (DBSCAN was chosen after testing several methods, see next notebook), then fits a regression per cluster plus one on all the data combined. Exports `ccgt_regression_forecast.csv`.
2. **`CT_gas_capex.ipynb`** — Same cleaning approach for CT, but fits a single regression on all the data (no clustering). Exports `ct_regression_forecast.csv`.
3. **`CCGT_clustering_methods.ipynb`** — Side notebook comparing clustering methods (K-Means, hierarchical with ward/complete/average/single linkage, DBSCAN) on the CCGT data, to justify why DBSCAN is the one used in `CCGT_gas_capex.ipynb`. Not part of the main pipeline — exploratory only.
4. **`gas_CAPEX_update.ipynb`** — Reads `ccgt_regression_forecast.csv` and `ct_regression_forecast.csv` and builds 3 new versions of the ATB gas cost input, replacing `capcost` for `Gas-CC` and `Gas-CT` in 2026-2032 only (other gas technologies and years are left untouched).

## Output CSVs

In this folder:
- `ccgt_regression_forecast.csv` — CCGT forecast 2026-2032: low-cost cluster, high-cost cluster, and all-data.
- `ct_regression_forecast.csv` — CT forecast 2026-2032 (single scenario).

In `inputs/plant_characteristics/` (new files, the original `gas_ATB_2024_moderate.csv` is left unmodified):
- `gas-ccgt_CEPM_low.csv` — Gas-CC = CCGT low-cost scenario, Gas-CT = CT forecast.
- `gas-ccgt_CEPM_high.csv` — Gas-CC = CCGT high-cost scenario, Gas-CT = CT forecast.
- `gas-ccgt_CEPM_all.csv` — Gas-CC = CCGT all-data (mid/reference) scenario, Gas-CT = CT forecast.

These names must match the `plantchar_gas` switch values allowed by the
`Choices` column in `cases.csv` (`gas-ccgt_CEPM_(low|high|all)`) and be
registered in `inputs/plant_characteristics/dollaryear.csv`; renaming them
requires updating both.

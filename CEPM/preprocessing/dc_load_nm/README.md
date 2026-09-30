# New Mexico Data Center Load Site
## Last Updated: 2026-08-19

## Summary

**NOTE: This folder is basically redundant with datacenter_load_forecast. Currently keeping for posterity purposes.**

Builds a New Mexico data center load-site trajectory from EPRI Powering
Intelligence projections, converting projected annual energy into the flat
hourly load that ReEDS reads as an exogenous large-load site.

## Key Info
| | |
|---|---|
| **Source data** | EPRI Powering Intelligence dashboard, <https://powering-intelligence.epri.com/dashboard/>. The raw export lives in this folder: `epri_powering_intelligence_nm.csv` (NM rows only; `Historical` plus Low/Medium/High scenarios, with `Nominal Capacity (GW)`, `Peak Load (GW)`, and `Annual Energy (TWh)`). |
| **Produces** | `inputs/load/loadsite_st_NM_EPRI_medium_2026_2032.csv` — long format `*loadsitereg,t,MW`, NM only, 2026-2032. Note this output is not currently committed, and no case in `cases_cepm.csv` selects it yet. |
| **Related switch(es)** | `GSw_LoadSiteTrajectory` — `runfiles.csv` resolves `inputs/load/loadsite_{GSw_LoadSiteTrajectory}.csv`, so this output corresponds to `GSw_LoadSiteTrajectory = st_NM_EPRI_medium_2026_2032`. The file is only staged when `GSw_LoadSiteCF > 0`. |
| **ReEDS files touched** | None. `runfiles.csv`'s existing `loadsite_{GSw_LoadSiteTrajectory}.csv` template picks the file up by name, and that switch's `Choices` entry is a generic pattern (`^(nercr\|transreg\|transgrp\|cendiv\|st\|interconnect\|country\|usda_region)_.*$`) that already admits any `st_*` identifier — so no `cases.csv` edit is required. No `dollaryear.csv` entry is needed either: load sites are MW, not monetary values. |
| **Confirmed run?** | Not yet. |

## Files and run order

| File | Description |
|---|---|
| 1. `nm_loadsite_dc_csv.ipynb` | Filters the EPRI export to the Medium scenario for NM, takes annual energy for 2026-2030, extrapolates 2031-2032, converts to a flat MW load, and writes the loadsite CSV. |
| — `epri_powering_intelligence_nm.csv` | Raw EPRI export; input to step 1. |

### Method and assumptions

- Uses the **Medium** EPRI scenario.
- Uses EPRI annual energy directly for **2026-2030**.
- **2031-2032 are not EPRI forecasts.** They are a straight-line continuation:
  `energy(y) = energy(2030) + (y - 2030) x avg annual increase`, where the
  average annual increase is `(energy(2030) - energy(2026)) / 4`.
- Converts annual energy to a flat hourly load, so the site draws the same MW in
  every hour of the year:

  `Flat MW = Annual Energy TWh x 1,000,000 / 8,760`

- The region column holds state codes (`NM`). Per the switch's own
  description, the filename is `loadsite_{hierarchy level}_{identifier}.csv`,
  so the `st` in the filename and the state codes in the first column have to
  agree. Multiple regions can be listed as extra rows in long format.

Paths in this notebook resolve from a `REPO_ROOT` walk, so it can be run from
any working directory.

## Issues

- **Superseded by [`../datacenter_load_forecast/`](../datacenter_load_forecast/).**
  This NM-only output is not committed and no case selects it.

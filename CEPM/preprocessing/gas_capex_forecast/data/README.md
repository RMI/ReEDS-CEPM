# Halcyon data (not tracked in git)

This folder holds the proprietary Halcyon Gas Power Plant Tracker data used by
the notebooks in `CEPM/preprocessing/gas_capex_forecast/`. The data files are
licensed to RMI and must not be committed, so `*.csv` and `*.xlsx` in this
folder are listed in the repo's `.gitignore`. Only this README is tracked.

## Getting the files

RMI staff can download them from SharePoint:

`CEP (Clean Energy Planning)/ACTIVE IRP Direct Engagement and Load Growth TL/Clean Energy Portfolios 4.0/VM-Inputs/halcyon-data`

Put them in this folder with these exact names:

| File | Description |
|---|---|
| `Halcyon Gas Power Plant Tracker - 24 Aug 2026 .xlsx` | Raw tracker export (note the space before `.xlsx`). Input to `data_cleaning_gas.ipynb`. |
| `Halcyon_August_CCGT.csv`, `Halcyon_August_CT.csv` | Cleaned, cost-normalized CCGT and CT exports. Written by `data_cleaning_gas.ipynb`, read by `CCGT_gas_capex.ipynb`, `CT_gas_capex.ipynb`, and `CCGT_clustering_methods.ipynb`. |

The two CSVs can be regenerated from the `.xlsx` by running
`data_cleaning_gas.ipynb`, so only the `.xlsx` is strictly required.

## Before committing

- Check that `git status` doesn't list any Halcyon files.
- Clear notebook outputs before committing (for example,
  `jupyter nbconvert --clear-output --inplace *.ipynb`), since saved tables and
  plots can contain plant-level Halcyon data.

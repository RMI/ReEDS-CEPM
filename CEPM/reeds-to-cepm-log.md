**Note: This document is incomplete!**

# ReEDS-to-CEPM change log

This file will track the changes made by the CEPM repo compared to the ReEDS
repo, including the location of files in the ReEDS repo that were changed by
CEPM.

**Current ReEDS base release: June 2026**

# Changes to base ReEDS files

In some cases, we change base ReEDS files to fix bugs, ensure compatiability,
or adjust ReEDS functionality for CEPM's needs. Most of these are captured in [`known issues`](known-issues.md).

## GAMS Compatibility

### Description of issue:

### Files changed:

### Reference: [`known issues`](known-issues.md)

### What to test in new releases:

## Resolving census divisions in fuelcostprep.py

### Description of issue:
### Files changed:
### Reference: [`known issues`](known-issues.md)
### What to test in new releases:

## Resolving recf.py when offshore wind is disabled

### Description of issue:
### Files changed:
### Reference:
[`known issues`](known-issues.md)
### What to test in new releases:

# Custom CEPM inputs and changes to ReEDS files

We also implement several custom inputs to our CEPM scenarios, which add new input files and also change some underlying ReEDS files. These should all have documentation in [CEPM/preprocessing](CEPM/preprocessing).



## Updated CAPEX for gas resources

### Description:

### Input files created:

### Underlying ReEDS files changed:
- cases.csv
- dollaryear.csv

### Reference:
[CEPM/preprocessing/gas_capex_forecast](CEPM/preprocessing/gas_capex_forecast)

### What to test in new releases

## Updated load forecasts for data centers

### Description:

### Input files created:

### Underlying ReEDS files changed:

### Reference:
[CEPM/preprocessing/datacenter_load_forecast](CEPM/preprocessing/datacenter_load_forecast)

### What to test in new releases:
- Has loadsite's compatibility changed?
- Are we changing underlying load forecast / would that double-count data center loads?

# CEPM documentation and functionality

## Github repo-level ENABLE_GAMS_CI variable:

### Description:
### Files included:
### Reference: 
### What to test in new releases:

## Using uv isntead of mamba for environemnt/apckage management

### Description:
### Files included:
### Reference: 
### What to test in new releases:


## run_cepm helper script

### Description:
### Files included:
### Reference: 
[`run_cepm.ps1`](run_cepm.ps1), [`CEPM/scripts`](CEPM/scripts)
### What to test in new releases:
Does environemtn still resolve? Did Python version expectations change? Do we need to change the environemnt variables that the script automatically sets?

## CEPM documentation
### Description:
### Files included:
### Reference: 
[`run_cepm.ps1`](run_cepm.ps1), [`CEPM/scripts`](CEPM/scripts)
### What to test in new releases:
Does environemtn still resolve? Did Python version expectations change? Do we need to change the environemnt variables that the script automatically sets?

## cases_cepm.csv file
### Description:
### Files included:
### Reference: 

### What to test in new releases:





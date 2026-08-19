# ReEDS-to-CEPM change log

This file will track the changes made by the CEPM repo compared to the ReEDS
repo, including the location of files in the ReEDS repo that were changed by
CEPM.

> **Status: incomplete.** The tables below have been started but are not a
> complete record of divergence from upstream. Until they are filled in, `git
> diff` against the upstream remote remains the authoritative answer to "what
> did CEPM change?"

## Changed upstream files

CEPM-specific additions are kept in `CEPM/` where practical, but some changes
necessarily live in upstream file locations. Those go here.

| Upstream path | Change | Why | Reference |
|---|---|---|---|
| `cases.csv` | Added `gas-ccgt_CEPM_(low\|high\|all)` to the `plantchar_gas` row's `Choices` column, and reworded that row's `Description` to distinguish upstream `gas_` options from CEPM `gas-ccgt_CEPM_` ones. | `Choices` is enforced as a regex in [`reeds/inputs.py`](../reeds/inputs.py) (`parse_cases`), so a CEPM switch value that is not listed raises `ValueError` at case setup. There is no per-fork override — the upstream file has to be edited in place. | [`gas_capex_forecast/README.md`](preprocessing/gas_capex_forecast/README.md) |

> **This section is incomplete.** Other upstream files have already been changed
> without being logged here — `inputs/plant_characteristics/dollaryear.csv` and
> the `inputs/` CSVs themselves among them. Add a row whenever you change a file
> that came from upstream.

## CEPM-only additions

Files that exist only in this repo and have no upstream counterpart. See
[`README.md`](README.md) for what each one does.

| Path | Purpose |
|---|---|
| _(not yet populated)_ | |

## CEPM inputs criteria:

* **Each CEPM input category gets its own file or folder in `CEPM/preprocessing'**: It's OK if one folder creates multiple types of outputs, but the folder name should be descriptive.
* **Pre-processing folders are easily understandable.**: Pre-processing folders should contain a file named, for example, "main.ipynb" or "README.md" that orients the reader to what's in the folder--what each file does, and if needed which order they run in. Any main or README file should include a header with a concise description of what we're making, where the source comes from, where the new inputs files live in the repo, and any other files that were changed to facilitate this input.
* **Raw inputs are either in the CEPM preprocessing folder or are easily accessible:** Documentation explicitly identifies the exact source of our data. The raw data file is either included in `CEPM/preprocessing` or is linked somewhere in the folder.
* **Pre-processing converts raw inputs to ReEDS-ready inputs**: A user should be able to track the raw inputs all the way to what ReEDS sees.
* **Custom CEPM input files include `CEPM` in their titles**: This way it's easy to know what's a custom input and what's not.
* **CEPM inputs are validated against ReEDS inputs.**: This should happen, if possible, in the preprocessing scripts. Can we compare our inputs against what's already in ReEDS to show that they're apples-to-apples?
* **Pre-processing scripts save CEPM input files in the right location in the repo**: Pre-processing scripts should save CEPM input files directly where they can be used by ReEDS--no manual moving required. If you don't kinow where the file eventually needs to go, consult runfiles.csv or your favorite LLM.
* **CEPM inputs are integrated into relevant ReEDS infrastructure.**: Any changes to other files in the ReEDS repo that are required for this input to run should be implemented and recorded somewhere in the ReEDS preprocessing folder. This could include, but likely is not limited to:
    * **cases.csv**: Any change to switch options will require a change here.
    * **runfiles.csv**: Double-check that the path is correct for this.
    * **dollaryear.csv**: All plant characteristics files need to specify their dollaryear.
    * `reeds-data-sources.md` might be helpful for identifying other files that need updating.
* **You've kicked off at least one run and confirmed that it loads in the new inputs.**
# Requirements for adding inputs to CEPM
# Last Edited: 2026-08-20

Below is a list of requirements criteria for adding custom inputs to CEPM. These bullets ensure that our custom
inputs are consistent, understandalbe, and relatively easy to adjust if changes to ReEDS' functionality require
that we adjust our appraoch.

## CEPM inputs criteria:

* **Each CEPM input category gets its own file or folder in `CEPM/preprocessing'**: It's OK if one folder creates multiple types of outputs, but the folder name should be descriptive.
* **Pre-processing folders are easily understandable.**: Pre-processing folders should contain a file named, for example, "main.ipynb" or "README.md" that orients the reader to what's in the folder--what each file does, and if needed which order they run in. Any main or README file should include a header with a concise description of what we're making, where the source comes from, where the new inputs files live in the repo, and any other files that were changed to facilitate this input. The [`README_TEMPLATE`.md](README_TEMPLATE.md) file in this folder provides a good reference.
* **Raw inputs are either in the CEPM preprocessing folder or are easily accessible:** Documentation explicitly identifies the exact source of our data. The raw data file is either included in `CEPM/preprocessing` or is linked somewhere in the folder.
* **Pre-processing converts raw inputs to ReEDS-ready inputs**: A user should be able to track the raw inputs all the way to what ReEDS sees.
* **Custom CEPM input files include `CEPM` in their titles**: This way it's easy to know what's a custom input and what's not.
* **CEPM inputs are validated against ReEDS inputs.**: This should happen, if possible, in the preprocessing scripts. Can we compare our inputs against what's already in ReEDS to show that they're apples-to-apples?
* **Pre-processing scripts save CEPM input files in the right location in the repo**: Pre-processing scripts should save CEPM input files directly where they can be used by ReEDS--no manual moving required. If you don't kinow where the file eventually needs to go, consult runfiles.csv or your favorite LLM.
* **Edit any ReEDS-specific files you have to, and record what you edited..**: Any changes to other files in the ReEDS repo that are required for this input to run should be implemented and recorded in your README.. This could include, but likely is not limited to:
    * **cases.csv**: Any change to switch options will require a change here.
    * **runfiles.csv**: Double-check that the path is correct for this.
    * **dollaryear.csv**: All plant characteristics files need to specify their dollaryear.
    * `reeds-data-sources.md` might be helpful for identifying other files that need updating.
* **You've kicked off at least one run and confirmed that it loads in the new inputs.**
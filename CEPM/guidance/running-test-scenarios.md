# Guide to running test scenarios

This doc guides users through running test scenarios in CEPM.

# What is a test scenario?

Test scenarios are not intended to be new iterations of our core CEPM runs.
Instead, test scenarios

# Objectives

# Steps

1. Pull a new branch from the appropriate working branch, likely either `main` or `dev`. Give it a descriptive title.
2. Make a new cases file by copying `cases_cepm.csv`. Give it a descriptive suffix like `cases_coalretirement.csv`. Keep it in the root folder for now. By default, let's run our tests on the whole two-step scenario run, so you'll want to keep at least one geography with _baseline, _limitre, and _optimized.
3. Add new rows to your cases file with the switches you'd like to test. It makes sense to keep one two-step scenario, then include one or more changed two-step scnearios. Change the run names to reflect the settings, but note that for each two-step scenario the name should remain the same, with the _baseline, _limitre, and _optimized suffixes intact.
4. Run your scenarios using ./run_cepm.ps1. You'll want to use the -m option to run the two-step scenario, and likely the -x method to generate the comparison reports. A command that sets off this two-step run might look like: 

`./run_cepm.ps1 -m st-AZNMnoretire -x -b vcoaltest1 -c coalretirement`
   1. Let's break this command down:
      1. `-m st-AZNMnoretire`. This option tells run_cepm to look for the two-step scenario setup for runs that start with st-AZNMnoretire.
      2. `-x` This option runs the multi-run comparison report once all runs are finished.
      3. `-b vcoaltest1` This option sets the batch name -- that's the prefix that comes before the run names in the `/runs` folder. We have previsouly used dates, but I think for these tests a descriptive name makes more sense. Note that these's a bug with -x right now, so each multi-step run should have its own batch name. Typically these batchhes have started with a `v`.
      4. `-c coalretirement` this option tells run_cepm which cases file to use. Note that you only need to give the part after the underscore.

5. Take a look at the run outputs and comparisons and, if needed, make changes and do more runs.
6. Once you're ready to share your test:
   1. Copy and paste your runs from the `runs` folder in your repo to the `VM-Outputs` file on Sharepoint.
   2. Add an entry in [`/CEPM/batch-log.md`](/CEPM/batch-log.md) using the batch template at the top.
   3. Tell the team about your test, what you found, and what you recommend we do moving forward.
7. Once the group has come to consensus, finalize your test:
   1. Update CEPM documentation as needed, including any decisions, reeds issues, or things to put in theh reeds_to_cepm_log.
   2. Move your `cases_example.csv` file into [`/CEPM/cases-archive`](/CEPM/cases-archive/).
   3. Open a pull request to pull your changes into the working branchh.
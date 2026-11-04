# Guide to running test scenarios
Written Date: 2026-09-29

This doc guides users through running test scenarios in CEPM.

# What is a test scenario?

Test scenarios are not intended to be new iterations of our core CEPM runs.
Instead, a test scenario changes one or two switches against a copy of the core
two-step runs (`_baseline`, `_limitre`, `_optimized`), so we can see what the
change does and decide as a group whether to adopt it. If we do, the change goes
into `cases_cepm.csv` and becomes part of the core runs from then on.

If what you've found is a bug in the model code rather than a question about
settings, follow [`fixing-reeds-issues.md`](fixing-reeds-issues.md) instead.

# Objectives

A good test scenario:

- **Changes only what's being tested.** Everything else matches the core runs, so
  any difference in the results comes from your change.
- **Can be reproduced.** Someone else can re-run it from your cases file and your
  `batch-log.md` entry alone.
- **Gives the team enough to decide.** The comparison report and your write-up
  show what changed and what you recommend.

# Steps

1. Pull a new branch from the appropriate working branch, likely either `main` or `dev`. Give it a descriptive title. Branch from the remote tip, since your local copy may be out of date:

   ```
   git fetch origin
   git switch -c test/coalretirement origin/dev
   ```

2. Make a new cases file by copying `cases_cepm.csv`. Give it a descriptive suffix like `cases_coalretirement.csv`. Keep it in the root folder for now. By default, let's run our tests on the whole two-step scenario run, so you'll want to keep at least one geography with _baseline, _limitre, and _optimized.
   1. Each two-step scenario needs all three columns. `_limitre` must have `GSw_CEPM_TgCap` set to `1`, and `_baseline` and `_optimized` must have it at `0` or blank. `run_cepm.ps1 -m` checks this before it starts anything.
   2. **Keep `cleanup_level` at `0` in every column**, including columns you aren't running. With any other value, `runreeds.py` stops and waits for a yes/no answer at launch. A `-m` run runs in the background, so you never see the prompt and the batch just hangs.
3. Add new rows to your cases file with the switches you'd like to test. It makes sense to keep one two-step scenario as-is as a counterfactual, then include one or more changed two-step scenarios. Change the run names to reflect the settings, but note that for each two-step scenario the stem should remain the same, with the _baseline, _limitre, and _optimized suffixes intact.

   For example, a file that keeps the core AZ/NM runs and adds one changed version might have these columns. `GSw_YourSwitch` stands in for whatever you're testing:

   | | `st-AZNM_baseline` | `st-AZNM_limitre` | `st-AZNM_optimized` | `st-AZNMnoretire_baseline` | `st-AZNMnoretire_limitre` | `st-AZNMnoretire_optimized` |
   |---|---|---|---|---|---|---|
   | `GSw_CEPM_TgCap` | | `1` | | | `1` | |
   | `cleanup_level` | `0` | `0` | `0` | `0` | `0` | `0` |
   | `GSw_YourSwitch` | | | | *new value* | *new value* | *new value* |

   The stem (`st-AZNMnoretire`) is what you pass to `-m` in the next step.

4. Run your scenarios using ./run_cepm.ps1. You'll want to use the -m option to run the two-step scenario, and likely the -x method to generate the comparison reports.
   1. **Do a dry run first.** Adding `-t` checks both phases' switches in a few seconds without solving anything, which catches typos that would otherwise fail well into a run:

      `./run_cepm.ps1 -m st-AZNMnoretire -t -b vcoaltest1 -c coalretirement`

   2. Then start the real run. A command that sets off this two-step run might look like:

      `./run_cepm.ps1 -m st-AZNMnoretire -x -b vcoaltest1 -c coalretirement`

      Let's break this command down:
      1. `-m st-AZNMnoretire`. This option tells run_cepm to look for the two-step scenario setup for runs that start with st-AZNMnoretire.
      2. `-x` This option runs the multi-run comparison report once all runs are finished.
      3. `-b vcoaltest1` This option sets the batch name -- that's the prefix that comes before the run names in the `/runs` folder. We have previously used dates, but I think for these tests a descriptive name makes more sense. Typically these batches have started with a `v`. **Use a new batch name for every run.** `-x` compares every folder in `runs/` whose name starts with the batch name, so reusing one pulls leftover runs from an earlier attempt into your comparison.
      4. `-c coalretirement` this option tells run_cepm which cases file to use. Note that you only need to give the part after the underscore.
   3. Other useful options:
      - `-u <name>` puts your name in the ntfy notifications, so the team can tell whose run finished.
      - `-o` re-runs only the comparison report for a finished batch, without re-solving anything. Use it if `-x` failed or you want to regenerate the report.
      - Don't pass `-r`/`--simult_runs`. PowerShell swallows it on the way through, and `-m` already sets the number of simultaneous runs for you.
   4. Expect a WECC-SW two-step run to take roughly 45-50 minutes. The ntfy notification tells you when it's done.

5. Take a look at the run outputs and comparisons and, if needed, make changes and do more runs.
   1. **Check that every run actually finished.** `runreeds.py` reports success even when a solve fails. Each run folder should contain `outputs/outputs.h5`; if one doesn't, that run failed.
   2. If a run failed, look at `gamslog.txt` in its run folder, then the newest file in its `lstfiles/` folder. Then search [`known-reeds-issues.md`](../known-reeds-issues.md) for the error text. If it turns out to be a bug in the model code, see [`fixing-reeds-issues.md`](fixing-reeds-issues.md).
6. Once you're ready to share your test:
   1. Copy and paste your runs from the `runs` folder in your repo to the `VM-Outputs` folder on SharePoint.
   2. Add an entry in [`/CEPM/batch-log.md`](/CEPM/batch-log.md) using the batch template at the top.
   3. Tell the team about your test, what you found, and what you recommend we do moving forward.
7. Once the group has come to consensus, finalize your test:
   1. Update CEPM documentation as needed:
      - If the team adopts the change, update `cases_cepm.csv`, and record the decision in `batch-log.md`.
      - If the test hit a bug in the model code, add it to [`known-reeds-issues.md`](../known-reeds-issues.md).
      - If you had to change any upstream file (anything outside `CEPM/`), record it in [`reeds-to-cepm-log.md`](../reeds-to-cepm-log.md).
   2. Move your `cases_example.csv` file into [`/CEPM/cases-archive`](/CEPM/cases-archive/).
   3. Open a pull request to pull your changes into the working branch.

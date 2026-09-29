# Guide to fixing ReEDS issues

This doc walks you through fixing a problem in the ReEDS model code on the CEPM
fork: from spotting the problem to opening a pull request.

For a worked example, see branch `fix/ra-plot-logging`
([PR #60](https://github.com/RMI/ReEDS-CEPM/pull/60)). It fixed two bugs in how
the resource-adequacy diagnostic plots run after each solve year. It's
referenced throughout.

# What is a ReEDS issue?

A ReEDS issue is a problem with the *machinery*: a script that crashes, a GAMS
equation that goes infeasible, a missing input file, a plot that can't handle
our region set, or a run that's slower than it should be. The test is whether a
fresh clone of the repo would hit it.

Problems with a *result* are different. A scenario set up wrong, an input we
don't trust, or a modeling choice we want to revisit goes in
[`batch-log.md`](../batch-log.md) against the batch that surfaced it, not here.

# Objectives

A good fix:

- **Is reviewable on its own.** One issue per branch, with no unrelated changes.
- **Keeps our divergence from upstream visible.** Every upstream file we touch is
  recorded, so whoever does the next upstream sync knows what to re-check.
- **Leaves a trail from symptom to fix.** Someone who hits the same error message
  later can find the cause, the fix, and whether it's still live.
- **Can go back to upstream.** Most bugs we find are upstream's too, and a
  well-documented fix is easy to contribute back.

# Steps

1. **Pull a new branch from the working branch.** The working branch is likely
   `dev`, occasionally `main`. Name the branch `fix/` plus a short description,
   like `fix/ra-plot-logging`.
   1. Branch from the *remote* tip, not your local copy, which may be out of date:

      ```
      git fetch origin
      git switch -c fix/example origin/dev
      ```

   2. If the working branch moves on before your fix merges, rebase onto it rather
      than merging it in:

      ```
      git fetch origin
      git rebase origin/dev
      git push --force-with-lease origin fix/example
      ```

      The force-push rewrites your branch on GitHub, so make sure nobody else
      has built on it first.

2. **If there isn't already an entry in
   [`known-reeds-issues.md`](../known-reeds-issues.md), write one.**
   1. Search the file first for the script name and the exact error text. The
      same problem often shows up with slightly different details.
   2. If it isn't there, add an entry using the same structure as the others:
      - **Symptom:** what you saw, with the exact error text and the run folder
        it came from (for example `runs/v20260902t7_WECC-SW_baseline/gamslog.txt`).
        Most failures show up first in `gamslog.txt`, then in the newest file
        under `lstfiles/`.
      - **Root cause:** why it happens, once you know.
      - **Impact:** what it breaks. Does it change model results, or only a plot,
        a log, or run time?
      - **Status:** "not fixed" for now.
      - **Fixed upstream?** Check the upstream release we're synced to (the tag is
        named at the top of `known-reeds-issues.md`, currently `2026.08.03`):

        ```
        git fetch upstream --tags
        git show 2026.08.03:path/to/file.py
        ```

        If upstream has the same code, say so. That tells us the bug is
        inherited rather than one we introduced.
   3. Check whether the problem is new or already existed. Try to reproduce it on
      the working branch before any recent changes. A bug that's been there all
      along is much less alarming than one a recent sync introduced.

3. **Propose a solution to the problem.**
   1. First check whether upstream has already fixed it. If so, take their
      version rather than writing our own. That keeps our changes from upstream
      small. Look at recently approved pull requests and issues in addition to release notes.
   2. Keep the fix as small as it can be. Put CEPM-only additions in `CEPM/` where
      possible. If you have to change an upstream file, add a comment saying *why*
      the code looks the way it does. For example, `runreeds.py` explains that
      the Windows run script is always run by `cmd.exe`, where a trailing `&`
      doesn't background anything.
   3. Show that the fix works: reproduce the problem, apply the fix, and show it's
      gone. Keep a note of exactly what you ran. Save relevant run results to VM-Outputs.
      A Python syntax check or unit test is not a GAMS solve, so if your change could
      affect model behavior, say whether you ran a real case.
   4. If the fix changes model results, talk to the team before finalizing it,
      and record the results in [`batch-log.md`](../batch-log.md).

4. **Update [`known-reeds-issues.md`](../known-reeds-issues.md) and
   [`reeds-to-cepm-log.md`](../reeds-to-cepm-log.md) to reflect the solution.**
   The two files do different jobs. `known-reeds-issues.md` answers "my run
   failed, what is this?" `reeds-to-cepm-log.md` answers "what did we change,
   and what breaks on the next upstream sync?"
   1. In `known-reeds-issues.md`:
      1. Add `(FIXED)` to the end of the entry's heading.
      2. Change **Status** to "fixed", with a one-line description of the fix and
         a pointer to the matching section in `reeds-to-cepm-log.md`.
      3. Add a **Files changed** list.
   2. In `reeds-to-cepm-log.md`, *only if you changed an upstream-owned file*
      (anything outside `CEPM/`):
      1. Add a row to the **Divergence inventory** table for each upstream file
         you changed.
      2. Add a section with the same four subheadings as the others:
         **Description of issue**, **Files changed**, **Reference** (your branch
         name, and a link back to the `known-reeds-issues.md` entry), and
         **What to test in new releases**. That last one is for whoever does the
         next upstream sync. It should tell them how to check whether upstream
         fixed it, and how to confirm our fix still works.
   3. Refer to code by what it is, not by line number. Write "the `#%% User
      warnings` block in `runreeds.py`", not "`runreeds.py:959-967`". Line
      numbers go out of date as soon as anyone edits the file. Our fix to
      `runreeds.py` shifted every line below it, which left citations in four
      other files wrong.
   4. If your fix uncovered a *new* problem, give it its own entry rather than
      folding it into this one. For example, adding logging to
      `diagnostic_plots.py` revealed an error that had been hidden until then.
   5. If you added a new file under `CEPM/`, add a row for it in
      [`CEPM/README.md`](../README.md).

5. **Open a pull request to pull the fix into the working branch.**
   1. Push your branch:

      ```
      git push -u origin fix/example
      ```

   2. Open the pull request against the working branch. Start it as a draft if
      you still have checks to run:

      ```
      gh pr create --repo RMI/ReEDS-CEPM --draft --base dev
      ```

      Always include `--repo RMI/ReEDS-CEPM`. This clone also has upstream's
      repo (`ReEDS-Model/ReEDS`) configured, and without a default set, `gh` may
      try to open the pull request there. Run
      `gh repo set-default RMI/ReEDS-CEPM` once to fix this for good.
   3. In the description, cover what the problem was, what you changed, what you
      tested, and **what you didn't test**. Also list any follow-up work the fix
      surfaced.
   4. Mark the pull request ready for review once you've run the checks you listed
      as outstanding. Then ask a teammate to review it.

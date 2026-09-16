# Upstream sync log

A dated record of every upstream [ReEDS](https://github.com/ReEDS-Model/ReEDS)
sync this fork has done: which branches and commits were involved, what broke
and why, how it was fixed, and whether each entry in
[`reeds-to-cepm-log.md`](reeds-to-cepm-log.md)'s "what to test in new
releases" lists actually needed attention.

This is different from the other two logs. `known-issues.md` is the
symptom-level "my run failed, what is this" index. `reeds-to-cepm-log.md` is
the standing "what does this fork change vs. upstream, and what to re-check"
index — it describes the *current* divergence, and gets edited in place as
patches are added, dropped, or superseded. This file is the opposite: an
append-only history of each sync *event* itself, written once and left alone,
so the next sync has a worked example instead of starting from zero. Add a new
`## Sync N` section at the top for each future sync; don't edit past entries
except to fix an error.

## Sync 1: June 2026 → August 2026 (`2026.06.18` → `2026.08.03`)

**Status:** Merged and validated on `temp-august`; not yet merged to `dev`/`main`.
Also not yet reconciled with `mvp/two-step-runs`, which branched from the same
pre-sync commit and has its own unmerged feature work (see "Open items" below).

### Timeline

| Step | Ref | Date |
|---|---|---|
| Starting upstream release | tag `2026.06.18` (`sync/june-26`) | — |
| Shared merge-base with `upstream/main` | `62f6381e` | 2026-06-23 |
| Starting CEPM branch | `dev`, cut into `temp-dev` at `ad0f56b0` (PR #29 `mvp-scenario` merge) | 2026-08-26 |
| Ending upstream release | tag `2026.08.03` (`sync/august-26`) | — |
| Upstream merged into sandbox branch `temp-august`, then `temp-august` merged into `temp-dev` | `622ceba6` | 2026-08-27 |
| PR #47: `temp-dev` merged back into `temp-august` (the sync "lands") | `16f8e013` | 2026-08-27 |
| Fix-up commits (environment + doc work below) | `129ecdbc`..`b8dd04d8` | 2026-09-10/11 |

`ad0f56b0` is the last commit before this sync started, and is worth keeping
as a reference: it's the commit `mvp/two-step-runs` still sits on, and the one
used as the "pre-sync baseline" for the comparison run described below.
`temp-dev` itself was deleted from the remote sometime after PR #47 merged —
finding `ad0f56b0` again required searching `git log --grep` across the whole
repo, which is exactly the kind of digging this log is meant to save the next
sync from doing. **Record the pre-sync commit hash in this file the day you
cut the sync branch**, before anything gets merged, renamed, or deleted.

### Overview of RMI commits from this sync — what broke, why, how fixed

| Commit | What broke | Why | Fix |
|---|---|---|---|
| *(part of PR #47 itself, not a separate commit)* | `cases_test.csv`'s merge resolution kept RMI's (`temp-dev`'s) version wholesale, silently dropping upstream's own independent additions (`MultiMetricRA` column, `GSw_PRM_StressThresholdMetrics` row, `USA_fast`'s `yearset` edit) | `cases_test.csv` is upstream's own file that both sides edit independently; a "take one side" merge resolution — the default outcome of any ordinary merge tool on a two-sided edit — has no way to know that | `687e758e`: reconciled with a 3-way `pandas` comparison (base `62f6381e` vs. RMI vs. upstream, cell-by-cell — a raw text diff is unreadable here since both sides insert new columns at different positions) |
| `129ecdbc` | Any `uv run`/`runreeds.py` invocation on `temp-august` failed immediately: `ValueError: Your environment is reeds2 and your pandas version is 2.0.3` | Upstream's `environment.yml` moved Python 3.11→3.14 and bumped ~25 packages (notably `pandas` 2.0→3.0, `numpy` 1.26→2.5) as part of the same release; `pyproject.toml`/`uv.lock` hadn't been touched to match | Full realignment to `environment.yml`, resolving 5 distinct blockers along the way: removed `rmi.etoolbox` (pins `pandas<2.4`, flatly incompatible — confirmed unused anywhere in the repo first); dropped the `docs` extra (its packages are never actually installed by anything that runs — the real docs build does its own independent `pip install`); kept `fiona` version-matched to `environment.yml` but platform/version-marker-excluded on Windows+3.14 (no wheel yet, confirmed a Linux wheel exists — a publishing lag, not an incompatibility); bumped `pyproj` 3.6.1→3.8.0 (same wheel problem, no `environment.yml` pin to preserve); pinned `pillow==12.3.*` explicitly (transitive `python-pptx` dependency on a pre-3.14 release that fails to build) |
| `a889d914` | `check_env_sync.py` reported false-positive drift after the above bump: `sphinx<9` and `gamsapi[transfer]` | Its parser (`split_conda_spec`) only recognized `==`/`=` separators, so a range constraint was mis-parsed; it also never stripped a PEP 508 extras bracket before comparing names | Extended the separator regex to `<`,`<=`,`>`,`>=` (version comes back `None`, already treated as "nothing to compare"); added an extras-stripping step to `normalize()` |
| `bce87b39` | `run_cepm.ps1` hard-failed at bootstrap: its Step 4 pin-check hardcoded `3.11` in ~6 places and tried to force a re-pin back to it, which fails outright against `requires-python = "==3.14.*"` | Literal version strings written directly into the script rather than derived from `pyproject.toml` | Parses `requires-python` out of `pyproject.toml` with a regex and pins to whatever it finds — no version literal in the script at all going forward. Also renamed `CONDA_DEFAULT_ENV` `reeds2`→`reeds` (matches `environment.yml`'s `name:`; was not itself blocking anything, just stale) |
| `687e758e` | *(see PR #47 row above)* | | |
| `b8dd04d8` | — (no code break; documentation only) | | Recorded all of the above in `reeds-to-cepm-log.md`, `guidance/UV_MAMBA_GUIDE.md`, and `known-issues.md` |

### Validation performed

- **GAMS 44.4.0 + Python 3.14 compatibility** — the one risk with no existing
  evidence either way (upstream tests on GAMS 49.6.0/51.3.0, not 44.4.0):
  tested directly by reading a real GDX file (1444 symbols) and round-tripping
  a fresh write/read through `gdxpds`. Both succeeded.
- **Full `USA_faster` run to completion** — twice: once in the working
  directory, once from a genuinely fresh `git clone` of `temp-august` *after*
  pushing, to prove the pushed commits work on a clean checkout and not just
  in whatever state the working tree happened to be in.
- **Pre-sync vs. post-sync comparison** — ran `USA_faster` at `ad0f56b0` (the
  exact pre-sync commit) and diffed it against the fresh post-sync clone with
  `compare_cases.py`. Generation (6880.32→6880.94 TWh) and retirements
  (16.42→16.42 GW) were essentially identical — the model is solving the same
  underlying problem — while capacity (−1.8%), system cost (−2.2%), and
  transmission build (+8.3%) shifted by a few percent. That pattern (same
  demand met, different cost-optimal build-out) is consistent with upstream's
  actual `2026.08.03` data/model changes, not an artifact of the Python/package
  bump, since GAMS — not the Python environment — solves the capacity-expansion
  problem. One plotting section (`plot_trans_diff`) threw `KeyError: 2020`
  because `compare_cases.py` was invoked directly without `--startyear` (its
  own default is 2020; CEPM cases start at 2026) — a self-inflicted invocation
  mistake, not a regression; every other slide's independent `try`/`except`
  let the rest of the 44-slide comparison complete normally. `run_cepm.ps1 -x`
  avoids this by auto-deriving `--startyear` from the batch's own `yearset`.

### Implications for `reeds-to-cepm-log.md`'s "what to test in new releases" items

Every upstream-file patch section was checked against `temp-august`'s actual
post-sync code (not assumed from the doc) before this sync was called done:

| RMI patch | Still needed at `2026.08.03`? | Altered by this sync? | Verified |
|---|---|---|---|
| GAMS Error 579 fix (`h5_to_gdx.py`/`b_inputs.gms`) | Yes — GAMS is still pinned 44.4.0 | No | `write_sets_declare_and_load()` and its `$include` call site both intact |
| Census divisions in `fuelcostprep.py` | Yes | No | `val_cendiv` restriction present; `reeds.io.get_dfmap()` still returns a national-scope `cendiv` |
| `recf.py` offshore wind | Yes | No | `else` branch assigning an empty `df_windofs` still present |
| `compare_cases.py` "Flexibly Sited Demand" (`add_to_pptx`) | Yes — upstream hasn't fixed its own typo | No | call site still `reeds.report_utils.add_to_pptx` |
| `report_utils.py` `parse_caselist` | Yes | No | `_caselist[0]` fix present |
| `compare_cases.py` hardcoded `2020` | Yes | No | all 5 sites use the `startyear` variable; see the false-alarm note in Validation above |
| Minor/cosmetic (`reeds2pras` README, `cases_small.csv`) | Yes | No | paths and `endyear` unchanged |
| Gas CAPEX (`dollaryear.csv`, `cases.csv`) | Yes | No | all 3 rows present, `plantchar_gas` `Choices` pattern unchanged |
| Data-center load forecasts | Yes | No | all 5 loadsite files present; `runfiles.csv` template and `GSw_LoadSiteCF`/`Trajectory` switches unchanged |
| `cases_test.csv` reconciliation | N/A — one-time event, not an ongoing patch | This sync's own outcome | See the PR #47 row above |

None of RMI's own patches to base ReEDS files were altered, reverted, or made
redundant by this sync.

### Open items / carried into the next sync

- **`fiona`'s platform marker** — re-check whether a Windows/cp314 wheel has
  shipped yet; if so, drop the marker (see `pyproject.toml`).
- **Gas CAPEX schema** — did not re-verify `gas_ATB_2024_moderate.csv`'s
  columns/units against the new upstream release this cycle; do so before
  trusting the CEPM gas-cost files are still shape-compatible.
- **`mvp/two-step-runs` is still unmerged** and diverged from this same
  pre-sync commit (`ad0f56b0`). A `git merge-tree` dry run confirms it merges
  cleanly with `temp-august` with no textual conflicts, and every load-bearing
  assumption behind its own "what to test" items (`eq_interconnection_queues`,
  `cap_new_out`, `ilr(i)`, `CAP_ABOVE_LIM`, the `runfiles.csv` region-column
  split) still holds against `temp-august`'s actual code. One cleanup item for
  whoever does that merge: `cases_test.csv`'s `USA_fasterish` column ends up
  documented twice in the merged `reeds-to-cepm-log.md` (a terse bullet under
  "Minor and cosmetic" from `mvp`, and the full reconciliation section from
  this sync) — fold them into one before merging.
- **`known-issues.md` vs. `known-reeds-issues.md`** — `mvp/two-step-runs`
  renamed this file (2026-09-04); `temp-august` still uses the old name. Pick
  one before merging the branches.

### Lessons for the next sync

- **Tag or otherwise record the pre-sync commit hash immediately**, before
  merging or branching further — see the `temp-dev`-deletion note under
  Timeline above.
- **Never resolve a two-sided file (`cases_test.csv`, and anything else
  upstream continues to edit) by "take one side."** Do the 3-way `pandas`
  comparison every time, even when it looks like a trivial file.
- **Reconcile `pyproject.toml` against `environment.yml` by actually running
  `uv lock`**, not by reading the diff — every real blocker this sync hit
  (`rmi.etoolbox`, `fiona`, `pyproj`, `pillow`) only surfaced that way.
- **Test the GAMS version this repo actually runs, not the version upstream
  tested on.** A Python/package bump can silently break the `gamsapi`/`gdxpds`
  binding layer against an older GAMS engine even when nothing upstream
  "changed" from upstream's own point of view.
- **Validate from a fresh clone, not just the working tree**, before telling
  anyone else the sync is safe to pull.
- **Re-run the full "what to test in new releases" list against the actual
  post-sync files**, not against what the log already claims — some claims in
  that log were last checked against a different commit than the one you're
  currently on (see the `upstream/main` vs. `2026.08.03` distinction that came
  up reconciling with `mvp/two-step-runs`).

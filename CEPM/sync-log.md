# Upstream sync log

A dated record of every upstream [ReEDS](https://github.com/ReEDS-Model/ReEDS)
sync this fork has done: which branches and commits were involved, what broke
and why, how it was fixed, and whether each entry in
[`reeds-to-cepm-log.md`](reeds-to-cepm-log.md)'s "what to test in new
releases" lists actually needed attention.

This is different from the other two logs. `known-reeds-issues.md` is the
symptom-level "my run failed, what is this" index. `reeds-to-cepm-log.md` is
the standing "what does this fork change vs. upstream, and what to re-check"
index — it describes the *current* divergence, and gets edited in place as
patches are added, dropped, or superseded. This file is the opposite: an
append-only history of each sync *event* itself, written once and left alone,
so the next sync has a worked example instead of starting from zero. Add a new
`## Sync N` section at the top for each future sync; don't edit past entries
except to fix an error.

## Sync 2: August 2026 → September 2026 (`2026.08.03` → `2026.09.21`)

**Status:** In progress. Merge and CEPM adaptations are on PR #80
(`temp_dev` ← `temp_upstream_09.21.26`). The baseline-vs-merged validation
runs, `temp_dev` → `dev`, and `dev` → `main` are still to come.

### Timeline

| Step | Ref | Date |
|---|---|---|
| Starting upstream release (also the merge base) | tag `2026.08.03` (`1515f8ae`) | — |
| Intermediate upstream release (no release notes) | tag `2026.09.08` (`6f70abd9`) | 2026-09-08 |
| Ending upstream release | tag `2026.09.21` (`8a157233`; `sync/september-26`) | 2026-09-17 |
| Pre-sync baseline: `dev` tip, tagged and pushed | tag `pre-sync-2026-09` → `ba6fc3df` | 2026-11-16 |
| Integration branch cut from the tag | `temp_dev` | 2026-11-16 |
| Upstream branch for the PR head (`sync/september-26` kept untouched) | `temp_upstream_09.21.26` | 2026-11-16 |
| Conflicts resolved in the GitHub UI | `c65795b7` | 2026-11-17 |
| CEPM adaptations | `139d8bea`, `17ed65fb`, `e727784e` | 2026-11-18 |
| Sync documentation (this entry and related docs) | PR #80 | 2026-11 |

`dev` did not move between the tag and the merge, so unlike Sync 1 there was
no parallel work stream to reconcile.

### Upstream release contents that mattered to CEPM

The 33 PRs in `2026.09.21` are listed on its
[release page](https://github.com/ReEDS-Model/ReEDS/releases/tag/2026.09.21).
The ones that touched CEPM directly:

| Upstream PR | Change | Effect on CEPM |
|---|---|---|
| #181 | Declare and load each GAMS set/parameter together | Same fix as RMI's GAMS Error 579 patch; works unmodified on GAMS ≥ 44.2.0 (we run 44.4.0). RMI patch retired |
| #12 | `startyear` removed from `cases.csv`; derived from the first `yearset` year and must equal 2010 | `cases_cepm.csv` failed setup until fixed; plotting start year logic rewritten |
| #221 | `this_year` 2025 → 2026; `GSw_StartMarkets` 2026 → 2027 | 2026 becomes a fixed year: no endogenous builds, relaxed load balance, no stress-period iteration, RPS/mandates not enforced. Every `firstyear` shifts a year later (offshore wind 2029 → 2030). Drove the yearset change (separate PR) |
| #190, #221 | Generator database moves to AEO-NEMS 2026 | Large expected changes in existing/planned capacity |
| #172 | Default `yearset` 3-year → 5-year steps | No effect on cases with an explicit `yearset` |
| #164 | `retscen` → `nukeretscen` (integer years, default 80) | No CEPM case set it; docs updated |
| #182, #111 | `GSw_CurtMarket` removed; `GSw_FuelCell` split into gas and H2 fuel cells | No CEPM case used them |
| #157 | Input documentation moved from `docs/sources.csv` to `inputs/*/README.md`; `get_source_deflator_map()` removed | Dollar years now come only from each folder's `dollaryear.csv` (our gas rows already use it); docs updated |
| #208, #165 | actionlint → `kjanat/actionlint` v1.13.0 (third-party fork, "temporary"), `$/` action syntax; checkout v7.0.1 | `python-app.yaml` conflict |
| #176, #87, #191, #197, #199, #200, #206, #167 | Battery lifetime, 2025 NERC regions and PRM, daily gas prices, gas-cc start costs, Clean Air Act adjustment, degradation, distributed PV losses, Canada trade | Expected result changes, to attribute during validation |

`environment.yml` is byte-identical between `2026.08.03` and `2026.09.21`, so
`pyproject.toml`/`uv.lock` needed no changes. Upstream `main` has since bumped
`geopandas` to 1.2 and added `adjustText`; those arrive next sync.

### Conflict resolutions (`c65795b7`)

| File | Resolution |
|---|---|
| `reeds/core/setup/b_inputs.gms` | Took upstream; removed the `CEPM CHANGE` block |
| `reeds/input_processing/h5_to_gdx.py` | Took upstream; also deleted RMI's `write_sets_declare_and_load()`, which sat outside the conflict block. File now identical to upstream |
| `inputs/plant_characteristics/dollaryear.csv` | Kept RMI's 3 `gas-ccgt_CEPM_*` rows and upstream's `h2fuelcell_*` rows. Dropped RMI's copies of the two `fuelcell_ATB_2024_*` rows, which upstream moved further down the file |
| `.github/workflows/python-app.yaml` | Took upstream's `$/` syntax and dropped RMI's `zizmor: ignore` comments. The `ENABLE_GAMS_CI` guard merged cleanly and stays |

All other files merged without conflicts. The `actionlint`, `zizmor` and
labeler checks passed on the PR. `python-app` only runs on PRs into `main`.

### CEPM adaptations

| Commit | Change |
|---|---|
| `139d8bea` | `cases_cepm.csv`: removed the `startyear` row; yearsets → `2010_2026..2032..3`. Same solve years as before, because `dev` already added `startyear` (2010) to the yearset |
| `17ed65fb` | `get_batch_info.py` / `multistep_cases.py`: `--startyear` is now the first `yearset` year after 2010 (via `reeds.inputs.parse_yearset`); comments in `run_cepm.ps1` and `CEPM/README.md` |
| `e727784e` | `h5_to_gdx.py` whitespace aligned with upstream; dropped `cases_cepm.csv`'s `GSw_SkipRAyear` override so CEPM follows upstream's default (2020 → 2024; no effect on CEPM solves) |

### Validation performed so far

- No conflict markers or leftover RMI GAMS-fix code; `dollaryear.csv` has no
  duplicate rows; `h5_to_gdx.py` is identical to upstream.
- `uv sync --extra dev`, `check_env_sync.py` and the `run_cepm.ps1` bootstrap
  pass (GAMS 44.4.0, Julia 1.12.1, Python 3.14).
- `runreeds.py -t` (switch and compatibility checks) passes for all 9
  `cases_cepm.csv` cases and for `cases_RMI-test.csv`.
- pytest: no new failures. `hourlize/tests` (its test data has never been in
  the repo), `test_read_h5py_file` and hourlize's `test_main` fail identically
  at `pre-sync-2026-09`. See `known-reeds-issues.md`.
- **Not yet done:** a GAMS 44.4 model run confirming upstream's #181 replaces
  the Error 579 patch, and the baseline (`pre-sync-2026-09`) vs. merged
  comparison across national, cendiv, regional and state cases.

### Implications for `reeds-to-cepm-log.md`'s "what to test in new releases" items

| RMI patch | Still needed at `2026.09.21`? | Verified |
|---|---|---|
| GAMS Error 579 (`h5_to_gdx.py`/`b_inputs.gms`) | **No** — retired, replaced by upstream #181 | Moved to the log's "Resolved upstream" section; model-run confirmation pending |
| Census divisions in `fuelcostprep.py` | Yes | `val_cendiv` restriction present |
| `recf.py` offshore wind | Yes | `else` branch assigning an empty `df_windofs` present |
| Onshore wind pandas 3 fix (`writesupplycurves.py`) | Yes — upstream still has the bare `[]` | Fix merged cleanly (now line 125) |
| `compare_cases.py` "Flexibly Sited Demand" | Yes | `reeds.report_utils.add_to_pptx` call site present |
| `report_utils.py` `parse_caselist` | Yes | `_caselist[0]` fix present |
| `compare_cases.py` hard-coded `2020` | Yes | No literal `2020` left at the 5 sites |
| `dollaryear.csv` gas rows, `ENABLE_GAMS_CI` guard | Yes | Present after conflict resolution |
| RA plot fixes, minor/cosmetic, data-center load sites, TgCap and queue additions | Yes | Merged cleanly; details to re-check during validation |

Known issues resolved by this sync (moved to `known-reeds-issues.md`'s
"Resolved upstream" section): GAMS Error 579; `startyear` > 2022 crashing
`hydcf.py` (`startyear` must now be 2010); `report_dump.py` reading
`df_capex_init.csv` (`1b3bba93`); `report_dump.py` dropping sets from
`outputs.h5` (`038dd8ed`).

### Open items / carried forward

- **Validation runs** (baseline vs. merged), then `temp_dev` → `dev` and
  `dev` → `main`.
- **Yearset change** to `2010_2026_2030_2033` (`endyear` 2033), agreed in
  response to #221; separate PR with a `CEPM/decisions/` entry.
- **Data that stops at 2032** (separate PR): the data-center load-site
  trajectories (`*_extended_to_2032`) would silently give zero load in 2033,
  because `forecast.py` only extends inputs when `endyear` > 2050; the CEPM gas
  capex forecast reverts to ATB after 2032 (Gas-CC 2,181.7 → 1,127.0).
- **Next sync, upstream `main`:** `geopandas` 1.2 and `adjustText` in
  `environment.yml`; `GSw_QueueConstraintYears` (`0dc01add`) keeps queue
  limits only through `this_year + 3`, which may drop the queue constraint from
  a 2030 first decision year; `cap_limit` renamed to `queue_limit` (`7c39fc98`).
- `fiona`'s Windows/Python 3.14 platform marker: still needed.
- Report the onshore-wind pandas 3 bug upstream.

### Lessons for the next sync

- **Read the diff, not just the release notes.** `startyear`'s removal came in
  #12 ("Adding technology classes") and the `this_year`/`StartMarkets` shift in
  #221 ("Update years to endogenous…"); neither title says so.
- **Dry-run the merge first** (`git merge-tree --write-tree`). It showed 4
  conflicts before any branch existed and made the plan concrete.
- **Resolving in the GitHub UI works for small conflicts**, with two cautions:
  the resolution commit lands on the PR's head branch (so keep a separate
  untouched copy of upstream), and the editor only shows the conflict block,
  not related code that merged cleanly around it.
- **`runreeds.py -t` is a cheap gate.** It validates every case's switches
  against the new `cases.csv` in seconds.
- **Check each CEPM input's last year whenever `endyear` changes.**

## Sync 1: June 2026 → August 2026 (`2026.06.18` → `2026.08.03`)

**Status:** Merged to `dev` via PR #52 (2026-09-22), reconciling with
`mvp/two-step-runs` (already merged to `dev` via PR #49) along the way.
Merged to `main` via PR #78 (2026-11-04).

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
- **`mvp/two-step-runs` merged to `dev` first** (PR #49, `db39de07`), before
  `temp-august` did. `dev` and `temp-august` diverged independently from the
  same commit (`ad0f56b0`) the whole time this sync was in progress — see
  "Landing this sync into dev" below for how the two were reconciled.
- **`known-issues.md` vs. `known-reeds-issues.md`** — resolved as part of that
  same reconciliation: `dev`'s rename (via `mvp/two-step-runs`) was kept,
  `temp-august`'s two content additions were folded into the renamed file by
  hand.

### Landing this sync into dev

By the time `temp-august` was ready to merge, `dev` had already merged
`mvp/two-step-runs` (PR #49) and moved 13 commits further, all from the same
`ad0f56b0` starting point — so this was really two independent efforts
reconciling, not a simple fast-forward. A `git merge-tree` dry run against
`dev`'s actual tip found exactly 2 conflicts, both documentation
(`CEPM/README.md`, `CEPM/known-reeds-issues.md`) and both purely additive on
each side — no redundant or contradicting content, confirmed by mapping every
new section on both sides against the shared base before touching anything.
Zero conflicts in any code or data file (`cases.csv`, `b_inputs.gms`,
`c_model.gms`, `runfiles.csv`, `run_cepm.ps1`) — `dev`'s and `temp-august`'s
changes never touched the same lines.

**Process used:**

1. **Tag both sides before merging**, so "what did this look like right
   before" never requires reconstructing it from a merge commit's parents:
   - `pre-sync-2026-08` on `dev`'s tip immediately before merging (`db39de07`)
   - `sync-2026-08-temp-august` on `temp-august`'s tip as actually validated
     by the `Pacific`/`WECC-SW_baseline` test runs (`f90dea37`) — tagged
     *before* merging `dev` in, so the tag reflects exactly what was tested,
     not a later state that also includes `dev`'s independent work.
   - Both are annotated tags, pushed immediately (a local-only tag is
     invisible to everyone else and easy to lose).
2. **Open the PR (base `dev`, compare `temp-august`) before resolving
   anything.** GitHub allows a PR to be opened with conflicts present — it
   just shows "Can't automatically merge" until they're resolved, and
   pushing a resolution to `temp-august` afterward updates the same PR
   automatically. Considered doing the resolution on a separate branch cut
   from `dev` instead (to keep `temp-august` itself from moving past what
   was tagged), but that turned out to be unnecessary complexity: the tag
   already captures the exact validated state permanently, so `temp-august`
   drifting forward afterward loses nothing.
3. **Resolve locally (`git checkout temp-august && git merge origin/dev`),
   not through GitHub's web conflict editor** — `known-reeds-issues.md` is
   850+ lines with two separate insertion points; editing that in a browser
   textarea is far more error-prone than a real local editor, even though
   GitHub's web editor can technically handle simple text conflicts.
4. **Write an explicit commit message for the resolution**, not git's default
   auto-generated one — state which files were resolved and confirm the
   reasoning (additive, no redundancy) directly in the commit, so `git log`
   carries the "why" without anyone needing to re-derive it from the diff.
5. **Push the resolution to `temp-august`**, which updates the already-open
   PR in place — no need to touch the PR itself.
6. **Merge with "Create a merge commit," never squash or rebase.** This is
   the one step that actually determines whether any of the above survives:
   squash would flatten the resolution commit (and every commit from both
   sides of this sync) into one opaque commit, erasing the exact record
   steps 1-4 exist to create.
7. **Delete `temp-august` after merging.** Every commit on it stays
   permanently reachable through `dev`'s ancestry once merged via a real
   merge commit, so nothing is lost — the tag just keeps a convenient, named
   pointer to the exact validated state, matching the same branch-cleanup
   convention already used for `temp-dev`.

**Landed:** [PR #52](https://github.com/RMI/ReEDS-CEPM/pull/52), merge commit
`eeecc479` (2026-09-22) — joining `dev`'s pre-merge tip `db39de07` (tagged
`pre-sync-2026-08`) with `temp-august`'s final tip `11efac87`, itself built on
top of the validated state tagged `sync-2026-08-temp-august` (`f90dea37`).

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

# Sub-national region support: GSw_ZoneSet x GSw_Region audit

**Status:** 1 of 4 issues fixed (`fix/techs-banned-region-mapping`, merged into `zone-region-audit`); 3 documented, not yet fixed
**Affected versions:** repo state as of commit `fd6fb46a` (branch `mvp-scenario`)
**Symptom:** Outside of the two national z48 cases already validated in `cases_cepm.csv` (`USA_gas_mvp`, `USA_optimized_mvp`), most `GSw_ZoneSet`/`GSw_Region` combinations fail somewhere between `copy_files.py` and the GAMS solve — including the repo's *default* zoneset (z134), used whenever `GSw_ZoneSet` is left blank, as in `NM_optimized_2yrs`/`NM_optimized_3yrs`/`NM_optimized_LLtest`.

## Motivation

`cases_cepm.csv`'s NM-only cases (`NM_optimized_*`) never got past `copy_files.py`, while the USA-wide z48 cases worked. The original hypothesis was a county/zone mapping problem. This audit traces exactly what breaks, why, and how far it generalizes across the other `GSw_ZoneSet` options (z48/z54/z69/z90/z132/z134/z3109/PJMcounty/UTcounty) and `GSw_Region` selections.

## Methodology

Two rounds of throwaway test cases (`cases_zonesweep.csv`, `cases_zonesweep2.csv`; run directories under `runs/zonesweep1_*` and `runs/zonesweep2_*` — all gitignored via `runs/*`, safe to delete):

1. **Round 1** — 6 zonesets (z48, z54, z69, z90, z132, z134), each subset to `st/NM`, run through `copy_files.py` + `mcs_sampler.py` only (`input_processing_only=2`). Cheap (~2-3 min/case), isolates the earliest failure point.
2. **Round 2** — after merging the round-1 fix, 7 configs chosen to cover the remaining zonesets and a variety of `GSw_Region` mechanics (state selection, multi-value `.` syntax, a `nercr/` level selection, a different split state, and the untested `mixed`-resolution `PJMcounty` path), run through the *full* pipeline: `copy_files.py` → ... → `a_createmodel.gms` compile → a single-year LP solve → PRAS → reporting/plotting. `yearset` was pinned to one year (`2026`) specifically so a real solve would finish in minutes rather than hours while still exercising GAMS end-to-end.

Both rounds needed one environment fix first: `runreeds.py`'s generated `.bat` scripts call bare `python`, which only resolves correctly if the repo's `.venv\Scripts` is prepended to `PATH` before invoking `runreeds.py` — otherwise it silently resolves to the broken Windows Store `python.exe` alias, and the case fails before writing any log output (masked further because the batch script's `goto:eof` on error doesn't propagate a nonzero exit code to the launching process).

## Issue 1 — `techs_banned.csv` matched directly against zone names instead of states (FIXED)

**Symptom:** `copy_files.py` crashes with
```
ValueError: No overlapping region columns found between inputs/state_policies/techs_banned.csv and inputs_case/hierarchy.csv
```

**Root cause:** `reeds/input_processing/copy_files.py`'s `read_banned_tech_file()` has a `.csv` branch (`elif fext == '.csv':`) that matches `techs_banned.csv`'s columns — 2-letter state abbreviations — directly against `hierarchy['*r']`, the run's actual zone names. This only coincides when a zoneset never splits a state into multiple zones (true for z48, where `r == st` always). Once any selected state is split into ≥2 zones — true for `NM` under z69/z132/z134, or `CA` under z54/z132/z134/etc. — none of those zone names literally equal a 2-letter state code, `overlap_regions` comes back empty, and the `ValueError` fires. When *some but not all* selected states are split (e.g. z54, z69, z90), the run doesn't crash — it silently drops the ban for the split states instead, since only the unsplit states' names overlap.

Confirmed empirically by checking exactly which states are split per zoneset (`inputs/zones/{z}/hierarchy.csv`, grouped by `st`):

| Zoneset | # states split | Split states |
|---|---|---|
| z48 | 0 | — |
| z54 | 4 | CA, IL, NY, TX |
| z69 | 15 | AR, CA, FL, IL, KY, MI, MO, MS, MT, ND, **NM**, NY, SD, TX, WY |
| z90 | 28 | AR, AZ, CA, CO, FL, GA, ID, IL, IN, KY, MI, MN, MO, MS, MT, NC, ND, **NM**, NV, NY, OH, OR, PA, TX, VA, WA, WI, WY |
| z132 | 38 | AL, AR, AZ, CA, CO, FL, IA, ID, IL, IN, KS, KY, LA, MD, MI, MN, MO, MS, MT, NC, ND, NE, **NM**, NV, NY, OH, OK, OR, PA, SC, SD, TX, UT, VA, WA, WI, WV, WY |
| z134 | 38 | (same list as z132) |

NM is split in z69/z90/z132/z134 (which is why those all reproduce the original bug for `st/NM`) but not in z48/z54 (why those two passed even before the fix).

**Why upstream doesn't have this:** it's not a GAMS-version or upstream-vs-fork drift issue like the [Error 579 bug](GAMS_ERROR_579_INVESTIGATION.md) — upstream (`ReEDS-Model/ReEDS`) never has this code path at all. Upstream ships the main ban list as `techs_banned.yaml`, and its `read_banned_tech_file()` explicitly rejects anything that isn't `.yaml`/`.yml`. RMI's fork diverged in commit `b971d816` ("Working fix for replacing banned techs file", 2026-07-29), which converted the file to a wide CSV (to support the `USA_gas_mvp` case's `file_replacements` swap to `techs_banned_no_new_windsolar_ccs.csv`) and bolted on the `.csv` branch that has this bug. There is no upstream fix to pull — this is a locally introduced format choice, and the fix below reimplements the same state-mapping logic upstream's YAML branch already uses (`hierarchy.loc[hierarchy.st.isin(ban_states)]['*r']`), just adapted to the CSV shape.

**The fix** (`fix/techs-banned-region-mapping`, commit `4d0c2810`): the `.csv` branch now expands each state column onto the run's actual zones via `hierarchy['st']` instead of matching column names against `hierarchy['*r']` directly — mirroring the existing YAML branch. Verified against the real `techs_banned.csv` + `z134/hierarchy.csv` (NM's zones `p31`/`p47` and MD's/OR's bans resolve correctly) and against live `copy_files.py` runs (z132/NM, z54/CA, and PJMcounty/MD all cleared this stage and went on to solve — see Issue 3/4 below).

## Issue 2 — z90's zoneset is missing a required input file (NOT FIXED — data gap)

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: inputs/zones/z90/hierarchy_from134.csv
```
raised in `check_compatibility()` (`reeds.io.get_hierarchy`), before any case directory is even created — this blocks the *entire* launch batch if z90 is included alongside other cases, since `runreeds.py` validates every requested case's switches up front.

**Root cause:** every other zoneset directory (z48, z54, z69, z132, z134) ships `hierarchy_from134.csv` alongside `hierarchy.csv`; `inputs/zones/z90/` only has `hierarchy.csv`. This is a genuine missing-data gap in the repo, not a code bug — not something to patch in `copy_files.py`. z90 is unusable in its current state regardless of region choice, including `country/USA`.

## Issue 3 — z134 (the default zoneset) can't get past `writecapdat.py` (NOT FIXED)

**Symptom:** every z134 test case (`st/NM`, `nercr/WECC_SW`, `st/NM.CO` — three different region selections) failed identically:
```
FileNotFoundError: .../inputs_case/inputs.h5 has no 'ba' key and .../inputs_case/ba.csv does not exist
```
in `writecapdat.py:887` (`reeds.io.read_input(inputs_case, agglevel)`).

**Root cause:** `reeds/spatial.py`'s `get_agglevel_variables()` reads `inputs_case/agglevels.csv` and, for a single-resolution run, reduces it to a scalar `agglevel` — `'ba'` for a fully disaggregated zoneset (z134), `'aggreg'` for an aggregated one (z48/z54/z69/z90/z132). `writecapdat.py`'s single-resolution branch then does `reeds.io.read_input(inputs_case, agglevel)`, which looks for a dataset named literally `agglevel` in `inputs_case/inputs.h5` (or a `{agglevel}.csv` fallback). Inspecting the actual `inputs.h5` files confirms the mismatch:

- z132 case (`agglevel == 'aggreg'`): `inputs.h5` has an `aggreg` key → succeeds.
- z134 case (`agglevel == 'ba'`): `inputs.h5` has `r` but **no `ba` key**, and no `ba.csv` exists → fails.

So `copy_files.py` writes an `aggreg`-named alias of the region set when a zoneset aggregates BAs, but never writes an equivalent `ba`-named alias for the un-aggregated case — even though `get_agglevel_variables`/`writecapdat.py` expect one to exist whenever resolution is `'ba'`.

**Impact — this is not region-specific.** All three z134 cases failed identically regardless of `GSw_Region` (a single state, a multi-BA `nercr` region, and a multi-state selection all hit the exact same error), which is the tell that this is a zoneset-wide gap, not a region-selection issue. Since z134 is the resolution any case gets when `GSw_ZoneSet` is left blank (see `reeds/spatial.py`'s `get_county2zone(GSw_ZoneSet='z134', ...)` default), **this would break a full national z134 run too**, not just sub-national ones. It was never observed before this audit because `NM_optimized_2yrs`/`NM_optimized_3yrs`/`NM_optimized_LLtest` (all blank-`GSw_ZoneSet`, i.e. z134) always hit Issue 1's crash first, earlier in the pipeline, masking this one entirely.

## Issue 4 — PRAS crashes on genuinely single-zone regions (NOT FIXED)

**Symptom:** `z48`/`st/NM` compiled and solved the LP successfully, then failed in the post-solve resource-adequacy step:
```
ERROR: LoadError: BoundsError: attempt to access 0-element Vector{Main.ReEDS2PRAS.Line} at index [1]
  @ run_pras.jl:411
```
surfaced to Python as `run_pras.jl returned code 1` in `reeds/resource_adequacy/ra_calcs.py:164`.

**Root cause:** z48 never splits any state (see Issue 1's table — 0 split states), so `st/NM` under z48 resolves to exactly one zone. With one zone there are zero inter-zone transmission lines, so `ReEDS2PRAS` builds a 0-element `Line` vector — and something at `run_pras.jl:411` unconditionally indexes into it (`[1]`, Julia 1-indexed), assuming at least one line/interface exists. `z132`'s `st/NM` (2 zones: `p31`, `p47`, hence ≥1 internal line) did not hit this and ran cleanly through PRAS and reporting.

**Impact:** specific to genuinely single-zone region selections (zone count depends on both the zoneset and the chosen region, not either alone) — a smaller blast radius than Issues 1 or 3, but relevant for RMI's use case since a single-BA state under an aggregated zoneset (e.g. z48) is exactly the kind of minimal test case one would reach for.

## Compatibility matrix (as tested)

| Zoneset | `st/NM` (or equivalent split-state test) | Notes |
|---|---|---|
| z48 | Compiles + solves; **fails in PRAS** (Issue 4) | Never splits states — immune to Issue 1 |
| z54 | **Full success** (tested with `st/CA`) | NM itself is unsplit in z54; CA is split — confirms Issue 1's fix generalizes |
| z69 | Fails at `copy_files.py` pre-fix (Issue 1); not re-tested post-fix | NM is split in z69 |
| z90 | Blocked — missing `hierarchy_from134.csv` (Issue 2) | Untestable in current state |
| z132 | **Full success** | Confirms Issue 1's fix, and the `aggreg`-resolution path generally |
| z134 (default) | Fails at `writecapdat.py` regardless of region (Issue 3) | Blocks national z134 runs too, not just sub-national |
| z3109 (county) | Not tested — flagged as too granular for this use case | |
| PJMcounty (mixed) | **Full success** (tested with `st/MD`) | First confirmation the `mixed`-resolution path works at all |
| UTcounty (mixed) | Not tested | |

One test-design artifact, not a real bug: all three fully-successful cases (`z132`/NM, `z54`/CA, `PJMcounty`/MD) hit `ValueError: cannot convert float NaN to integer` in `single_case_plots.py`'s `plot_stress_mix`, because the test cases pinned `yearset` to a single year and `pd.Series(years).diff().max()` is `NaN` with only one year. It didn't stop the run or the rest of the plots, and won't occur in any real multi-year case.

## Open follow-ups

- Issue 3 (z134 `ba` key) and Issue 4 (PRAS single-zone) are documented but not yet fixed.
- z69, z3109, and UTcounty were not pushed through the full pipeline — Issue 1's fix should unblock z69's `copy_files.py` stage, but nothing downstream has been verified for it.
- Issue 2 (z90) needs the missing `hierarchy_from134.csv` regenerated or sourced before it's usable at all.

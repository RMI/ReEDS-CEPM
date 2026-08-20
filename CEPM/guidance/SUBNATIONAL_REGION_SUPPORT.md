# Sub-national region support: GSw_ZoneSet x GSw_Region audit

**Symptom:** Outside of the two national z48 cases already validated in `cases_cepm.csv` (`USA_gas_mvp`, `USA_optimized_mvp`), most `GSw_ZoneSet`/`GSw_Region` combinations fail somewhere between `copy_files.py` and the GAMS solve — including the repo's *default* zoneset (z134), used whenever `GSw_ZoneSet` is left blank, as in `NM_optimized_2yrs`/`NM_optimized_3yrs`/`NM_optimized_LLtest`.
**Status:** We identified 5 issues within this repo's codebase; 2 fixed (Issue 1 via `fix/techs-banned-region-mapping`, merged into `zone-region-audit`; Issue 5 directly in `fuelcostprep.py`), 3 documented but not yet fixed (Issues 2, 3, 4)
**Affected versions:** repo state as of commit `fd6fb46a` (branch `mvp-scenario`)


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

**Alternative not taken:** convert `techs_banned.csv` back to a `.yaml` file matching upstream's format exactly, and delete the `.csv` branch of `read_banned_tech_file()` entirely rather than fixing it in place. This would remove the whole bug class (and any future ones like it in that branch) and re-align with upstream instead of carrying a local format divergence. Not pursued here because it touches the input file itself (would need to regenerate the YAML from the current CSV's data, and re-point `file_replacements`/`runfiles.csv` at it) and loses whatever human-editability motivated the CSV conversion in commit `b971d816` in the first place — worth revisiting as deliberate cleanup, but out of scope for a targeted bug fix.

## Issue 2 — z90's zoneset is missing a required input file (NOT FIXED — data gap)

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: inputs/zones/z90/hierarchy_from134.csv
```
raised in `check_compatibility()` (`reeds.io.get_hierarchy`), before any case directory is even created — this blocks the *entire* launch batch if z90 is included alongside other cases, since `runreeds.py` validates every requested case's switches up front.

**Root cause:** every other zoneset directory (z48, z54, z69, z132, z134) ships `hierarchy_from134.csv` alongside `hierarchy.csv`; `inputs/zones/z90/` only has `hierarchy.csv`. This is a genuine missing-data gap in the repo, not a code bug — not something to patch in `copy_files.py`. z90 is unusable in its current state regardless of region choice, including `country/USA`.

**Upstream comparison:** upstream's `inputs/zones/z90/` is missing the exact same file — this isn't an RMI-introduced gap. But it doesn't matter upstream, because `hierarchy_from134.csv` isn't referenced anywhere in upstream's code at all anymore (`git grep hierarchy_from134` on `upstream/main` returns nothing). Upstream's `copy_files.py` builds the hierarchy via `reeds.io.assemble_hierarchy(inputs_case, extra=False)` directly instead of reading that file. Our own `copy_files.py` already has a dormant TODO sitting right above the `hierarchy_from134.csv` read:
```python
## TEMPORARY 20260402: Load the full regions list
## Use the line below once we make the switch
# hierarchy = reeds.io.assemble_hierarchy(inputs_case)
hierarchy = pd.read_csv(
    Path(reeds.io.reeds_path, 'inputs', 'zones', sw.GSw_ZoneSet, 'hierarchy_from134.csv')
)
```
— i.e. this is a migration we've already flagged for ourselves but haven't done. (Also noted in passing: upstream has renamed/replaced `z69` with a `z70` zoneset; not directly relevant to z90 but another sign this area has drifted.)

**Potential solutions:**

- **Option A — derive and add the missing file locally.** `hierarchy_from134.csv` is one row per original 134-zone BA (`p1`..`p134`) giving each BA's `nercr`/`transreg`/`transgrp`/`cendiv`/`st`/`interconnect`/`country`/`usda_region`/`h2ptcreg`/`hurdlereg`/`aggreg` (the last being which z90 zone that BA rolls up into). z90 doesn't ship this, but it does ship `county2zone.csv` (county FIPS → z90 zone). Cross-referencing that against `z134/county2zone.csv` (county FIPS → original BA) would recover the missing BA → z90-zone mapping by grouping counties by BA and reading off each BA's (should be unique) z90 zone; the other descriptive columns can be merged in via `state_groups.csv` the same way `assemble_hierarchy()` already does. This reconstructs the file from real repo data rather than fabricating values, but the "each BA maps to exactly one z90 zone" assumption should be spot-checked before trusting it, and it only fixes z90 — the next missing zoneset would need the same treatment again.
- **Option B — adopt upstream's `assemble_hierarchy()` migration** (i.e., finally do the TODO above). Removes the `hierarchy_from134.csv` dependency for every zoneset, not just z90, matching upstream and permanently closing off this entire class of "missing file" issue. Larger blast radius: `assemble_hierarchy()` doesn't return the same shape as the current `pd.read_csv(hierarchy_from134.csv)` call, so the hierarchy-subsetting/`GSw_Region` logic immediately below it in `copy_files.py` (roughly lines 200–260) would need to be re-validated against the new output shape, and this is the same underlying migration that would likely also resolve Issue 3 below — worth doing once, together, rather than as two separate efforts.
- **Option C — deprioritize z90.** Lowest effort: document it as unsupported in its current state and don't invest further unless a 90-zone resolution is actually needed for RMI's analysis.

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

**Upstream comparison:** the whole `get_agglevel_variables()`/`agglevel_variables` mechanism doesn't exist upstream — not renamed, just absent from `reeds/spatial.py` entirely. Upstream's `writecapdat.py` reads the region set with a plain, unconditional `reeds.io.read_input(inputs_case, 'r')` — no `agglevel`-keyed lookup at all. This mechanism (and the bug in it) looks like an RMI-side addition, presumably for the mixed-resolution (`PJMcounty`/`UTcounty`) support this audit confirmed *does* work (see Issue 4's compatibility matrix) — so it's doing real work, just with a gap for the pure-`'ba'` case.

**Potential solutions:**

- **Option A — write the missing `'ba'` key (minimal, local, recommended shape).** In `copy_files.py`, the region-writing section builds a `comments` dict of hierarchy-level columns (`aggreg`, `cendiv`, `country`, `h2ptcreg`, `hurdlereg`, `interconnect`, `nercr`, `transgrp`, `transreg`, `usda_region`) and writes each to `inputs.h5` via `reeds.io.write_to_inputs_h5(...)` — `'ba'` is conspicuously absent from that dict. It can't simply be added there, though: `hier_sub['ba']` is already dropped a few lines earlier (`hier_sub = hier_sub.drop(['county', 'ba', 'itlgrp'], axis=1)`), right before that same drop is also where `'itlgrp'` gets captured and written out first. The fix is to capture `hier_sub['ba'].drop_duplicates()` at that same point (mirroring the existing `itlgrp` pattern immediately above it) and write it as key `'ba'`, so an un-aggregated run gets a `'ba'`-named alias of its region set exactly the way an aggregated run already gets an `'aggreg'`-named one.
- **Option B — map `'ba'` → `'r'` at the read site(s) instead.** In `writecapdat.py` (and any other caller that keys off `agglevel_variables['agglevel']` the same way — worth a grep before committing to this), treat `agglevel == 'ba'` as "read key `'r'`" rather than looking for a literal `'ba'` dataset, since `'r'` already *is* the BA-resolution region set whenever resolution is `'ba'`. Smaller diff if only `writecapdat.py` needs it, but the mapping would need to be duplicated at every call site that has the same assumption, or centralized in a small helper.
- **Option C — adopt upstream's simplification** and remove `get_agglevel_variables`/`agglevel_variables` in favor of always reading `'r'` directly, matching upstream exactly. This eliminates the bug class rather than papering over it, but it's the riskiest option here: this mechanism is what's currently making the `mixed`-resolution `PJMcounty`/`UTcounty` path work (confirmed via this audit's `PJMcounty`/`MD` test), and it isn't yet understood how — or whether — upstream supports `mixed` resolution at all despite still shipping `PJMcounty`/`UTcounty` zonesets and referencing them in `zoneset_config.yaml`. Removing this without first tracing upstream's equivalent (if any) risks breaking the one region-resolution path already confirmed to work end-to-end.

## Issue 4 — PRAS crashes on genuinely single-zone regions (NOT FIXED)

**Symptom:** `z48`/`st/NM` compiled and solved the LP successfully, then failed in the post-solve resource-adequacy step:
```
ERROR: LoadError: BoundsError: attempt to access 0-element Vector{Main.ReEDS2PRAS.Line} at index [1]
  @ run_pras.jl:411
```
surfaced to Python as `run_pras.jl returned code 1` in `reeds/resource_adequacy/ra_calcs.py:164`.

**Root cause:** z48 never splits any state (see Issue 1's table — 0 split states), so `st/NM` under z48 resolves to exactly one zone. With one zone there are zero inter-zone transmission lines. `ReEDS2PRAS` is vendored directly in this repo (`reeds/resource_adequacy/reeds2pras/src/`, included at runtime by `run_pras.jl` — not an external Julia package), so the exact failing line is locatable: `make_pras_interfaces()` in `reeds/resource_adequacy/reeds2pras/src/models/utils.jl:334` does
```julia
timesteps = first(sorted_lines).timesteps
```
to recover the timestep count from an arbitrary `Line` object, assuming at least one line exists. With zero lines, `sorted_lines` is empty and `first()` on an empty vector throws `BoundsError`, surfacing at its call site in `create_pras_system()` (`reeds/resource_adequacy/reeds2pras/src/main/create_pras_system.jl:54`). `z132`'s `st/NM` (2 zones: `p31`, `p47`, hence ≥1 internal line) did not hit this and ran cleanly through PRAS and reporting.

**Impact:** specific to genuinely single-zone region selections (zone count depends on both the zoneset and the chosen region, not either alone) — a smaller blast radius than Issues 1 or 3, but relevant for RMI's use case since a single-BA state under an aggregated zoneset (e.g. z48) is exactly the kind of minimal test case one would reach for.

**Upstream comparison:** unlike Issues 1 and 3, this one is upstream's own bug rather than RMI-introduced drift. `reeds/resource_adequacy/reeds2pras/src/models/utils.jl` is byte-identical between this fork and `upstream/main` — both resolve to blob `cbb20a69`, checked against `upstream/main` at `bc804315` (2026-08-18) — carrying the same unguarded `timesteps = first(sorted_lines).timesteps`. Upstream has never modified the file since it arrived in the initial `bda96d54` ("copy .gov branch") import, and a blob comparison across every `upstream/*` branch turns up only two that differ at all (`ko/itl_hourly`, `pb/itl_hourly`), whose change is confined to VSC converter capacities in `process_vsc_lines` (`forward_cap`/`backward_cap` wrapped in `fill(..., timesteps)`) and leaves line 334 untouched. Nor is there a single-zone guard anywhere else in upstream's resource-adequacy layer to inherit: upstream's `ra_calcs.py` differs from ours only in commented-out debug scaffolding, and the vendored test suite has no single-region or zero-line case. Notably, upstream *does* already defend against empty component vectors in immediately adjacent code — `isempty` ternaries for storages and gen_stors in `create_pras_system.jl:74-126`, empty-legacy-line checks in `Line.jl:150` and `Interface.jl:145` — so the defensive pattern exists in this codebase; lines and interfaces simply never received the same treatment.

Two consequences for how to act on this. First, there is no upstream fix to pull and no upstream work in flight to wait for — whichever option below is taken puts us ahead of upstream, and Option A in particular (behavior-preserving for every multi-zone case, no new code path) is a clean candidate to contribute back as a PR rather than carry indefinitely as a fork patch. Second, the vendored `reeds2pras/` tree is currently close to pristine: it diverges from `upstream/main` in exactly two files, `README.md` (test-path corrections, cosmetic) and `src/utils/reeds_data_parsing.jl` (8 lines). A local patch to `utils.jl` would be the third divergence, and the one most exposed to being silently clobbered on the next upstream sync — a further argument for upstreaming it. Option C sidesteps that entirely by staying in `ra_calcs.py`, where the surrounding Python RA layer (`stress_periods.py`, `diagnostic_plots.py`) is already substantially diverged, so it would introduce no new class of drift.

**Potential solutions:**

- **Option A — thread `timesteps` through explicitly (smallest, most surgical).** `create_pras_system()` already receives `timesteps::Int` as its own parameter (`create_pras_system.jl:44`, used a line later for `PRAS.Regions{timesteps, ...}`), so `make_pras_interfaces()` doesn't need to derive it from a line at all. Note there are *two* `make_pras_interfaces` methods: the one at `utils.jl:286` takes `regions::Vector{Region}` and does nothing but forward to the one at `utils.jl:324`, which takes `region_names::Vector{String}` and holds the offending `first(sorted_lines)` call. Since `create_pras_system.jl:54` calls the `Vector{Region}` form, `timesteps` has to be added to *both* signatures — the forwarder passing it straight through, the inner method using it directly in place of `first(sorted_lines).timesteps`. That removes the empty-vector access entirely, with no behavior change for any multi-zone case (there, the line-derived value and the passed-in value are already guaranteed equal).
- **Option B — guard the empty case specifically.** `if isempty(sorted_lines) ... construct empty PRAS.Lines/PRAS.Interfaces directly ... else ... (existing logic)`. More localized/defensive than Option A, at the cost of a second code path that duplicates part of the construction logic.
- **Option C — skip PRAS for single-zone runs at the Python level**, e.g. in `ra_calcs.py`, detect a 1-zone region before calling `run_pras` and skip it with a logged warning instead. This avoids touching the vendored Julia code at all, and arguably reflects what PRAS is actually for — its entire value is modeling capacity-credit sharing *between* zones, which is undefined for a literal single-zone island. Tradeoff: single-zone regions would then never get a resource-adequacy metric at all, which is fine for small test regions but would need a conscious decision if a real production analysis ever intentionally selects a single-BA region.

## Issue 5 — `cendivweights.csv` includes census divisions outside the run's own region set (FIXED)

**Symptom:** `a_createmodel.gms` fails to compile with
```
*** Error 170 in .../inputs_case/cendivweights.csv
    Domain violation for element
--- a_createmodel.gms(10) 89 Mb 1 Error
*** Status: Compilation error(s)
```
flagged at line 1 (the header row) of `cendivweights.csv`. Hit on a `nercr/WECC_SW` run under `z132` (case `WECC_SW-test`, run dir `runs/20260820_WECC_SW-test`) — the first test in this audit to select a region large enough to touch a census-division border. The same error, with no root cause identified at the time, was hit earlier by a colleague on a `v20260716_WECC_optimized` run (see `cepm_errorlog.md`).

**Root cause:** `reeds/core/setup/b_inputs.gms` declares `table cendiv_weights(r,cendiv)` domain-checked against the run's own `cendiv` set — for `WECC_SW-test` that set has exactly one member, `Mountain` (confirmed via `inputs_case/hierarchy.csv`). `cendivweights.csv` is generated in `reeds/input_processing/fuelcostprep.py` by `smear(dfzones=dfmap['r'], dfgroups=dfmap['cendiv'], ...)`, a distance-decay weighting between every model region and every census division. The bug: `dfmap['cendiv']` (from `reeds.io.get_dfmap()`) is built from the *original*, national hierarchy, not filtered to the divisions actually present in this run's region set. A border region (`p59`, geographically near the Mountain/West-South-Central boundary) picked up a real, non-negligible decay weight (0.544) toward `West_South_Central` — a division that doesn't exist in this run's `cendiv` set — so it showed up as an extra column in `cendivweights.csv`, which GAMS then rejected as a domain violation.

**Impact:** any sub-national region selection whose zones sit near a census-division border, under any zoneset — not specific to `z132` or `nercr/WECC_SW`. It went unnoticed until now because the zonesets validated so far in this audit (`z132`/`st/NM`, `z54`/`st/CA`, `PJMcounty`/`st/MD`) all happened to select regions sitting well clear of a cendiv boundary, and the two national z48 cases already in `cases_cepm.csv` include every census division by construction, so no out-of-scope column could ever appear.

**Upstream comparison:** inherited, not RMI-introduced. Upstream's current `fuelcostprep.py` (substantially refactored past our fork's version — it adds a `daily_gasprice_multipliers`/`gasreg_cendiv_weights` layer ours doesn't have) still has the identical unrestricted call, `cendivweights = smear(dfzones=dfmap['r'], dfgroups=dfmap['cendiv'], ...)`. Notably, upstream *does* already restrict several sibling outputs in the same script to the run's own `val_cendiv` before writing them out (`ngdemand`, `ngtotdemand`, `alpha` are each filtered via `.isin(val_cendiv)`) — it simply never applied that same pattern to `cendivweights`. That makes this fix a small, self-contained candidate to upstream: it's the same restriction upstream already applies elsewhere in this exact file, just extended to the one output that was missing it.

**The fix** (`reeds/input_processing/fuelcostprep.py`, `smear()` call site): restrict `dfgroups` to the divisions in `val_cendiv` (the run's own `cendiv` set, already loaded earlier in the script for the sibling-output filtering above) before computing weights:
```python
cendivweights = smear(
    dfzones=dfmap['r'],
    dfgroups=dfmap['cendiv'].loc[dfmap['cendiv'].index.isin(val_cendiv)],
    decay_km=float(sw.GSw_GasRegionSmooth),
).round(3)
```
Verified directly against `WECC_SW-test`'s own `inputs_case` data: the unfixed call reproduces the `West_South_Central` column exactly (weights `[0.994, 0.958, 0.883, 0.456, 0.965]` for `Mountain` and `[0.006, 0.042, 0.117, 0.544, 0.035]` for `West_South_Central` across `p27/p29/p31/p59/z28`); the fixed call produces only the `Mountain` column, correctly renormalized to 1.0 for every region.

## Compatibility matrix (as tested)

| Zoneset | `st/NM` (or equivalent split-state test) | Notes |
|---|---|---|
| z48 | Compiles + solves; **fails in PRAS** (Issue 4) | Never splits states — immune to Issue 1 |
| z54 | **Full success** (tested with `st/CA`) | NM itself is unsplit in z54; CA is split — confirms Issue 1's fix generalizes |
| z69 | Fails at `copy_files.py` pre-fix (Issue 1); not re-tested post-fix | NM is split in z69 |
| z90 | Blocked — missing `hierarchy_from134.csv` (Issue 2) | Untestable in current state |
| z132 | **Full success** for `st/NM`; hit Issue 5 on the larger `nercr/WECC_SW` selection (fixed) | Confirms Issue 1's fix, and the `aggreg`-resolution path generally; `st/NM` alone doesn't cross a cendiv border, so Issue 5 only surfaced at the larger region |
| z134 (default) | Fails at `writecapdat.py` regardless of region (Issue 3) | Blocks national z134 runs too, not just sub-national |
| z3109 (county) | Not tested — flagged as too granular for this use case | |
| PJMcounty (mixed) | **Full success** (tested with `st/MD`) | First confirmation the `mixed`-resolution path works at all |
| UTcounty (mixed) | Not tested | |

One test-design artifact, not a real bug: all three fully-successful cases (`z132`/NM, `z54`/CA, `PJMcounty`/MD) hit `ValueError: cannot convert float NaN to integer` in `single_case_plots.py`'s `plot_stress_mix`, because the test cases pinned `yearset` to a single year and `pd.Series(years).diff().max()` is `NaN` with only one year. It didn't stop the run or the rest of the plots, and won't occur in any real multi-year case.

## Open follow-ups

- Issues 2, 3, and 4 each have candidate solutions written up above, but none are implemented yet — this document is a scoping pass, not a patch.
- Issues 2 and 3 both trace back to the same underlying drift: our fork is still on a `hierarchy_from134.csv`-based hierarchy assembly that upstream has already replaced with `reeds.io.assemble_hierarchy()` (our own `copy_files.py` has a dormant `## TEMPORARY 20260402` TODO marking this exact migration). If both get fixed, doing the upstream migration once (Issue 2's Option B / Issue 3's Option C) is likely more valuable than patching each symptom locally (Issue 2's Option A, Issue 3's Option A/B) — but the migration is also the highest-risk option of the three, particularly because it isn't yet known whether it would preserve the `mixed`-resolution (`PJMcounty`/`UTcounty`) support this audit confirmed currently works.
- z69, z3109, and UTcounty were not pushed through the full pipeline — Issue 1's fix should unblock z69's `copy_files.py` stage, but nothing downstream has been verified for it.
- Issue 4's fix (Option A) is self-contained to the vendored `reeds2pras/` code and doesn't interact with Issues 2/3 at all — it can be picked up independently of any decision on the hierarchy-assembly migration.
- Issue 5's fix is a one-line change inherited by upstream too (see its "Upstream comparison") — a good candidate to contribute back, similar in spirit to Issue 4's Option A.
- Any zoneset/region combination not yet run at a large enough spatial extent to cross a census-division border should be considered untested for Issue 5, even where it's listed as "Full success" above for a smaller test region — the bug is about region geography relative to cendiv boundaries, not the zoneset or `GSw_Region` mechanism itself.

# Known issues log

A running index of issues seen in ReEDS-CEPM runs. If your run hits an error, check
here first — it may already be understood, non-fatal, or have a documented fix.
Deeper investigations get their own doc (linked from the relevant entry, and listed
under [Related documents](#related-documents)); this file is the quick-reference
index of symptom → cause → status.

Entries are generalized from whatever run first surfaced them — treat script names
and error text as the pattern to match, not a one-off.

Each entry includes a **Fixed upstream?** note checked against
[ReEDS-Model/ReEDS](https://github.com/ReEDS-Model/ReEDS) tag `2026.08.03` (the
latest tagged release as of this writing, commit `1515f8ae`) — not the tip of
upstream's `main` branch, which may have moved further.

## GAMS 44.4.0 compile failure: `Error 579` in `autocode/b_load_sets.gms` (FIXED)

**Symptom:** `a_createmodel.gms` fails to compile with 16x
```
*** Error 579 in .../autocode/b_load_sets.gms
    Cannot clear a set used as a domain or used in lag/ord operations
```
followed by `*** Status: Compilation error(s)`, immediately after
`copy_files.py`/`h5_to_gdx.py` finish input processing. Hit **every** case that
reached the model-compile step — not specific to any one case's switches.

**Root cause:** `h5_to_gdx.py` auto-generates GAMS snippets that declare every
set/parameter first (`b_declare_sets.gms`), then `$loadDCR` every set afterward
(`b_load_sets.gms`). By the time GAMS reaches `$loadDCR r = r`, `r` has already
been referenced as a domain by a dependent subset (e.g. `offshore(r)`) declared
earlier in the same declare-everything-first pass — and GAMS 44.4.0 refuses to
`$loadDCR` a set once anything else depends on it as a domain. Affects every
primary set with at least one dependent subset/parameter: `r`, `i`, `v`, `e`,
`eall`, `f`, `p`, `wst`, `allt`, `geotech`, `h2_st`, `hintage_char`, `ofstype`,
`pcat`, `pvb_config`, `trtype` — exactly the 16 sets that error.

This is a **GAMS-version incompatibility**, not a logic bug: GAMS 45.6.0's release
notes explicitly fixed `$loadDCR` to stop complaining about this exact case, but
that fix never landed anywhere in the 44.x line, and this repo is pinned to GAMS
44.4.0 (see [tech-limit-options.md](guidance/tech-limit-options.md) and this
repo's GAMS-version policy — don't suggest upgrading GAMS as a fix).

**Impact:** blocked every run before it could even start solving — this is a
hard, total failure, not a degraded/partial one.

**Status:** fixed, on `fix/GAMS-h5-bugfix`. `h5_to_gdx.py` now generates a single
`autocode/b_sets.gms` that declares and `$loadDCR`s each set immediately, one at a
time (primary sets first, then subsets), instead of declaring all sets before
loading any of them; `b_inputs.gms` includes the new file in place of the old
declare-all/load-all pair. Parameters are unaffected (a parameter can never be
used as another symbol's domain) and keep the declare-then-load split. Full
investigation and verification in
[GAMS_ERROR_579_INVESTIGATION.md](guidance/GAMS_ERROR_579_INVESTIGATION.md).

**Files changed:**
- `reeds/input_processing/h5_to_gdx.py` — added `write_sets_declare_and_load()`;
  `main()` now calls it for sets instead of the old declare-all/load-all
  `write_declaration`/`write_gdxread` pair (still used for parameters). Also
  cherry-picked `add v to special_keys` from upstream commit `066d8fe6` while in
  this function (unrelated to the bug, but touches the same code).
- `reeds/core/setup/b_inputs.gms` — includes the new `autocode/b_sets.gms` in
  place of `b_declare_sets.gms`/`b_load_sets.gms`, with `$gdxin` opened first so
  sets can be loaded inline as they're declared.

**Fixed upstream?** N/A in the usual sense — this isn't a code bug upstream could
fix, it's a GAMS-version compatibility gap. Upstream (`ReEDS-Model/ReEDS`) has the
*identical* declare-all-then-load-all structure in `b_inputs.gms`/`h5_to_gdx.py`
(confirmed at tag `2026.08.03` too) — it's not a fork-specific regression. Upstream
just never hits the bug because they test on GAMS 49.6.0/51.3.0, both well past
the 45.6.0 release where GAMS itself patched `$loadDCR`. Since this repo alone is
pinned to 44.4.0, there's no upstream fix to pull — the incompatibility only
exists on our GAMS version, and the fix has to live in this fork.

## Offshore-wind RPS infeasibility for NY/CT (`eq_RPS_OFSWind`) — fix reverted, currently live again

**Symptom:** GAMS solve fails with no feasible/optimal solution; root cause traced
to `eq_RPS_OFSWind` having a contradictory RHS for CT and NY — a state RPS
offshore-wind carve-out target that can't be satisfied because those states have
zero available offshore wind capacity in the run.

**Root cause:** two compounding issues, first hit on the (now-deprecated)
`USA_gas_mvp` case (`country/USA`, `GSw_StateRPS` active) with `GSw_OfsWind`
disabled:
1. The state RPS's offshore-wind carve-out for NY/CT stays active and unmet
   whenever `GSw_OfsWind=0` zeroes out available offshore capacity everywhere —
   `GSw_StateRPS` and `GSw_OfsWind` aren't mutually consistent by default.
2. Separately, `copy_files.py`'s `read_runfiles()` always read the base repo's
   `reeds/input_processing/runfiles.csv`, never a case-specific override, so the
   `file_replacements` switch — meant to let a case swap in a custom input file
   (e.g. a modified banned-tech/policy file to work around #1) — silently did
   nothing. Attempting to fix the policy contradiction via `file_replacements`
   wouldn't have worked without also fixing this.

**Impact:** blocked the `v20260717_USA_gas` run outright (no feasible solution).

**Status:** fixed once, then **reverted — currently live again.**
- Fixed 2026-07-30 in commit `2b95f3d7` ("Bug fix for getting reeds to read the
  case-specific runfiles.csv thereby allowing easier custom file replacement"):
  `read_runfiles()` was changed to prefer a `runfiles.csv` colocated with the
  executing copy of the script, falling back to the base repo copy. The
  triggering case was also given `GSw_StateRPS=0`/`GSw_OfsWind=0` to remove the
  policy contradiction directly.
- Reverted 2026-08-20 in commit `3efc5f9d` ("undo techs_banned and changes to
  copy_files and runfiles"), part of deprecating that case (renamed
  `USA_gas_mvp_NOTE-DEPRECATED` in the immediately preceding commit `37405c2e`)
  and simplifying `copy_files.py`/`techs_banned` handling back toward upstream's
  format. `read_runfiles()` no longer prefers a case-local `runfiles.csv` — it
  unconditionally reads the base repo copy again, exactly as before the fix.

**Live risk today:** lower than it looks, but not zero. `file_replacements` is
`none` for every case in `cases_cepm.csv` right now, and the active
`USA_optimized_mvp` case runs with `GSw_StateRPS`/`GSw_OfsWind` both at their
enabled defaults (`1`) — the combination that avoids the contradiction. The
original trigger (`GSw_OfsWind=0` while `GSw_StateRPS` stays on) was specific to
the abandoned `USA_gas_mvp` "ban most non-gas builds" scenario design, which
isn't planned to be revisited — so this specific contradiction is unlikely to
recur *by accident* under the current case set. It's kept here as a documented
hazard rather than a live alarm: if `GSw_OfsWind` is ever turned off again for
any national/NY-CT-inclusive case, for whatever reason, check `GSw_StateRPS`'s
offshore carve-out first — and note that `file_replacements` isn't currently a
usable workaround path either way, since `read_runfiles()` no longer honors it.

**Files changed (fix, now reverted):**
- `reeds/input_processing/copy_files.py` — `read_runfiles()`'s case-local
  `runfiles.csv` preference (commit `2b95f3d7`), removed by commit `3efc5f9d`.
- `reeds/input_processing/runfiles.csv`, `cases_cepm.csv`,
  `inputs/state_policies/techs_banned*.csv` — related file-replacement plumbing
  for the triggering case, also removed/reverted by `3efc5f9d`.

**Fixed upstream?** N/A for the `read_runfiles()` piece — `file_replacements`
and the case-local-runfiles mechanism it depends on are RMI-fork-only additions,
not present upstream. The `GSw_StateRPS`/`GSw_OfsWind` policy-contradiction risk
itself is a switch-combination hazard, not a code bug, so there's nothing
upstream to check against either way.

## H2 infeasibility in DE (2032) — unfixed, workaround not applied to active case

**Symptom:** GAMS solve fails with no feasible/optimal solution for a solve year
(2032 observed). Diagnosis pointed to a contradiction in Delaware: constraints
force positive hydrogen production (`PRODUCE(H2, electrolyzer, ..., DE, 2032)`)
while DE's regional hydrogen-demand balance equations are fixed to zero across
many timeslices for that same year — production is mandated where demand is
simultaneously forced to zero.

**Root cause:** not actually identified. The investigation in `cepm_errorlog.md`
got as far as isolating *where* the contradiction shows up (DE, 2032, H2
production vs. demand balance) but the specific switch/input creating the
positive lower bound on H2 production was never traced further before the
workaround (below) was applied instead.

**Impact:** blocked the `v20260730_USA_gas_mvp` run (now the deprecated
`USA_gas_mvp_NOTE-DEPRECATED` case) at the 2032 solve year.

**Status:** not fixed — worked around, and the workaround isn't in the current
active case. The response at the time was to turn `GSw_H2` off entirely for that
run rather than fix the underlying contradiction. That workaround isn't reflected
in `cases_cepm.csv` today: `GSw_H2` is blank for every CEPM case, including the
active `USA_optimized_mvp`, so it inherits the repo-wide default `GSw_H2=2`
(regional H2 with storage — i.e. **on**, the same setting that triggered the
original infeasibility). `USA_optimized_mvp` also matches the original failure's
scope and timing exactly: `country/USA` (includes DE) with a `yearset` that
reaches 2032.

**Live risk today:** genuinely unknown, not just unmitigated. `USA_optimized_mvp`
as currently configured has the same switch/scope combination that failed before,
but there's no recent evidence either way — both `v20260818_USA_optimized_mvp`
and `v20260818_TF_USA_optimized_mvp` failed at input processing on the unrelated
`startyear=2026` hydro-CF bug (see the entry above) before ever reaching a solve
year, so neither run tested whether this H2 contradiction still occurs. Unlike
the offshore-wind RPS entry above, this one's trigger was never actually traced
to a specific switch, so there's no basis for assuming it's tied to the abandoned
banned-tech scenario and therefore moot — it could just as easily be a general
latent issue in any national-scope, `GSw_H2=2`, year-2032 run. Recommended next
step: fix `USA_optimized_mvp`'s `startyear` first, then either run it through
2032 as a real test, or set `GSw_H2=0` as a precaution if you'd rather not risk
the solve failing there before finding out.

**Fixed upstream?** Unknown/not checked — the root cause was never isolated to a
specific input or code path in the first place, so there's nothing concrete to
compare against upstream yet. Worth revisiting once the trace is actually done.

## `z134` (the default zoneset) doesn't work

**Symptom:**
```
FileNotFoundError: .../inputs_case/inputs.h5 has no 'ba' key and .../inputs_case/ba.csv does not exist
```
raised from `writecapdat.py:887` (`reeds.io.read_input(inputs_case, agglevel)`), for
any `GSw_Region` selection under z134 — including a full national run, since z134 is
what a case gets whenever `GSw_ZoneSet` is left blank.

**Root cause:** `copy_files.py` writes an `aggreg`-named alias of the region set
when a zoneset aggregates BAs (e.g. z48/z54/z69/z90/z132), but never writes an
equivalent `ba`-named alias for z134's un-aggregated case, even though
`get_agglevel_variables()`/`writecapdat.py` expect a `'ba'`-keyed dataset to exist
whenever resolution is `'ba'`.

**Impact:** blocks every z134 case at `writecapdat.py`, regardless of region
selection. **Leaving `GSw_ZoneSet` blank in a new case is not safe** — it silently
selects z134. Set `GSw_ZoneSet` explicitly to a zoneset other than z134 (e.g. z132)
until this is fixed.

**Status:** not fixed. Full root-cause writeup and candidate fixes (Issue 3) in
[SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md).

**Fixed upstream?** No upstream fix needed — the bug doesn't exist there. The
`get_agglevel_variables()`/`agglevel_variables` mechanism in `reeds/spatial.py`
that this bug lives in is entirely absent from ReEDS-Model at tag `2026.08.03`;
upstream's `writecapdat.py` reads the region set unconditionally via
`reeds.io.read_input(inputs_case, 'r')`, with no `'ba'`-keyed lookup at all. This
looks like an RMI-fork-only mechanism (plausibly added to support the
`mixed`-resolution `PJMcounty`/`UTcounty` zonesets), so there's nothing to pull
from upstream — the fix has to be made locally.

## `z90` zoneset is missing a required input file

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: inputs/zones/z90/hierarchy_from134.csv
```
raised in `check_compatibility()` (`reeds.io.get_hierarchy`), before any case
directory is even created. Because `runreeds.py` validates every requested case's
switches up front, including `z90` in a launch batch alongside other cases blocks
the *entire* batch, not just the z90 case.

**Root cause:** every other zoneset directory (z48, z54, z69, z132, z134) ships
`hierarchy_from134.csv` alongside `hierarchy.csv`; `inputs/zones/z90/` only has
`hierarchy.csv`. This is a genuine missing-data gap in the repo's `inputs/zones/z90/`
directory, not a `copy_files.py` code bug — inherited from upstream, where the same
file is missing but harmless because upstream no longer reads it at all.

**Impact:** `z90` is entirely unusable in its current state, regardless of
`GSw_Region` selection (including `country/USA`).

**Status:** not fixed — a genuine data gap, not yet resolved. Candidate fixes
(reconstruct the file from `county2zone.csv`, or migrate to upstream's
`assemble_hierarchy()` and drop the `hierarchy_from134.csv` dependency entirely) are
written up as Issue 2 in
[SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md). Workaround: avoid
`GSw_ZoneSet=z90` for now, and don't batch it alongside other cases you need to run.

**Fixed upstream?** Not directly, but effectively moot there. `hierarchy_from134.csv`
is missing from `inputs/zones/z90/` at tag `2026.08.03` too — the same underlying
data gap, not RMI-introduced. But it no longer matters upstream, because upstream's
`copy_files.py` doesn't read `hierarchy_from134.csv` at all anymore (no hits
anywhere in the tag's source for that filename) — it assembles the hierarchy via
`reeds.io.assemble_hierarchy()` instead. Our fork still has a dormant
`## TEMPORARY 20260402` TODO in `copy_files.py` marking this exact migration as
not yet done; doing it would close this gap (and Issue 3/z134 above) at the root
instead of patching each symptom.

## `cendivweights.csv` domain violation near census-division borders (FIXED)

**Symptom:**
```
*** Error 170 in .../inputs_case/cendivweights.csv
    Domain violation for element
*** Status: Compilation error(s)
```
flagged at the header row of `cendivweights.csv` during `a_createmodel.gms`
compile, for a sub-national region selection whose zones sit near a census-division
boundary.

**Root cause:** `fuelcostprep.py` generates `cendivweights.csv` via a
distance-decay weighting (`smear()`) between every model region and every census
division in `dfmap['cendiv']` — but `dfmap['cendiv']` is drawn from the *original,
national* hierarchy, not filtered to the divisions actually present in this run's
region set. A border region can pick up a small but non-negligible weight toward a
neighboring census division that isn't part of this run, adding an extra column to
`cendivweights.csv` that GAMS then rejects as a domain violation against the run's
own (smaller) `cendiv` set.

**Impact:** any sub-national region selection whose zones sit near a
census-division border, under any zoneset — not specific to any one `GSw_ZoneSet`
or `GSw_Region`. National cases are immune since they include every census division
by construction; it's easy to miss in testing if your test region happens to sit
well clear of a cendiv boundary.

**Status:** fixed, in `reeds/input_processing/fuelcostprep.py`'s `smear()` call
site — `dfgroups` is now restricted to `val_cendiv` (the run's own `cendiv` set)
before computing weights. As of this writing the fix is a local, uncommitted change
on `mvp-fix/tech-reset` — confirm it's committed/merged before assuming a fresh
checkout of another branch has it. Full writeup as Issue 5 in
[SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md).

**Files changed:**
- `reeds/input_processing/fuelcostprep.py` — the `cendivweights = smear(...)` call
  site: `dfgroups=dfmap['cendiv']` changed to
  `dfgroups=dfmap['cendiv'].loc[dfmap['cendiv'].index.isin(val_cendiv)]`. No other
  files touched.

**Fixed upstream?** No. `reeds/input_processing/fuelcostprep.py` at tag `2026.08.03`
still has the identical unrestricted call — `dfgroups=dfmap['cendiv']`, with no
`val_cendiv` restriction. Same bug, inherited from upstream, not RMI-introduced.
Notably, upstream already restricts several sibling outputs in the same script to
`val_cendiv` (`ngdemand`, `ngtotdemand`, `alpha`) — it just never applied that same
pattern to `cendivweights`. That makes our fix a small, self-contained candidate to
contribute back.

## `recf.py` crashes when offshore wind is disabled (FIXED)

**Symptom:** `reeds/input_processing/recf.py`'s `main()` fails, either with a
`NameError: name 'df_windofs' is not defined` or a downstream `pd.concat` shape
error, whenever `GSw_OfsWind=0`.

**Root cause:** `df_windofs` was only created inside the
`if int(sw['GSw_OfsWind']) != 0:` branch, but is unconditionally referenced later at
`recf = pd.concat([df_windons, df_windofs, df_upv, df_distpv])`. With offshore wind
disabled, `df_windofs` was either undefined or (in an earlier attempt at the fix)
inconsistent in shape/index with the other frames being concatenated.

**Status:** fixed. `recf.py` now has an `else` branch that sets
`df_windofs = pd.DataFrame(index=df_windons.index)` when `GSw_OfsWind` is disabled,
matching the existing pattern already used for `GSw_distpv`/`GSw_CSP` a few lines
below it (empty dataframe aligned to `df_upv.index`). Landed in commit `4d74f94b`
("Handle disabled offshore wind in recf input build"); an earlier attempt
(`3a356d36`) was reverted alongside an unrelated change before this version landed.
If you see this on an older checkout, update `recf.py`/pull the latest `main`.

**Files changed:**
- `reeds/input_processing/recf.py` — added an `else` branch after the
  `if int(sw['GSw_OfsWind']) != 0:` block in `main()`, setting
  `df_windofs = pd.DataFrame(index=df_windons.index)`. No other files touched
  (commit `4d74f94b`); the earlier, reverted attempt (`3a356d36`) touched the same
  single file, then at path `input_processing/recf.py` before the later
  `reeds/`-prefixed repo reorg.

**Fixed upstream?** No. `reeds/input_processing/recf.py` at tag `2026.08.03` has
the identical `if int(sw['GSw_OfsWind']) != 0: df_windofs = ...` block with no
`else` branch — `df_windofs` is still unconditionally referenced later in
`pd.concat([df_windons, df_windofs, df_upv, df_distpv])`, so upstream would hit the
same crash if run with `GSw_OfsWind=0`. Good candidate to contribute back, since
it's the same fix pattern upstream already uses for `GSw_distpv`/`GSw_CSP` a few
lines below.

## `startyear` must be old enough for historical hydro capacity factor data — currently blocking `USA_optimized_mvp`

**Symptom:** confirmed live traceback, from `runs/v20260818_USA_optimized_mvp/gamslog.txt`
and `runs/v20260818_TF_USA_optimized_mvp/gamslog.txt` (both 2026-08-18/19), which
failed identically at `hydcf.py`, right after `copy_files.py`, before ever reaching
model compile or solve:
```
hydcf.py | ... | ERROR | + np.arange(data_endyear+1, model_endyear+1).tolist()
hydcf.py | ... | ERROR | ValueError
hydcf.py | ... | ERROR | : arange: cannot compute length
```
at `assemble_hydcf()` (`hydcf.py:397`).

**Root cause:** `calculate_historical_monthly_regional_cf()` filters the
EIA-plant-generation-derived historical hydro CF data down to
`t >= startyear` (`hydcf.py:166-169`). Historical generation data only exists up
through some past year; if `startyear` is set later than that, the filter empties
out the historical CF dataframe entirely. Downstream in `assemble_hydcf()`,
`data_endyear = hydcf.index.max()` on that now-empty frame returns `NaN` (pandas
doesn't raise on `.max()` of an empty numeric index), and
`np.arange(data_endyear+1, model_endyear+1)` then raises `ValueError` because one
bound is `NaN` — this `arange` crash is the concrete failure mode of the same
empty-historical-data condition described generically below.

Confirmed both in `switches.csv` for the failed runs (`startyear=2026`,
`endyear=2032`, `GSw_Region=country/USA`, `GSw_ZoneSet=z48`) and in
`cases_cepm.csv` today — the `startyear` row is
`startyear,2010,,,,,,2026`, meaning **`USA_optimized_mvp` (the last column) still
has `startyear=2026` set explicitly right now.** `hydcf.py` hasn't changed since
those runs (`diff` against the run's own copied `hydcf.py` is empty), so re-running
`USA_optimized_mvp` as currently configured will fail the same way. This is the
same defect already fixed for `USA_gas_mvp` in commit `fd6fb46a` ("Corrected
cases_cepm -- note that startyear has to be 2010 or hydro capacity factor breaks")
— that fix was never applied to `USA_optimized_mvp`'s own column.

**Open question:** the exact cutoff between "works" (2010, confirmed) and "breaks"
(2026, confirmed) hasn't been isolated — it depends on how recent the EIA hydro
generation data bundled in this repo's inputs actually is, which needs to be checked
directly (e.g. the max year present in the raw hydro generation input file) rather
than assumed. Until that's pinned down, don't set `startyear` later than 2010
without first verifying it against the actual historical data range.

**Status:** not fixed / not fully diagnosed — and, unlike when this entry was first
written, **now confirmed to actively block the current `USA_optimized_mvp` case**
before it can reach `a_createmodel.gms`, let alone solve any year. Fix: change
`cases_cepm.csv`'s `startyear` value for `USA_optimized_mvp` from `2026` to blank
(inherits the repo default of `2010`), the same fix already applied to
`USA_gas_mvp`. Until that's done, `USA_optimized_mvp` cannot be used to test
anything downstream of input processing — including whether the offshore-wind RPS
and DE/H2 issues below still reproduce.

**Fixed upstream?** No — same latent bug. `reeds/input_processing/hydcf.py` at tag
`2026.08.03` has the identical `t >= startyear` filter and the identical
`historical_endyear = historical_monthly_regional_cf.index.get_level_values('t').max()`
in `assemble_hydcf()`. (Upstream's `hydcf.py` has otherwise diverged well past our
fork's version — it adds an entire hydropower climate-adjustment layer ours
doesn't have yet — but that addition doesn't touch this filter.) Inherited, not
RMI-introduced; not something upstream has addressed.

## Postprocessing: `report_dump.py` crashes reading `df_capex_init.csv`

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: '...\inputs_case\df_capex_init.csv'
```
raised from `reeds/results.py`'s `calc_systemcost()`, called from `report_dump.py`'s
`postprocess_outputs()`.

**Root cause:** pipeline ordering bug. `df_capex_init.csv` is generated by
`retail_rate_calculations.py` (via `calculate_historical_capex.py`), but
`report_dump.py` — which needs that file for `calc_systemcost()` — runs *before*
`retail_rate_calculations.py` in the postprocessing sequence.

**Impact:** `postprocess_outputs()` aborts partway through, so the system-cost CSV
output (and anything else queued after `calc_systemcost` in that function) is not
written for the run. Earlier report_dump outputs (e.g. `error_check.csv`,
`error_gen.csv`) are unaffected since they're saved before the crash. The rest of
the postprocessing pipeline (retail rate calcs, health damage calcs, reV handoff,
plotting) still runs — this doesn't stop the run overall.

**Status:** not fixed. Fix would be reordering the postprocessing call sequence (run
`retail_rate_calculations.py` before `report_dump.py`, or have `report_dump.py`
generate/depend on `df_capex_init.csv` itself) — not yet implemented.

**Fixed upstream?** No. `runreeds.py` at tag `2026.08.03` calls `report_dump.py`
before `retail_rate_calculations.py` in the identical order, and `reeds/results.py`'s
`calc_systemcost()` reads `df_capex_init.csv` via the same plain
`pd.read_csv(os.path.join(inputs_case, 'df_capex_init.csv'))` — upstream would hit
the identical `FileNotFoundError` under the same conditions. (Upstream's `main`
branch, past this tag, has since refactored that read to go through
`reeds.io.read_input(case, 'df_capex_init')`, but that only changes the error
message shape — the fallback path still looks for a CSV that hasn't been written
yet, so the underlying ordering dependency remains unresolved even there.)

## `reeds_to_rev.py` can't reach supply curve source files on `\\nrelnas01`

**Symptom:**
```
***Error reading //nrelnas01\ReEDS\Supply_Curve_Data\...\results\..._supply_curve_raw.csv...
FileNotFoundError: [Errno 2] No such file or directory: '...'
```
for one or more of wind-ons, UPV, GeoHydro (any tech whose raw supply curve lives on
that network share).

**Root cause:** not a code bug — the network share path is unreachable or the file
isn't present there from this machine (VPN not connected, drive not mapped, or the
configured path is stale). Confirm by checking whether `\\nrelnas01\ReEDS\...` is
browsable at all from the machine running the case.

**Impact:** built capacity for the affected tech(s) can't be disaggregated for the
reV handoff step, so those reV output files aren't produced. The core ReEDS solve
outputs are unaffected — this only breaks the reV/site-level disaggregation output.
This also cascades into `single_case_plots.py`: without the reV handoff,
`outputs/df_sc_out_{upv,wind-ons,wind-ofs}_reduced.csv` never get written, so the
supply-curve overlay on the VRE-sites maps (`map_VREsites-*`) fails with
`FileNotFoundError` for each missing tech (each caught individually — the run and
the rest of `single_case_plots.py` continue). Confirmed in
`runs/20260821_USA_fasterish/gamslog.txt`.

**Status:** environment issue, not a repo bug. Verify network/VPN access to
`nrelnas01` before assuming this is a code problem.

**Fixed upstream?** N/A — this isn't a code bug to begin with, just local
network/VPN access to an RMI-internal share. Not something upstream code
addresses either way.

## `single_case_plots.py` diagnostic plots fail on single-region / reduced-hierarchy cases

**Symptom:** one or more of the following appear as `<plot function> failed:` with a
traceback, during the final plotting stage — each is caught individually, so the run
completes and later plots still generate:
- `map_translines_all`, `map_translines_vsc`, `map_net_imports`, `plot_max_imports` —
  `ValueError`/`IndexError` from empty-array or scalar-mismatch assumptions.
- `plot_interreg_transfer_ratio`, `plot_interface_flows` — explicit
  `NotImplementedError` ("only one region modeled" / "no interfaces to plot").
- `plot_capacity_offline` — `KeyError` for a region name not present in the run's
  region set (e.g. `'AZ'`; also seen as `'CA'` on a `country/USA`/`z54` run — not
  single-region-specific, just needs the missing region to be absent from whatever
  aggregation the run uses).
- `map_capacity_techs` — `ValueError: list.remove(x): x not in list` for a hardcoded
  tech not present in the run's tech set.
- `map_prm` — `TypeError: 'Axes' object is not subscriptable`, from
  `reedsplots.py`'s `map_prm()` indexing a `plt.subplots()` result that's a bare
  `Axes` (not an array) when only one year is being plotted.

**Root cause:** these plotting functions assume the full national, multi-region,
multi-year model structure (inter-regional transmission, multiple hierarchy levels,
a fixed set of region names, multiple year subplots). A reduced-region or
single-year test case violates one or more of those assumptions. Some failure modes
are explicitly guarded (`NotImplementedError`, working as intended); others are
unguarded code bugs that happen to only trigger in this configuration (`map_prm`,
`map_capacity_techs`, `plot_capacity_offline`).

**Impact:** the corresponding diagnostic maps/plots are missing from the run's
`outputs` folder. Core solve outputs and CSV results are unaffected.

**Status:** known, not fixed. See [SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md)
for the broader audit of sub-national/reduced-region behavior in this repo,
including a related single-year plotting NaN in `plot_stress_mix`.

**Fixed upstream?** Mixed, checked individually against `reeds/reedsplots.py` at
tag `2026.08.03`:
- `map_prm`'s `ax[coords[year]]` indexing and `map_capacity_techs`'s unguarded
  `techs.remove('Remove')` are byte-identical to our fork at the tag — same bugs,
  not RMI-introduced, not fixed upstream.
- `plot_interreg_transfer_ratio`/`plot_interface_flows`'s explicit
  `NotImplementedError` guards are present at the same call sites in the tag too —
  these are intentional upstream guards, not bugs to fix.
- `plot_capacity_offline`: confirmed root cause, no hardcoded literal involved.
  `reedsplots.py`'s `plot_capacity_offline()` builds `regions` from
  `dftemp['min'].columns.tolist()` (an unfiltered/broader temperature-data region
  list) and then indexes `capacity_offline[region]` — but `capacity_offline`'s
  columns are the run's own, narrower region set, so any region present in the
  temperature source but absent from the run's aggregation raises `KeyError`. Seen
  live as `KeyError: 'CA'` in `runs/20260821_USA_fasterish/gamslog.txt` (a
  `country/USA`/`z54` run) — different region than the original `'AZ'` case,
  confirming it's this systemic region-list/column-set mismatch, not one bad
  literal. `reedsplots.py`'s temperature/region-aggregation code has been
  substantially rewritten between tag `2026.08.03` and our fork (different
  intermediate variables, different level-mapping logic), so it's unconfirmed
  whether upstream's version hits the identical failure, but the same underlying
  pattern exists in both versions' structure. Fix would be intersecting `regions`
  with `capacity_offline.columns` before the plot loop; not yet implemented.
- `map_translines_all`, `map_translines_vsc`, `map_net_imports`, `plot_max_imports`
  weren't individually diffed against the tag — unconfirmed either way.

## bokehpivot HTML report: every map-type section fails on an aggregated zoneset

**Symptom:** in the `reeds-report`/`reeds-report-reduced` `report.html`/`report.log`
output, every map-based section — "Final Wind/PV/CSP/Biopower/Geothermal/Hydro and
Canadian Import/Pumped-hydro/Battery Storage Capacity (GW)", "Final Regional Energy
Price ($/MWh)", etc. — is silently missing, each logged in `report.log` as
`***Error in section N...` followed by:
```
File ".../postprocessing/bokehpivot/core.py", line 1812, in create_map
    height=int(height),
ValueError: cannot convert float NaN to integer
```
Non-map chart types (national bar/line totals) for the same underlying data render
fine — e.g. "Capacity (GW)" (national) succeeds while "Final Wind Capacity (GW)"
(map) fails immediately after it. Confirmed in
`runs/20260821_USA_fasterish/outputs/reeds-report/report.log` (sections 24, 36, 37,
39–44), a `country/USA`/`z54`/`GSw_RegionResolution=aggreg` run.

**Root cause:** `create_maps()` (`postprocessing/bokehpivot/core.py:1667-1680`) reads
region boundary polygons from `postprocessing/bokehpivot/in/gis_rb.csv` — keyed to
raw, un-aggregated BA IDs (`p1`, `p2`, ...) — then filters it to
`region_boundaries['id'].isin(full_rgs)`, where `full_rgs` are the region labels
actually present in this run's output data. Under an aggregated zoneset
(`GSw_ZoneSet=z48/z54/z69/z90/z132` with `GSw_RegionResolution=aggreg`), those
labels are the zoneset's own aggregated zone names, not `p1`...`p134` — none of
them match anything in `gis_rb.csv`, so the filter empties `region_boundaries`.
`.max()`/`.min()` on the empty frame return `NaN`, which propagates through
`aspect_ratio = (y_max-y_min)/(x_max-x_min)` into `height=int(height)` at
`core.py:1812`, raising. Only `gis_rb.csv` (raw BA) and `gis_st.csv` (state) exist
in `postprocessing/bokehpivot/in/` — no boundary file for any aggregated zoneset.
Same underlying family as the aggregated-zoneset assumptions audited in
[SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md) (e.g. the
z134 `'ba'`-key bug above), but this specific bokehpivot map failure isn't covered
there yet.

**Impact:** every map-type section of the bokeh HTML/Excel report is missing for
any aggregated-zoneset run — not just z54. Non-map (bar/line/national) sections in
the same report are unaffected, and the run itself, `single_case_plots.py`, and all
other postprocessing steps complete normally; this only degrades the bokeh report's
map coverage.

**Status:** not fixed. Candidate fixes: generate a `gis_<zoneset>.csv` boundary file
per aggregated zoneset (dissolve/union the `gis_rb.csv` BA polygons per the
zoneset's BA-to-zone membership), or have `create_maps()`/`create_map()` detect an
empty `region_boundaries` after filtering and skip the map with a logged message
instead of crashing on `NaN`.

**Fixed upstream?** Not checked yet.

## Cosmetic warnings safe to ignore

- **`copy_files.py`** — pandas `DtypeWarning: Columns (N) have mixed types` while
  reading an input CSV. Cosmetic; doesn't affect the data actually loaded.
- **`hourly_repperiods.py`** (via `hourly_plots.py`) — `UserWarning: The
  GeoDataFrame you are attempting to plot is empty` followed by
  `IndexError: index 0 is out of bounds for axis 0 with size 0`. Happens when a
  representative-period map has nothing to plot for the run's region set (e.g. a
  reduced-region case). Diagnostic image only; doesn't affect model results.

## Related documents

- [GAMS_ERROR_579_INVESTIGATION.md](guidance/GAMS_ERROR_579_INVESTIGATION.md) — GAMS 44.4.0
  `$loadDCR`/domain-set compile failure in `autocode/b_load_sets.gms` (fixed).
- [SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md) — audit of
  `GSw_ZoneSet`/`GSw_Region` combinations, covering several zoneset-specific
  failures (`techs_banned.csv` region matching, missing `hierarchy_from134.csv` for
  z90, `writecapdat.py`'s missing `'ba'` key for z134, PRAS crashing on single-zone
  regions, `cendivweights.csv` domain violations near census-division borders).

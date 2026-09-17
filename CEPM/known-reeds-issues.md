# Known ReEDS issues

A running index of things that are **broken, missing, or surprising in the model
code itself** — ReEDS and this fork's changes to it. If your run errors, crashes,
silently drops an output, or fails a check, look here first: it may already be
understood, non-fatal, or have a documented fix. Deeper investigations get their
own doc (linked from the relevant entry, and listed under
[Related documents](#related-documents)); this file is the quick-reference index of
symptom → cause → status.

**Scope.** This file is about the *machinery*: a script that raises, a GAMS
equation that goes infeasible, a missing input file, a plot that can't handle our
region set. Issues with a *result* — a scenario configured wrong, an input we
don't trust, a modelling choice we want to revisit — belong in
[`batch-log.md`](batch-log.md) against the batch that surfaced them. The dividing
question is whether a fresh clone of the repo would hit it.

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

## `GSw_GrowthAbsCon=1` makes the **final** solve year infeasible (`eq_growthlimit_absolute`)

**Symptom:** with `GSw_GrowthAbsCon=1`, every solve year runs normally until the
last modeled year, which fails:
```
**** MODEL STATUS      4 Infeasible
Row 'eq_growthlimit_absolute(PV,2032)' infeasible, all entries at implied bounds.
*** Error at line 221291: Execution halted: abort 'Model did not solve to optimality'
```
followed by `3_solve_oneyear.gms failed with return code 3`. Only fires when
`GSw_GrowthConLastYear` is ≥ the last modeled year, which is why the repo-default
`GSw_GrowthConLastYear=2026` never trips it. Note the batch **still exits 0** (see
Impact below).

**Root cause:** `eq_growthlimit_absolute` (`c_model.gms:1088-1102`) sizes its
per-year allowance from the gap to the **next** modeled year:
```gams
(sum{tt$[tprev(tt,t)], yeart(tt) } - yeart(t)) * growth_limit_absolute(tg) =g= sum{...INV...}
```
`tprev(t,tt)` means "tt is the year before t" (`b_inputs.gms:1027`, `1053-1055`),
so `tprev(tt,t)` selects the year *after* `t`. In the last modeled year no such
`tt` exists, the sum collapses to 0, and the coefficient becomes `-yeart(t)` — so
the constraint reads `INV ≤ -yeart(t) × growth_limit_absolute(tg)` against
`INV ≥ 0`. There is no slack variable, so it's infeasible rather than tight.
For `tg='pv'` in 2032 that RHS is 2032 × 28,582 = **58,078,624**, which matches
the observed `5.80786e+07` exactly.

`yearweight` (`b_inputs.gms:5573-5574`) uses the identical expression and then
explicitly patches the last year; `eq_growthlimit_absolute` never got that patch.

**Impact:** blocks any run that turns on the absolute growth constraint through
its own final year — which is exactly what
[tech-limit-options.md](guidance/tech-limit-options.md) used to recommend for
CEPM (that recommendation has since been withdrawn and corrected). **The failure
is easy to miss:** `runreeds.py` prints *"…has finished"* and returns exit code
0 despite the aborted solve, so `run_cepm.ps1` reports success. Check for
`outputs/outputs.h5` and a `neue_<endyear>i0.csv` rather than trusting the exit
code — the missing final-year `neue` file is what first flagged this.

**Status:** not fixed; understood, with two ways around it.
- **Workaround (keeps Option 3):** add a sacrificial final solve year, e.g.
  `yearset=2026..2035..3` with `endyear=2035`, leaving
  `GSw_GrowthConLastYear=2032`. The coefficient only needs *some* later modeled
  year to exist, so 2032's gap goes from −2032 to +3. **Confirmed live** in
  `runs/v20260901t0b_WECC-SW_t0bsacrificial`: same config as the failing run
  except for the horizon, and 2032 solves to `MODEL STATUS 1 Optimal`. Both runs
  generate exactly 3 `eq_growthlimit_absolute` rows in 2032, so the constraint is
  live rather than silently dropped. Costs one extra solve year and requires
  truncating all reporting at 2032, since 2035 is unconstrained and meaningless.
- **What CEPM actually does instead:** the purpose-built cumulative caps
  (`GSw_CEPM_TgCap`, `eq_cepm_tg_cap_sys`/`_reg`), which are cumulative rather
  than per-year and so have no final-year arithmetic at all. Option 3 has three
  further limitations for a ceiling use case (no year index, MW_dc vs MW_ac, no
  first-year floor) documented in
  [two-step-re-limited-runs.md](guidance/two-step-re-limited-runs.md).

A genuine fix, if we ever want Option 3 itself to work, is a one-line `tlast`
fallback in the equation mirroring what `yearweight` already does. Not applied —
we're not using the mechanism.

**Verified:** 2026-09-01, two independent ways. (1) A ~40-line standalone GAMS
file replicating `b_inputs.gms:1049-1055` and the equation's LHS over a CEPM
solve-year set reproduces the infeasibility in 0.3 s. (2) A live run,
`runs/v20260901t0_WECC-SW_t0growthcon` — `WECC-SW_baseline`'s exact config plus
`GSw_GrowthAbsCon=1`/`GSw_GrowthConLastYear=2032` — gave 2026 Optimal, 2029
Optimal, 2032 Infeasible, with CPLEX's conflict refiner naming the single
offending row.

**Fixed upstream?** No. `reeds/core/setup/c_model.gms` at tag `2026.08.03` has
the byte-identical expression with no `tlast` guard, and
`GSw_GrowthAbsCon`/`GSw_GrowthConLastYear` are unchanged in `cases.csv` — same
latent bug, inherited, not RMI-introduced. It stays latent upstream because
`GSw_GrowthConLastYear` defaults to 2026 while upstream runs end in 2050, so the
equation is never generated in the final year. Good candidate to contribute back,
since the fix pattern (`yearweight`'s `tlast` override) already exists a few
thousand lines away in the same codebase.

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
before computing weights. Committed in `4e943cdc` and present on `dev` and the
`mvp/*` branches, but **not yet on `main`** — a checkout of `main` still has the
bug. Full writeup as Issue 5 in
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

## `startyear` must be old enough for historical hydro capacity factor data

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

Confirmed in `switches.csv` for the failed runs (`startyear=2026`,
`endyear=2032`, `GSw_Region=country/USA`, `GSw_ZoneSet=z48`), and at the time in
`cases_cepm.csv`, whose `startyear` row carried an explicit `2026` in the
`USA_optimized_mvp` column. `hydcf.py` has not changed since those runs (`diff`
against the run's own copied `hydcf.py` is empty), so the case would have failed
the same way on any re-run. This was the same defect already fixed for
`USA_gas_mvp` in commit `fd6fb46a` ("Corrected cases_cepm -- note that startyear
has to be 2010 or hydro capacity factor breaks"); that fix had never been applied
to `USA_optimized_mvp`'s own column.

**~~Open question~~ — ANSWERED 2026-09-03: the cutoff is 2022.** The historical
hydro data bundled in this repo covers **2007-2022**, confirmed directly on both
files `hydcf.py` reads, as staged into `runs/v20260902t7_WECC-SW_baseline`:

```
inputs_case/net_gen_existing_hydro.csv   min t 2007, max t 2022
inputs_case/cap_existing_hydro.csv       min t 2007, max t 2022
```

So `startyear` **must be ≤ 2022**; at 2023 or later the `t >= startyear` filter
empties the frame and the `arange` crash above is guaranteed.

Note the practical limit is lower than the hard one: at `startyear = 2022`
exactly one year of data survives, so hydro capacity factors would be derived
from a single year rather than sixteen — no crash, but a silent quality loss.
And `startyear` is not a free knob for other reasons either — it also redraws the
existing-vs-prescribed capacity boundary in `writecapdat.py`, so two runs with
different `startyear` values are not comparable on new-capacity metrics. See
[interconnection-queue-and-prescribed-builds.md](guidance/interconnection-queue-and-prescribed-builds.md)
§5.3 for the full set of traps, and for why adding an early *solve year* is the
better lever when the goal is to spread out prescribed builds.

**Status: worked around, 2026-09-04.** `cases_cepm.csv`'s `startyear` value for
`USA_optimized_mvp` is now blank, so the case inherits the repo default of `2010`
— the same fix already applied to `USA_gas_mvp`. That unblocks input processing;
it does not fix the underlying script, which still empties the frame silently and
then dies at an unrelated `arange` rather than saying what went wrong. Keep this
entry: the trap is live for any new case that sets `startyear` past 2022.

`USA_optimized_mvp` has not been re-run since the change, so whether the
offshore-wind RPS and DE/H2 issues below still reproduce remains untested — the
`startyear` failure had been masking both.

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

## `compare_cases.py` crashes when comparing cases via a shared-prefix glob (`TypeError` in `parse_caselist`) (FIXED)

**Symptom:**
```
TypeError: expected str, bytes or os.PathLike object, not list
```
raised from `reeds/report_utils.py`'s `parse_caselist()` (`os.path.basename(_caselist)`), called from `compare_cases.py` right after argument parsing, before any case data is loaded. Hit every time `compare_cases.py` is invoked with a single shared-casename-prefix argument (e.g. `runs/<BatchName>_`) and no explicit `--titleshorten` — exactly how `run_cepm.ps1`'s `-x/--compare-cases` step calls it.

**Root cause:** in the prefix-glob branch of `parse_caselist()`, when `titleshorten` is left at its default (falsy), the function derives one from the length of the prefix's basename — but passes the whole `_caselist` list to `os.path.basename()` instead of `_caselist[0]`, the single string it actually expects.

**Impact:** blocked `compare_cases.py` immediately for this invocation style, before generating any output. Non-fatal to the overall batch — `run_cepm.ps1` already treats a `compare_cases.py` failure as a warning, not a thrown error — but the comparison report was never produced.

**Status:** fixed.

**Files changed:**
- `reeds/report_utils.py` — `parse_caselist()`: `os.path.basename(_caselist)` changed to `os.path.basename(_caselist[0])`.

**Fixed upstream?** No. `reeds/report_utils.py` at tag `2026.08.03` has the byte-identical line — same bug, inherited, not RMI-introduced. Good candidate to contribute back.

## `compare_cases.py` hardcodes year 2020 in several plots instead of using `--startyear` (FIXED)

**Symptom:** several plots/slides fail independently — each caught by the script's own per-section `try`/`except`, so the rest of the report still generates — whenever a batch's model years don't include 2020 (e.g. a `yearset` starting at 2026):
```
ValueError: 2020 is not in list
```
from `reeds/plots.py`'s `annotate()`, via the "Transmission at Different Resolutions" slide, and
```
KeyError: 2020
```
from `reeds/reedsplots.py`'s `plot_trans_diff()` (`tran_out[case].pivot(...)[subtract_baseyear]`), via the "Transmission maps" slide.

**Root cause:** `compare_cases.py` already resolves a `startyear` variable from its `--startyear` argument and uses it correctly almost everywhere, but five call sites still had a literal `2020`: two `plots.annotate(...)` calls and one `df[case][2020]` lookup in the transmission-resolution slide, plus `subtract_baseyear=2020` in two of the transmission-maps calls. Any batch whose cases don't happen to include exactly year 2020 among their solve years hits one of these — which is any CEPM case, since `cases_cepm.csv`'s `yearset` values all start at 2026.

**Impact:** the affected slides/plots are silently missing from the `.pptx` for any such batch; the rest of the comparison report is unaffected.

**Status:** fixed — all five sites now use the existing `startyear` variable instead of a literal `2020`. Surfaced while wiring up `run_cepm.ps1`'s new `-x`/`--compare-cases` auto-detected `--startyear` (see [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md)), which made `--startyear` actually vary per batch for the first time instead of always sitting at its 2020 default.

**Files changed:**
- `postprocessing/compare_cases.py` — replaced the five hardcoded `2020` literals with the existing `startyear` variable. Also corrected a stale `### Annotate the 2020 value` comment on a nearby line that was already using `startyear` correctly.

**Fixed upstream?** No. `postprocessing/compare_cases.py` at tag `2026.08.03` has identical hardcoded `2020` literals at all five sites — same bug, inherited, not RMI-introduced. Doesn't surface upstream by default because upstream's own default `--startyear` is also 2020, so it only breaks for a start year other than 2020 — which is what every CEPM case uses.

## `runreeds.py` reports success on a failed case, and hangs on a multi-case `-s`

Two separate behaviors, both of which break unattended/batch automation rather
than any single run. Grouped because anyone scripting `runreeds.py` hits both.

**Symptom 1 — silent failure.** A case's solve aborts (infeasible year, GAMS
`abort`, `3_solve_oneyear.gms` returning 3), yet `runreeds.py` prints
*"…has finished"* and returns **exit code 0**, so `run_cepm.ps1` reports success
and any wrapper proceeds as if the run were fine. Seen at least twice: the
`GSw_GrowthAbsCon` final-year infeasibility (entry above,
`runs/v20260901t0_WECC-SW_t0growthcon`) and the `GSw_CEPM_TgCap` empty-cap-files
guardrail (`runs/v20260902t5b_WECC-SW_limitre`).

**Symptom 2 — interactive hang on the worker count.** With more than one case
requested, `runreeds.py` calls
`WORKERS = int(input('Number of simultaneous runs [positive integer]: '))`
(`runreeds.py:987`) unless `--simult_runs`/`-r` was given. A single case
short-circuits to `WORKERS = 1` with no prompt (`runreeds.py:979-981`), so this
only appears once a batch has two or more — where it blocks forever in a
background, CI, or non-interactive shell with no visible prompt.

**Symptom 3 — interactive hang on `cleanup_level`.** `runreeds.py:959-967`
prints an R2X warning and blocks on `input('\nProceed? y/[n]: ')` — defaulting
to `n`, which `quit()`s — whenever **any** case has `cleanup_level >= 1` and
`--skip_checks`/`-f` was not passed. Two details make this nastier than it
looks: it fires at launch, before any run starts; and with `-s/--single` the
ignored cases are **not** dropped from `df_cases` first
(`runreeds.py:899-905`), so the check scans *every* column in the cases file,
not just the ones being run. A single `cleanup_level=2` on an unrelated,
ignored case therefore kills an otherwise valid batch. Note this is the
*launch-time* check only — the per-case cleanup that `runreeds.py` schedules at
the end of a run passes `--force --quiet`, so `cleanup_files.py`'s own
confirmation prompt never fires.

**Root cause:** neither is a bug exactly — `runreeds.py` was written for
interactive use, where a failed case is visible in its own console window and a
prompt is answerable. Both assumptions break under a wrapper.

**Impact:** the first is the dangerous one. A wrapper that trusts the exit code
will happily consume a partial run's outputs — which is precisely what the
two-step workflow's harvest step would have done, producing a silently wrong
capacity ceiling for the constrained case.

**Status:** not fixed upstream-side; worked around in `run_cepm.ps1`.
- **Check for `outputs/outputs.h5`, not the exit code.** `run_cepm.ps1 -m`
  gates phase A on that file existing before harvesting anything, and throws with
  an explicit message if it is missing. A `neue_<endyear>i0.csv` check is a useful
  second signal — its absence is what first flagged the T0 failure.
- **Always pass a worker count for multi-case invocations.** `-m` supplies
  `--simult_runs 2` for its two-case phase B unless the caller gave one. Note the
  wrapper-specific trap: a *caller-supplied* `-r` is swallowed by PowerShell (it
  is a unique prefix of `run_cepm.ps1`'s own `$RunbatchArgs` parameter) and
  `--simult_runs N` fails argparse through the same path — but arguments the
  script builds into an array itself reach `runreeds.py` intact.

**Fixed upstream?** No. `runreeds.py` at tag `2026.08.03` has the identical
`start /wait` launch with no per-case return-code check, and the identical
`input()` prompt at the same branch. Inherited, not RMI-introduced.

## `z_rep` is dominated by the interconnection-queue penalty and does not match `systemcost.csv`

**Symptom:** a CEPM run's early-year objective values look implausibly large and
cannot be reconciled against reported system cost. For
`runs/v20260902t7_WECC-SW_baseline`: `z_rep(2026)` is **$295.6bn** while the
pvf-weighted sum of `systemcost.csv` for 2026 is **$68.9bn**. Nothing in
`systemcost.csv` accounts for the difference.

**Root cause:** the gap is the interconnection-queue penalty. Exceeding
`cap_limit` is *allowed* — `CAP_ABOVE_LIM` absorbs it — but costs
`cap_penalty(tg)`, a flat **$10,000,000/MW** for every tech group, charged in
every modeled year because the constraint is cumulative. In 2026 that is
**$226.7bn, or 76.7% of the objective** (65.4% in 2029; zero in 2032, because
the queue data ends in 2030 and the constraint is not generated). The penalty is
in `Z` via `d_objective.gms:47` but appears in **no** `systemcost.csv` category —
`report.gms` introduces it only at line 1745, inside the `error_check('z')`
reconciliation.

Note `error_check('z')` reconciles only the **final** solve year, where the
penalty is zero — so a clean `error_check` does not indicate the earlier years
are penalty-free.

**Impact:** not a run failure, but larger than it first appears. It makes
`z_rep` unusable as a cost figure, and it does not cancel between cases with
different load (baseline $226.7bn vs data-center cases $298.8bn).

**It also changes the physical buildout** — measured, not inferred. Re-running
the same batch with the penalty disabled (`GSw_CapPenaltyMult=0.000001`) shifts
WECC-SW by **−14.9% PV, +12.6% onshore wind, +157.6% h2**, and moves the
two-step `_limitre` vs `_optimized` gap from +33.4% to **+43.4%**. An earlier
version of this entry said the penalty had no effect on buildout because ~94.5%
of it falls on prescribed capacity; that quantity split is right but the
inference was wrong. The active channel is the per-MW surcharge on *marginal*
builds in cells already over their limit, which bites in every year — most
visibly on onshore wind in `p31`, whose violation persists while PV's clears.

**Status:** understood, not changed. Use `systemcost.csv` for cost reporting and
treat `z` as an optimization artifact. Full write-up — including the structural
cause (CEPM's 2026 solve absorbs 16 years of accumulated prescriptions against
one year of queue headroom), the one *voluntary* violation found, and options for
2026 — in
[interconnection-queue-and-prescribed-builds.md](guidance/interconnection-queue-and-prescribed-builds.md).

**Fixed upstream?** N/A — not a bug. `cap_penalty.csv`, `eq_interconnection_queues`
and the `report.gms` reconciliation are byte-identical at `upstream/main`
(`1f73bd23`). The collision is specific to CEPM's short horizon and wide
`startyear`→first-solve-year gap, which upstream's 2010-2050 runs do not have.

## Cosmetic warnings safe to ignore

- **`copy_files.py`** — pandas `DtypeWarning: Columns (N) have mixed types` while
  reading an input CSV. Cosmetic; doesn't affect the data actually loaded.
- **`hourly_repperiods.py`** (via `hourly_plots.py`) — `UserWarning: The
  GeoDataFrame you are attempting to plot is empty` followed by
  `IndexError: index 0 is out of bounds for axis 0 with size 0`. Happens when a
  representative-period map has nothing to plot for the run's region set (e.g. a
  reduced-region case). Diagnostic image only; doesn't affect model results.

## Related documents

- [batch-log.md](batch-log.md) — the other half of the pair. Where this file
  records defects in the machinery, that one records what each batch ran and
  showed, including issues with *results* rather than with the code.
- [GAMS_ERROR_579_INVESTIGATION.md](guidance/GAMS_ERROR_579_INVESTIGATION.md) — GAMS 44.4.0
  `$loadDCR`/domain-set compile failure in `autocode/b_load_sets.gms` (fixed).
- [two-step-re-limited-runs.md](guidance/two-step-re-limited-runs.md) — design for the
  two-phase `*_baseline` → `*_limitre`/`*_optimized` runs, including the
  `eq_growthlimit_absolute` final-year infeasibility (finding F1, entry above) and
  why the interconnection-queue cap can't be repurposed for a policy ceiling.
- [tech-limit-options.md](guidance/tech-limit-options.md) — the menu of mechanisms for
  constraining a technology's capacity, and which ones can actually promise a hard
  ceiling.
- [interconnection-queue-and-prescribed-builds.md](guidance/interconnection-queue-and-prescribed-builds.md)
  — how the interconnection-queue ceiling and the prescribed-build floor are
  sourced, wired and enforced, and why they collide in 2026. Covers the two
  entries above on the queue penalty and on `startyear`, plus the 2032 blind spot
  (queue data ends in 2030, so the final CEPM year is interconnection-unconstrained).
- [SUBNATIONAL_REGION_SUPPORT.md](guidance/SUBNATIONAL_REGION_SUPPORT.md) — audit of
  `GSw_ZoneSet`/`GSw_Region` combinations, covering several zoneset-specific
  failures (`techs_banned.csv` region matching, missing `hierarchy_from134.csv` for
  z90, `writecapdat.py`'s missing `'ba'` key for z134, PRAS crashing on single-zone
  regions, `cendivweights.csv` domain violations near census-division borders).

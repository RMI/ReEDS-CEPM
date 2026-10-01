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

## Index

Every entry in this file, in page order. **Status** describes the state of the
*fix*, not the severity — the two most dangerous entries here are `Open` and fail
**silently**, producing a complete-looking run with wrong results. Those are
flagged in their descriptions; if you are auditing a finished run rather than
chasing a crash, start with them.

| Issue | Status | What it does |
|---|---|---|
| [GAMS 44.4.0: `Error 579` on model compile](#gams-4440-compile-failure-error-579-in-autocodeb_load_setsgms-fixed) | Fixed | Blocked every run at model compile on our pinned GAMS. Fixed in `h5_to_gdx.py`. |
| [`GSw_GrowthAbsCon=1`: final solve year infeasible](#gsw_growthabscon1-makes-the-final-solve-year-infeasible-eq_growthlimit_absolute) | Open — workaround | Last modeled year goes infeasible from a year-gap sign error. Use a sacrificial final year, or the cumulative caps instead. |
| [`GSw_CEPM_TgCap=1`: Virginia 2029 infeasible](#gsw_cepm_tgcap1-makes-the-virginia-2029-solve-infeasible--root-cause-not-yet-found) | Open — cause unknown | VA `limitre` dies at 2029 with 1665 infeasible rows. Cap is the trigger; the colliding constraint is not yet identified. Disabling the RPS is **not** expected to help. |
| [H2 infeasibility with `GSw_H2=2` (unverified)](#possible-h2-infeasibility-with-gsw_h22-in-national-runs-unverified) | Open — untested | A 2026-07 national run went infeasible in DE. Root cause never traced; every CEPM case sets `GSw_H2=0`. |
| [`cendivweights.csv` domain violation at cendiv borders](#cendivweightscsv-domain-violation-near-census-division-borders-fixed) | Fixed — not on `main` | Sub-national runs near a census-division border fail GAMS compile. Fixed on `dev`; `main` still has it. |
| [`recf.py` crashes when offshore wind is disabled](#recfpy-crashes-when-offshore-wind-is-disabled-fixed) | Fixed | `GSw_OfsWind=0` left `df_windofs` undefined before a concat. |
| [Onshore wind supply curve dropped under pandas 3](#onshore-wind-supply-curve-silently-dropped-under-pandas-3-when-a-sibling-curve-is-empty) | Open — fix identified | **Silent.** A landlocked region with `GSw_OfsWind=1` builds zero new onshore wind, with no error. Live upstream too. Four runs affected and still recurring. |
| [`startyear` > 2022 crashes `hydcf.py`](#startyear--2022-crashes-hydcfpy-arange-cannot-compute-length) | Open — fixed in `2026.09.08` | A later `startyear` empties the historical hydro frame and dies at an unrelated `arange`. Resolves at the next sync. |
| [`report_dump.py` crashes reading `df_capex_init.csv`](#postprocessing-report_dumppy-crashes-reading-df_capex_initcsv) | Open — fixed in `2026.09.08` | Postprocessing ordering bug: the system-cost CSV is never written. Run itself unaffected. |
| [`report_dump.py` leaves GAMS sets out of `outputs.h5`](#report_dumppy-leaves-gams-sets-out-of-outputsh5-could-not-convert-string-to-float-) | Open — fixed in `2026.09.08` | **Silent.** `read_output()` returns an empty table for sets such as `hierarchy`; read `outputs/<set>.csv`. Solve unaffected. |
| [`single_case_plots.py` plots fail on reduced-region cases](#single_case_plotspy-diagnostic-plots-fail-on-single-region--reduced-hierarchy-cases) | Open — partly by design | Several diagnostic maps fail on single-region or reduced-hierarchy runs. Each is caught; core outputs unaffected. |
| [bokehpivot: every map section fails on an aggregated zoneset](#bokehpivot-html-report-every-map-type-section-fails-on-an-aggregated-zoneset) | Open | No boundary file exists for aggregated zonesets, so all map sections of the HTML report are missing. |
| [Retail rate module: pandas-3 no-ops](#retail-rate-module-chained-assignments-are-no-ops-under-pandas-3) | Open | Some retail-rate fills and replacements silently do nothing, so retail outputs may be off. Capacity and dispatch unaffected. |
| [`compare_cases.py` crashes on a shared-prefix glob](#compare_casespy-crashes-when-comparing-cases-via-a-shared-prefix-glob-typeerror-in-parse_caselist-fixed) | Fixed | `TypeError` in `parse_caselist()` blocked the comparison report entirely. |
| [`compare_cases.py` hardcodes year 2020](#compare_casespy-hardcodes-year-2020-in-several-plots-instead-of-using---startyear-fixed) | Fixed | Five literal `2020`s broke slides for any batch whose years exclude 2020 — i.e. every CEPM case. |
| [`compare_cases.py` "Flexibly Sited Demand" slide](#compare_casespy-flexibly-sited-demand-slide-calls-the-wrong-module-fixed) | Fixed | Called `add_to_pptx` from the wrong module, dropping the slide. |
| [`runreeds.py` reports success on failure, hangs on multi-case `-s`](#runreedspy-reports-success-on-a-failed-case-and-hangs-on-a-multi-case--s) | Open — worked around | **Silent.** Exit code 0 despite an aborted solve; interactive prompts hang under a wrapper. Check for `outputs.h5`, not the exit code. |
| [`z_rep` dominated by the interconnection-queue penalty](#z_rep-is-dominated-by-the-interconnection-queue-penalty-and-does-not-match-systemcostcsv) | Not a bug | `z_rep` is unusable as a cost figure and the penalty does shift buildout. Use `systemcost.csv`. |
| [Operating reserves effectively off by default](#operating-reserves-are-effectively-off-under-default-switches) | Expected | Reserve constraints have 0 rows under default switches (upstream design with stress periods). |
| [`reeds2pras` `BoundsError` for `hydud`/`hydund`](#reeds2pras-boundserror-for-hydudhydund-hydro-capacity--no-monthly-profile-data) | Open — non-fatal | Hydro-upgrade categories have no monthly profile data, so PRAS zeroes their contribution. Diagnostic layer only. |
| [PRAS crashes on single-zone regions](#pras-crashes-on-single-zone-regions-boundserror--0-element-vectorline) | Open | A one-zone region has no lines, so `make_pras_interfaces()` throws after the solve. Use ≥ 2 zones. |
| [Cosmetic warnings safe to ignore](#cosmetic-warnings-safe-to-ignore) | Informational | Known-harmless warnings from `copy_files.py`, `hourly_repperiods.py`, the VRE-sites maps and bokeh "Firm Capacity". |

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

No at `2026.08.03`. Upstream tag `2026.09.08` has its own fix
(`write_declare_and_load()`); at that sync, confirm it compiles on GAMS 44.4.0,
then drop our patch and this entry.

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
  [two-step-re-limited-runs.md](guidance/two-step-re-limited-runs.md). Note the
  caps avoid *this* failure mode but have one of their own — see
  [the Virginia 2029 entry](#gsw_cepm_tgcap1-makes-the-virginia-2029-solve-infeasible--root-cause-not-yet-found)
  immediately below.

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

## `GSw_CEPM_TgCap=1` makes the Virginia 2029 solve infeasible — root cause not yet found

**Symptom:** a `limitre` case fails partway through its horizon with
```
**** SOLVER STATUS     1 Normal Completion
**** MODEL STATUS      4 Infeasible
*** Error at line 165146: Execution halted: abort 'Model did not solve to optimality'
```
and then `Exception: 3_solve_oneyear.gms failed with return code 3`. Observed on
`runs/v20260925_VA_limitre` (2026-09-25 19:36), which solved 2010 and 2026 normally
and died at **2029**, leaving only 6 files in `outputs/` and no `cap.csv`. The report
summary counts **1665 infeasible rows** (sum of violations 4,262,097; max 695,620).

Note the solver log looks alarming but is a red herring: CPLEX's barrier bails out
after 0.1 s with
```
Barrier limit on dual objective exceeded.
Infeasible barrier solution (dependent on objective limit).
--- LP status (22): dual objective limit exceeded.
```
and the dual objective running away to 1.57e20. That is the signature of an infeasible
primal, not a numerical or scaling problem.

**Root cause: not yet identified.** What is established:

- **The cumulative cap is the trigger.** `VA_limitre` differs from `VA_optimized`
  *only* by `GSw_CEPM_TgCap=1` and `cepmtgcapscen=v20260925` (verified by diffing
  `inputs_case/switches.csv`). `VA_optimized` carries the identical high data-center
  load (`GSw_LoadSiteTrajectory=st_epri_medium_extended_to_2032`,
  `GSw_LoadSiteCF=1`, `GSw_LoadSiteRA=1`) and solves through 2032 cleanly. So the
  infeasibility is created by `eq_cepm_tg_cap_sys`, not by the load scenario.
- **Not a prescribed-build collision.** The obvious failure mode for a cumulative
  investment cap is a forced build that exceeds it, but prescribed capacity from 2026
  on fits comfortably inside every cap: wind-ofs 2,640 MW against a 3,949.7 MW cap
  (the CVOW build in 2027), upv 1,465.6 against 23,976.6, wind-ons 78.0 against
  11,866.4. Ruled out.
- **Not the state RPS.** This was the first hypothesis and it does not hold up. VA's
  RPS rises 14.5% (2026) → 19.7% (2029) → 25.8% (2032), so capping RE while
  data-center load grows does make it harder to meet — but `eq_REC_Requirement`
  includes `+ ACP_PURCHASES(rpscat,st,t)$(not acp_disallowed(st,RPSCat))`,
  `acp_disallowed.csv` in the run is **empty** (ACP allowed everywhere), and
  `ACP_PURCHASES` is a positive variable with **no upper bound**. VA's 2029 ACP price
  is $54.36/MWh. The model can always buy its way out of the RPS, so an unreachable
  RPS produces an expensive solution, not an infeasible one. **Setting
  `GSw_StateRPS=0` is therefore not expected to unblock this run.**
- **Reserve margin is an unlikely culprit but unconfirmed.** The caps cover only
  `battery`, `csp`, `pumped-hydro`, `pv`, `wind-ofs` and `wind-ons` — gas is uncapped,
  and `eq_co2_cumul_limit` generates 0 rows in this run, so on the face of it the
  model should be able to meet PRM with gas. Not yet verified.

**Why the conflict refiner did not answer this already:** `iis 1` is *already set* in
the run's `cplex.opt`, but the refiner never ran. CPLEX only invokes it on a clean
infeasibility proof, and with `lpmethod = 4` the barrier aborted on "dual objective
limit exceeded" (LP status 22) instead. Re-solving 2029 with `lpmethod 1` or `2`
(primal/dual simplex) should let the already-enabled refiner produce the minimal
infeasible constraint set and name the offending equations. Everything needed is
present: GAMS 44.4.0, and the restart file
`g00files/v20260925_VA_limitre_2026i0.g00`. This is the obvious next step and has not
been done.

**Impact:** blocks the `limitre` leg of the two-step workflow for VA. Because
`limitre` is the constrained half of the `*_baseline` → `*_limitre`/`*_optimized`
comparison, its absence makes the VA batch's headline comparison impossible, not just
incomplete. `VA_baseline` and `VA_optimized` both completed and are unaffected.

Note the failure is easy to miss for the reason documented in the `runreeds.py` entry
below: the batch still reports success. Check for `outputs/cap.csv` and
`outputs/outputs.h5` rather than trusting the exit code.

**Status:** not fixed, root cause not yet isolated. No workaround identified — and
specifically, the intuitive one (disable the state RPS) is expected not to work, per
above. Until the conflict refiner is run, the honest summary is: the cumulative cap
makes VA's 2029 LP infeasible and we do not yet know which constraint it collides
with.

Worth checking once the refiner names the rows: whether this is specific to VA's
cap *values* (harvested from `VA_baseline` by `CEPM/scripts/make_tg_cap.py`) or a
general property of the cap mechanism under high load growth. The same two-step
workflow runs for WECC-SW and SERTP without this failure, which points toward the
former — VA's caps may simply be harvested too tight relative to what the
data-center load scenario needs — but that is a hypothesis, not a finding.

**Fixed upstream?** N/A. `GSw_CEPM_TgCap` and `eq_cepm_tg_cap_sys`/`_reg` are
RMI-fork-only additions (see the "Cumulative tech-group investment caps" entry in
[`reeds-to-cepm-log.md`](reeds-to-cepm-log.md)); there is no upstream equivalent to
compare against. If the refiner turns out to implicate a stock ReEDS equation rather
than the cap itself, that part should be re-checked against upstream.

## Possible H2 infeasibility with `GSw_H2=2` in national runs (unverified)

A 2026-07 `country/USA` run with `GSw_H2=2` went infeasible in 2032: electrolyzer
`PRODUCE` was forced positive in DE while DE's H2 demand balance was fixed to
zero. The root cause was never traced. Every `cases_cepm.csv` case now sets
`GSw_H2=0`; check this first if H2 is turned back on for a national run.

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
bug. Also tracked in [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md)'s
["Resolving census divisions in fuelcostprep.py"](reeds-to-cepm-log.md#resolving-census-divisions-in-fuelcostpreppy)
section.

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

## Onshore wind supply curve silently dropped under pandas 3 when a sibling curve is empty

**Symptom:** a run completes normally — no error, no warning, `writesupplycurves.py`
logs `Starting`/`Finished` as usual — but builds **no new onshore wind at all**.
Total `wind-ons` capacity sits flat at the existing fleet for every solve year. The
tell is in `inputs_case/rsc_combined.csv`: `wind-ons` has only `cost_cap` and
`cost_trans` rows, and no `cap` or `cost` rows, so the model is handed zero buildable
wind resource. To check any run:

```bash
awk -F, 'NR>1{split($1,a,"_"); print a[1]"|"$3}' inputs_case/rsc_combined.csv \
  | sort | uniq -c | grep wind
```

A healthy run shows four categories (`cap`, `cost`, `cost_cap`, `cost_trans`) with
equal row counts. An affected run is missing `cap` and `cost` entirely:

```
  377 cap   377 cost   377 cost_cap   377 cost_trans     <- healthy (v20260916v4_st-AZNM_baseline)
                       377 cost_cap   377 cost_trans     <- broken  (v20260924fix_st-AZNM_baseline)
```

First surfaced 2026-09-24 on `runs/v20260924fix_st-AZNM_*`, which built 0.7 GW of wind
in 2032 (the existing fleet, nothing new) against 14.2 GW (`baseline`/`limitre`) and
15.8 GW (`optimized`) in the otherwise-comparable `runs/v20260916v4_st-AZNM_*` eight
days earlier. Switches, `numbins_*` and siting scenarios were identical between the
two.

**Root cause:** a dtype bug in `agg_supplycurve()`
(`reeds/input_processing/writesupplycurves.py`) that only became live with pandas 3.0.

`st-AZNM` is landlocked, so its `supplycurve_wind-ofs.csv` is header-only — but
`GSw_OfsWind=1`, so offshore wind is still processed. For an empty input,
`agg_supplycurve()` takes its `if dfin.empty:` branch and assigns `dfin['bin'] = []`,
which pandas types as **float64**. pandas 3.0 stopped excluding empty frames from
dtype resolution in `pd.concat`, so `windall = pd.concat(wind, axis=0)` — which stacks
the onshore and offshore frames row-wise into a MultiIndex — upcasts the `bin` level
from int64 to float64. The next line,
`windall["bin"] = "wsc" + windall["bin"].astype(str)`, then produces `wsc1.0` instead
of `wsc1`, so the rename map `{"wsc1": "bin1", ...}` matches nothing and the wind bin
columns keep their `wsc*.0` names.

From there the loss is silent by construction: `alloutcap.pivot(...)` selects its value
columns with `[c for c in alloutcap.columns if c.startswith("bin")]`, which wind no
longer has, so all wind capacity is dropped without complaint. The final
`.pivot(...).dropna()` over the `(cap, cost)` pair then discards the orphaned wind cost
rows too. Only `cost_cap`/`cost_trans` survive, because those are concatenated on
*after* that pivot.

UPV, CSP, geohydro and EGS escape only incidentally — see Scope. `class` escapes for a
similar accidental reason: it is read from the CSV, which pandas types as object for an
empty file, rather than being assigned a bare `[]`.

**Trigger:** this fork's pandas pin moved to `pandas==3.0.*` on 2026-09-10 (`129ecdbc`,
"Bump Python to 3.14, realign packages with environment.yml"), and the local venv was
rebuilt to pandas 3.0.5 on 2026-09-24 at 20:24 — 21 minutes before the first affected
run started. `uv.lock` carried `pandas 2.0.3` from 2026-05-05 until that bump, so every
run before 2026-09-24 was unaffected with identical inputs and switches. This is a
pre-existing upstream bug that the pandas upgrade activated, not a regression
introduced by the pin — and note upstream pinned `pandas=3.0` four months before we did
(see **Fixed upstream?** below). Do not "fix" it by pinning pandas back.

**Scope — all four conditions must hold at once:**

1. **pandas >= 3.0.** The concat dtype-resolution change is what makes the latent bug
   live. Confirmed on 3.0.5: concatenating a populated int64-`bin` frame with an empty
   float64-`bin` one yields `['wsc1.0', 'wsc2.0', ...]`; the populated frame alone
   yields `['wsc1', 'wsc2', ...]`.
2. **The code path stacks sub-techs with `pd.concat(dict, axis=0)` and then does
   `.astype(str)` on the `bin` level.** Only two sites qualify: wind
   (`pd.concat(wind, axis=0)` over `ons`/`ofs`, then `"wsc" + bin.astype(str)`) and
   geothermal (`pd.concat(geo, axis=0)` over `geohydro`/`egs`, then
   `"geosc" + bin.astype(str)`). **UPV and CSP cannot hit this** — they call
   `agg_supplycurve()` standalone, so an empty result just stays empty with no
   populated sibling to corrupt.
3. **One member of that dict is empty and the other is not.** Both populated, no
   upcast; both empty, nothing to lose. Only the *mixed* case does damage, because the
   empty frame's float64 silently rewrites the populated frame's bin labels.
4. **The empty member is still being processed** — its switch is on, so it reaches the
   concat even though it has no resource.

For wind that reduces to: **offshore wind enabled in a region with no offshore
resource.** Verified against the affected `st-AZNM` inputs — `GSw_OfsWind=1` yields
0 `cap`/0 `cost` wind rows, `GSw_OfsWind=0` yields 1640/1640. It is leaving the switch
*on* over an empty curve that bites; turning it *off* is safe.

`GSw_OfsWind` defaults to **1** in `cases.csv`, so every case satisfies condition 4
unless it explicitly opts out. Which regions satisfy condition 3, measured by offshore
supply curve rows across existing runs:

| Region | offshore rows | exposed? |
|---|---|---|
| `st/AZ.NM` | 0 | **yes** — what this entry was raised for |
| `nercr/WECC_SW` | 0 | **yes** |
| `st/VA` | 149 | no |
| `st/MS.AL.GA` | 1207 | no |
| `transreg/SERTP` | 2848 | no |
| `country/USA` | 16191 | no |

**`nercr/WECC_SW` is exposed and has not been re-run since the pandas upgrade** — its
existing runs predate it and are clean, but the next WECC-SW run will lose its wind the
same way.

**The geothermal site is latent, not live.** `geoall = pd.concat(geo, axis=0)` followed
by `"geosc" + geoall["bin"].astype(str)` is the same construct, and fails condition 3
only by accident: `rev_geo_types` is built from whichever of `geohydrosupplycurve` /
`egssupplycurve` equals `reV`, and current switches set `egssupplycurve=reV` with
`geohydrosupplycurve=ATB_2023`, leaving a single-element dict with nothing to concat
against. Set both to `reV` in a region where one is empty and it would bite identically.

**Impact:** severe and silent — this is the dangerous kind. The run completes, every
output file is written, and the results look plausible; wind is simply absent from the
build. Anything downstream of capacity (generation mix, system cost, emissions, prices,
PRAS) is wrong in a way no error surfaces. Because the failure mode is a missing input
rather than a crash, affected runs have to be identified by inspecting
`rsc_combined.csv` — scanning logs will not find them.

**Status:** not fixed. Diagnosed, with a validated candidate fix not yet applied.

The candidate fix is one line — type the empty column to match the int64 that
`reeds.inputs.get_bin` produces in the non-empty branch, so the `bin` level never
upcasts:

```python
 if dfin.empty:
-    dfin['bin'] = []
+    dfin['bin'] = pd.Series([], dtype='int64')
```

Fixing at the dtype source rather than at the `.astype(str)` call is deliberate: the
same trap sits one line below on `class`, and `agg_supplycurve()` also feeds the
geothermal concat above. Validated offline against the real
`v20260924fix_st-AZNM_baseline` inputs — restores 377 `cap` and 377 `cost` rows for
`wind-ons` and 920.3 GW of buildable resource, with the `cap` rows byte-identical to
the pre-pandas-3 `v20260916v4` run, and UPV output unchanged. Not yet committed to any
mainline branch.

**Still recurring.** A sweep of every run under `runs/` finds four affected cases: the
three original `v20260924fix_st-AZNM_*` runs and `20260929_st-AZNM_baseline`, launched
2026-09-29 — after the bug was diagnosed but before any fix landed, and it lost its
wind the same way (0.7 GW in 2032). Every affected run needs re-running once a fix is
applied; their results are not usable.

Worth noting for whoever fixes this: the reason it went unnoticed is that
`[c for c in alloutcap.columns if c.startswith("bin")]` drops non-matching columns
silently. Asserting that no `wsc*` columns survive the rename would turn this class of
failure loud rather than letting the pivot discard them.

**Fixed upstream?** No — and, unlike most entries here, **the bug is live upstream right
now, not latent.** `reeds/input_processing/writesupplycurves.py` has the identical bare
`dfin['bin'] = []` at line 105 at tag `2026.08.03` and at line 121 on the current
`upstream/main`, and upstream's `environment.yml` has pinned `pandas=3.0` since
2026-05-08 (`2ff493b5`, "update all python packages and use conda-forge for
everything") — four months before this fork moved to it. So upstream satisfies
conditions 1 and 2 already; they simply have not hit conditions 3-4, because their
default and test cases (`cendiv/Pacific`, `country/USA`) are coastal or national and
always have a populated offshore curve. Any upstream user running a landlocked region
with `GSw_OfsWind=1` on a current checkout gets silently zeroed wind.

Not raised upstream as of 2026-09-29. Searched the `ReEDS-Model/ReEDS` issue tracker
(all 86 issues, open and closed) plus PR history for `writesupplycurves`,
`agg_supplycurve`, `rsc_combined`, `rscbin`/`wsc`, pandas/dtype, and
offshore/landlocked supply-curve terms. The nearest hits are unrelated: #27 ("Offshore
wind zones incompatible with custom regions") is about prescribed offshore builds under
`GSw_OffshoreZones=1`, and #28 is an offshore-zone TODO list. Strong candidate to report
and contribute back — it is a one-line dtype correction that is a no-op under pandas 2.

## `startyear` > 2022 crashes `hydcf.py` (`arange: cannot compute length`)

**Symptom:** `ValueError: arange: cannot compute length` in `hydcf.py`'s
`assemble_hydcf()`, right after `copy_files.py`, before model compile.

**Root cause:** `calculate_historical_monthly_regional_cf()` keeps only
`t >= startyear`, but the historical hydro data (`net_gen_existing_hydro.csv`,
`cap_existing_hydro.csv`) covers 2007–2022. A later `startyear` empties the frame,
`data_endyear` becomes `NaN`, and `np.arange` fails.

**Status:** not fixed. Leave `startyear` at the 2010 default. Other `startyear`
traps: [interconnection-queue-and-prescribed-builds.md](guidance/interconnection-queue-and-prescribed-builds.md)
§5.3.

**Fixed upstream?** No at `2026.08.03`; fixed in `2026.09.08` — resolves at the
next sync.

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

**Fixed upstream?** No at `2026.08.03`; fixed in `2026.09.08` (`1b3bba93`:
`calculate_historical_capex` moved into `report_dump.py`) — resolves at the next
sync.

## `report_dump.py` leaves GAMS sets out of `outputs.h5` (`could not convert string to float: ''`)

**Symptom:** one caught traceback per set (`r`, `hierarchy`, `valcap_i`, `cendiv`,
`e`, `fuel2tech`, `h_szn`, `szn_stress_t`, `v`) from `reeds/io.py`'s
`write_output_to_h5`:
`ValueError: could not convert string to float: '': Error while type casting for column 'Value'`.
The run continues.

**Root cause:** gdxpds 4.0 returns a set's `Value` as `''` instead of
`ctypes.c_bool`, so the drop-`Value` check misses it. Introduced by the August
2026 sync.

**Impact:** solve results are unaffected. The sets are only in
`outputs/<set>.csv` (kept at CEPM's `cleanup_level=0`). The trap is silent:
`reeds.io.read_output(case, '<set>')` returns an **empty** table instead of
raising, so read the CSV instead.

**Status:** not fixed.

**Fixed upstream?** No at `2026.08.03`; fixed in `2026.09.08` (`038dd8ed`) —
resolves at the next sync.

## `single_case_plots.py` diagnostic plots fail on single-region / reduced-hierarchy cases

**Symptom:** one or more of the following appear as `<plot function> failed:` with a
traceback, during the final plotting stage — each is caught individually, so the run
completes and later plots still generate:
- `map_translines_all`, `map_translines_vsc`, `map_net_imports`, `plot_max_imports` —
  `ValueError`/`IndexError` from empty-array or scalar-mismatch assumptions.
- `plot_interreg_transfer_ratio`, `plot_interface_flows` — explicit guards
  (expected).
- `validate_regional_capacity` — `TypeError: cannot unpack non-iterable int object`.
- `plot_neue_bylevel` — `ValueError: No objects to concatenate` (no PRAS outputs
  to plot).
- `plot_capacity_offline` — `KeyError` for a region name not present in the run's
  region set (e.g. `'AZ'`; also seen as `'CA'` on a `country/USA`/`z54` run — not
  single-region-specific, just needs the missing region to be absent from whatever
  aggregation the run uses).
- `map_capacity_techs` — `ValueError: list.remove(x): x not in list` for a hardcoded
  tech not present in the run's tech set.
- `map_prm` — `TypeError: 'Axes' object is not subscriptable`, from
  `reedsplots.py`'s `map_prm()` indexing a `plt.subplots()` result that's a bare
  `Axes` (not an array) when only one year is being plotted.

The same single-region runs also log `KeyError: 'res_marg_ann_flow'` from
`retail_rate_calculations.py:111` (no inter-region flows to read) — not a
`single_case_plots.py` failure, but the same missing-structure pattern.

**Root cause:** these plotting functions assume the full national, multi-region,
multi-year model structure (inter-regional transmission, multiple hierarchy levels,
a fixed set of region names, multiple year subplots). A reduced-region or
single-year test case violates one or more of those assumptions. Some failure modes
are explicitly guarded (`NotImplementedError`, working as intended); others are
unguarded code bugs that happen to only trigger in this configuration (`map_prm`,
`map_capacity_techs`, `plot_capacity_offline`).

**Impact:** the corresponding diagnostic maps/plots are missing from the run's
`outputs` folder. Core solve outputs and CSV results are unaffected.

**Status:** known, not fixed.

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
  literal. Same code at `2026.08.03`. Fix would be intersecting `regions`
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
File ".../postprocessing/bokehpivot/core.py", line ..., in create_map
    height=int(height),
ValueError: cannot convert float NaN to integer
```
Post-sync runs also log `***Error, your y-axis is a string.` for some of the same
sections (e.g. 39/40). Non-map chart types (national bar/line totals) for the same underlying data render
fine — e.g. "Capacity (GW)" (national) succeeds while "Final Wind Capacity (GW)"
(map) fails immediately after it. Confirmed in
`runs/20260821_USA_fasterish/outputs/reeds-report/report.log` (sections 24, 36, 37,
39–44), a `country/USA`/`z54`/`GSw_RegionResolution=aggreg` run.

**Root cause:** `create_maps()` (`postprocessing/bokehpivot/core.py`) reads
region boundary polygons from `postprocessing/bokehpivot/in/gis_rb.csv` — keyed to
raw, un-aggregated BA IDs (`p1`, `p2`, ...) — then filters it to
`region_boundaries['id'].isin(full_rgs)`, where `full_rgs` are the region labels
actually present in this run's output data. Under an aggregated zoneset
(`GSw_ZoneSet=z48/z54/z69/z90/z132` with `GSw_RegionResolution=aggreg`), those
labels are the zoneset's own aggregated zone names, not `p1`...`p134` — none of
them match anything in `gis_rb.csv`, so the filter empties `region_boundaries`.
`.max()`/`.min()` on the empty frame return `NaN`, which propagates through
`aspect_ratio = (y_max-y_min)/(x_max-x_min)` into `height=int(height)` in
`create_map()`, raising. Only `gis_rb.csv` (raw BA) and `gis_st.csv` (state) exist
in `postprocessing/bokehpivot/in/` — no boundary file for any aggregated zoneset.

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

**Fixed upstream?** No — bokehpivot is identical at `2026.08.03`.

## Retail rate module: chained assignments are no-ops under pandas 3

**Symptom:** `ChainedAssignmentError: A value is being set on a copy of a
DataFrame or Series through chained assignment` (logged at ERROR level,
non-fatal).

**Root cause:** pandas 3 copy-on-write, introduced by the August 2026 sync.
`df[col].fillna(..., inplace=True)` in `retail_rate_calculations.py` and two
assignments in `ferc_distadmin.py` never update the original: eval/depreciation
periods stay NaN, DC isn't mapped to MD, and negative extrapolation indices
aren't clamped.

**Impact:** retail-rate outputs may be off. Capacity and dispatch results are
unaffected, and CEPM doesn't currently use the retail-rate postprocessor.

**Status:** not fixed.

**Fixed upstream?** No at `2026.08.03` or `2026.09.08`; fixed on `upstream/main`
(`17054ae5`).

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

## `compare_cases.py` "Flexibly Sited Demand" slide calls the wrong module (FIXED)

**Symptom:** the "Flexibly Sited Demand" slide is missing from the comparison
`.pptx` for case pairs with load-site (data-center) demand enabled, with:
```
AttributeError: module 'reeds.results' has no attribute 'add_to_pptx'
```
Caught by the script's per-section `try`/`except`, so only that slide is dropped.

**Root cause:** a typo in that one call site. `add_to_pptx` is defined only in
`reeds/report_utils.py`, and every other slide already calls
`reeds.report_utils.add_to_pptx(...)`.

**Status:** fixed. See [`reeds-to-cepm-log.md`](reeds-to-cepm-log.md).

**Files changed:**
- `postprocessing/compare_cases.py` — the slide's `reeds.results.add_to_pptx(...)`
  call changed to `reeds.report_utils.add_to_pptx(...)`.

**Fixed upstream?** No — `postprocessing/compare_cases.py` still calls
`reeds.results.add_to_pptx` at `2026.08.03` and `2026.09.08`. Inherited (present
since upstream's `2026.04.15` tag), not RMI-introduced.

## `runreeds.py` reports success on a failed case, and hangs on a multi-case `-s`

Three separate behaviors, all of which break unattended/batch automation rather
than any single run. Grouped because anyone scripting `runreeds.py` hits them.

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
unless `--simult_runs`/`-r` was given. A single case
short-circuits to `WORKERS = 1` with no prompt, so this
only appears once a batch has two or more — where it blocks forever in a
background, CI, or non-interactive shell with no visible prompt.

**Symptom 3 — interactive hang on `cleanup_level`.** `runreeds.py`
prints an R2X warning and blocks on `input('\nProceed? y/[n]: ')` — defaulting
to `n`, which `quit()`s — whenever **any** case being run has
`cleanup_level >= 1` and `--skip_checks`/`-f` was not passed. Note this is the
*launch-time* check only — the per-case cleanup that `runreeds.py` schedules at
the end of a run passes `--force --quiet`, so `cleanup_files.py`'s own
confirmation prompt never fires.

**Root cause:** none is a bug exactly — `runreeds.py` was written for
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

## Operating reserves are effectively off under default switches

**Symptom:** none at solve time. `eq_OpRes_requirement` and `eq_ORCap_*` have 0
rows in every solve `.lst`, and `inputs_case/rep/opres_periods.csv` is
header-only. The bokeh "Final OpRes by timeslice" section fails with
`IndexError: list index out of range`.

**Root cause:** `GSw_OpResPeriods=peakload` (the default) applies reserves only in
peak-load periods, which exist only when `GSw_PRM_CapCredit=1`. Under the default
stress-period method there are none. Upstream's model documentation: "operating
reserves are typically turned off when using the stress periods formulation."

**Status:** expected; CEPM keeps the defaults. To enforce reserves, set
`GSw_OpResPeriods=representative`.

**Fixed upstream?** N/A — same defaults at `2026.08.03` and `2026.09.08`.

## `reeds2pras` `BoundsError` for `hydud`/`hydund` hydro capacity — no monthly profile data

**Symptom:** caught, non-fatal Julia errors during a solve year's `ReEDS2PRAS` step (visible in `gamslog.txt`, not `report.log`):
```
┌ Error: <timestamp> | p1,hydud,BoundsError(Float64[], (1,))
└ @ Main.ReEDS2PRAS .../reeds2pras/src/utils/reeds_data_parsing.jl:582
```
repeated once per month for every affected (zone, tech) pair — e.g. 72 lines total (6 pairs × 12 months) on a `cendiv/Pacific`/`z132` run: `p1,hydud`; `p1,hydund`; `p2,hydud`; `p5,hydund`; `p6,hydund`; `p9,hydund`.

**Root cause:** `process_hydro()` (`reeds/resource_adequacy/reeds2pras/src/utils/reeds_data_parsing.jl:485`) only runs this code path when `pras_hydro_energylim=1` — `cases.csv`'s own default, so this is the normal path for essentially every case, not an edge case. For each dispatchable-hydro (zone, tech) pair it has exogenous capacity for, it filters `hydcf.csv` (monthly hydro capacity factor) and `hydcapadj.csv` (monthly capacity adjustment) by month and indexes the first match with `[1]`. `hydud`/`hydund` (hydro-upgrade capacity categories, tied to `GSw_HydroCapEnerUpgradeType`/`hyd_add_upg_cap.csv`) have exogenous MW capacity in the run but **zero rows in `hydcf.csv`/`hydcapadj.csv` for any region** — confirmed directly against `inputs_case/hydcf.csv` and `inputs_case/hydcapadj.csv` in an affected run. The filter comes back empty, and indexing `[1]` throws `BoundsError`.

Non-fatal: `process_hydro()` wraps this in `catch e; @error ...` (upstream code,
unchanged at `2026.08.03`).

**Impact:** confined to the resource-adequacy diagnostic layer, not the GAMS capacity-expansion solve. All 12 months fail for each affected pair, so `monthly_energy`/`dispatch_limit`/`energy_cap`/`inflow`/`grid_inj_cap` for that hydro-upgrade unit stay at their pre-allocated `zeros()` for the entire year in PRAS's Monte Carlo simulation, instead of a real profile — a conservative understatement, not an overstatement, of that unit's reliability contribution. Doesn't touch investment, generation, system cost, or prices, which come from the GAMS LP and solve independently of this post-solve PRAS step. Confined to whichever zones actually carry `hydud`/`hydund` exogenous capacity (`p1`, `p2`, `p5`, `p6`, `p9` on the `cendiv/Pacific` case tested) — a case with no hydro-upgrade capacity never reaches this filter at all, which is presumably why it wasn't caught sooner.

**Status:** not fixed. No known upstream issue or PR tracking it. Candidate fix: populate `hydcf.csv`/`hydcapadj.csv` for `hydud`/`hydund` from whatever process derives their exogenous capacity in the first place, or give `process_hydro()` an explicit fallback profile for hydro-upgrade categories instead of relying on the catch to zero them out silently.

**Fixed upstream?** No — identical at `2026.08.03`.

## PRAS crashes on single-zone regions (`BoundsError ... 0-element Vector{...Line}`)

**Symptom:** after a successful LP solve, `run_pras.jl returned code 1` with
`BoundsError: attempt to access 0-element Vector{Main.ReEDS2PRAS.Line} at index [1]`.

**Root cause:** a region with one zone has no lines, but
`make_pras_interfaces()` (`reeds2pras/src/models/utils.jl`) reads
`first(sorted_lines).timesteps`.

**Status:** not fixed. Workaround: pick a region with at least 2 zones. Fix
candidate: pass `timesteps` (already a `create_pras_system()` argument) through
both `make_pras_interfaces` methods instead of reading it from a line — a clean
PR to upstream.

**Fixed upstream?** No — identical at `2026.08.03`. Not in upstream's issue
tracker. Inherited, not RMI-introduced.

## Cosmetic warnings safe to ignore

- **`copy_files.py`** — pandas `DtypeWarning: Columns (N) have mixed types` while
  reading an input CSV. Cosmetic; doesn't affect the data actually loaded.
- **`hourly_repperiods.py`** (via `hourly_plots.py`) — `UserWarning: The
  GeoDataFrame you are attempting to plot is empty` followed by
  `IndexError: index 0 is out of bounds for axis 0 with size 0`. Happens when a
  representative-period map has nothing to plot for the run's region set (e.g. a
  reduced-region case). Diagnostic image only; doesn't affect model results.
- **`single_case_plots.py`** `map_VREsites-*` — `FileNotFoundError` on
  `outputs/df_sc_out_{upv,wind-ons,wind-ofs}_reduced.csv`. Expected with
  `reeds_to_rev=0` (every CEPM case), since that step writes these files; its
  source supply-curve data is on NREL's `\\nrelnas01` share. Only the supply-curve
  overlay maps are skipped.
- **bokehpivot "Firm Capacity (GW)"** — `TypeError: '<' not supported between
  instances of 'str' and 'float'`. `cap_firm` is empty when `GSw_PRM_CapCredit=0`,
  and pandas 3 no longer tolerates the resulting mixed dtypes. No effect on
  results.

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
  sourced, wired and enforced, and why they collide in 2026. Covers the
  `startyear` and `z_rep` entries above, plus the 2032 blind spot
  (queue data ends in 2030, so the final CEPM year is interconnection-unconstrained).

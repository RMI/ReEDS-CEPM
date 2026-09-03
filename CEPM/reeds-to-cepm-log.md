# ReEDS-to-CEPM change log

Tracks how this repo diverges from upstream
[ReEDS](https://github.com/ReEDS-Model/ReEDS), including the location of every
upstream file that CEPM changed and what to re-check when we rebase onto a new
upstream release.

**Current ReEDS base:** upstream tag `2026.06.18`, plus upstream commits through
`62f6381e` (2026-06-23) — the merge base of this fork and `upstream/main`.

Most bug-fix entries below have a matching symptom-level entry in
[`known-reeds-issues.md`](known-reeds-issues.md); that file is the "my run failed, what is
this" index, while this file is the "what did we change, and what breaks on
rebase" index.

To regenerate the file-level inventory below:

```bash
git fetch upstream
git diff --stat $(git merge-base HEAD upstream/main) HEAD -- . ':!CEPM'
```

## Divergence inventory

Every upstream-owned path this fork has modified or added, as of the base above.
`CEPM/` itself is excluded — it is entirely new, and indexed by
[`CEPM/README.md`](README.md).

| Path | Change | Section |
|---|---|---|
| `reeds/input_processing/h5_to_gdx.py` | Modified | GAMS compatibility |
| `reeds/core/setup/b_inputs.gms` | Modified | GAMS compatibility |
| `reeds/input_processing/fuelcostprep.py` | Modified | Census divisions in fuelcostprep.py |
| `reeds/input_processing/recf.py` | Modified | recf.py when offshore wind is disabled |
| `reeds/resource_adequacy/reeds2pras/README.md` | Modified | Minor and cosmetic |
| `postprocessing/compare_cases.py` | Modified | Wrong module in compare_cases.py's "Flexibly Sited Demand" slide |
| `reeds/report_utils.py` | Modified | parse_caselist TypeError with a prefix-glob caselist |
| `postprocessing/compare_cases.py` | Modified | compare_cases.py hardcodes 2020 instead of --startyear |
| `cases_small.csv` | Modified | Minor and cosmetic |
| `cases.csv` | Modified | Updated CAPEX for gas resources |
| `inputs/plant_characteristics/dollaryear.csv` | Modified | Updated CAPEX for gas resources |
| `inputs/plant_characteristics/gas-ccgt_CEPM_{all,low,high}.csv` | Added | Updated CAPEX for gas resources |
| `inputs/load/loadsite_st_epri_{low,medium,high}_extended_to_2032.csv` | Added | Updated load forecasts for data centers |
| `inputs/load/loadsite_st_NMtest1.csv`, `loadsite_transreg_WCtest1.csv` | Added | Updated load forecasts for data centers |
| `.github/workflows/python-app.yaml` | Modified | ENABLE_GAMS_CI variable |
| `pyproject.toml`, `uv.lock`, `.python-version` | Added | Using uv instead of mamba |
| `hourlize/pyproject.toml`, `.gitignore` | Modified | Using uv instead of mamba |
| `run_cepm.ps1` | Added | run_cepm helper script |
| `README.md` | Modified | CEPM documentation |
| `AGENTS.md` | Added | CEPM documentation |
| `cases_cepm.csv` | Added | cases_cepm.csv file |
| `reeds/core/setup/c_model.gms` | Modified | Cumulative tech-group investment caps |
| `reeds/core/setup/b_inputs.gms` | Modified | Cumulative tech-group investment caps |
| `reeds/input_processing/runfiles.csv` | Modified | Cumulative tech-group investment caps |
| `cases.csv` | Modified | Cumulative tech-group investment caps |
| `inputs/growth_constraints/cepm_tg_cap_{sys,reg}_none.csv` | Added | Cumulative tech-group investment caps |

# Changes to base ReEDS files

In some cases, we change base ReEDS files to fix bugs, ensure compatibility,
or adjust ReEDS functionality for CEPM's needs. Most of these are captured in
[`known-reeds-issues.md`](known-reeds-issues.md).

## GAMS compatibility

### Description of issue:

Our GAMS install is pinned to **44.4.0**. Upstream's h5-to-GDX pipeline generates
GAMS code that declares *every* set (`b_declare_sets.gms`) before `$loadDCR`-ing
*any* set (`b_load_sets.gms`). On 44.4.0 that ordering is illegal: once a set has
been referenced as another set's domain, GAMS refuses to load it, raising
`Error 579` ("Cannot clear a set used as a domain or used in lag/ord
operations"). The result was 16x Error 579 and `*** Status: Compilation error(s)`
in `a_createmodel.gms`, hitting **every** case that reached model compile,
regardless of switches. GAMS 45.6.0 lifted the restriction, so upstream does not
see this on its own toolchain.

### Files changed:

- `reeds/input_processing/h5_to_gdx.py` — new `write_sets_declare_and_load()`
  emits a single `autocode/b_sets.gms` that declares and loads each set one at a
  time (primary sets first, then domain-dependent subsets), replacing the
  separate `b_declare_sets.gms` / `b_load_sets.gms` pair.
- `reeds/core/setup/b_inputs.gms` — includes `autocode/b_sets.gms` inside the
  `$gdxin` block instead of the old declare-then-load pair, with a comment
  recording the version constraint.

### Reference:

[`guidance/GAMS_ERROR_579_INVESTIGATION.md`](guidance/GAMS_ERROR_579_INVESTIGATION.md),
[`known-reeds-issues.md`](known-reeds-issues.md)

### What to test in new releases:

- Does upstream's `h5_to_gdx.py` still generate `b_declare_sets.gms` +
  `b_load_sets.gms`? If upstream restructures that codegen, this patch will
  conflict and should be re-derived rather than merged.
- Has any new primary set or domain-dependent subset been added upstream? The
  fix orders sets by dependency, so a new set with an unnoticed domain
  dependency can reintroduce the error.
- If the GAMS install moves to **45.6.0 or newer**, this patch is no longer
  required — consider dropping it and returning to upstream's codegen to shrink
  the diff.

## Resolving census divisions in fuelcostprep.py

### Description of issue:

`cendivweights.csv` triggered `Error 170 — Domain violation for element` when
GAMS read it. `fuelcostprep.py` builds census-division weights by smearing zones
against `dfmap['cendiv']`, which is drawn from the **original national
hierarchy**. For a sub-national run, the smear can therefore pull in census
divisions that are not part of the run's own `cendiv` set — typically a border
region bleeding into a neighboring division — and GAMS rejects those elements.
Reproduced on both `transreg/WestConnect` and `interconnect/western` runs.

### Files changed:

- `reeds/input_processing/fuelcostprep.py` — restricts `dfmap['cendiv']` to
  `val_cendiv` (the divisions actually in this run's region set) before smearing.

### Reference: [`known-reeds-issues.md`](known-reeds-issues.md)

### What to test in new releases:

- Does `reeds.io.get_dfmap()` still return a national-scope `cendiv` frame, or
  has upstream started scoping it to the run's regions? If upstream scopes it,
  this patch becomes redundant.
- Is `val_cendiv` still defined and populated at that point in the script?
- Re-run at least one sub-national case (a `transreg/`, `nercr/`, or `st/`
  selection — not `country/USA`) through `copy_files.py`, since a national run
  cannot surface this bug.

## Resolving recf.py when offshore wind is disabled

### Description of issue:

With `GSw_OfsWind = 0`, `recf.py` raised
`UnboundLocalError: cannot access local variable 'df_windofs' where it is not
associated with a value`. `df_windofs` is only assigned inside
`if int(sw['GSw_OfsWind']) != 0:`, but the later concat referenced it
unconditionally — a code-path bug exposed by disabling offshore wind, not a bad
input file.

### Files changed:

- `reeds/input_processing/recf.py` — adds an `else` branch assigning an empty
  `pd.DataFrame(index=df_windons.index)` so the concat inputs stay consistent.

### Reference:

[`known-reeds-issues.md`](known-reeds-issues.md)

### What to test in new releases:

- Has upstream guarded the concat itself (making this patch redundant), or added
  further unconditional references to `df_windofs`?
- Run one case with `GSw_OfsWind = 0` through `recf.py`. Upstream's default is
  `GSw_OfsWind = 1`, so upstream CI does not exercise this path.
- Note the related trap in [`known-reeds-issues.md`](known-reeds-issues.md): disabling
  offshore wind via `techs_banned` instead of `GSw_OfsWind = 0` leaves the
  `eq_RPS_OFSWind` state mandate active and the model infeasible.

## Wrong module in compare_cases.py's "Flexibly Sited Demand" slide

### Description of issue:

Running `compare_cases.py` on a case pair with load-site (data-center) demand
enabled crashed while building the "Flexibly Sited Demand" slide:
`AttributeError: module 'reeds.results' has no attribute 'add_to_pptx'`. Every
other slide in the file calls `reeds.report_utils.add_to_pptx(...)` —
`add_to_pptx` is only ever defined in `reeds/report_utils.py`, never in
`reeds/results.py`. `git blame` traces the bad line back to upstream's initial
`2026.04.15` tag, so this is an inherited upstream typo, not something CEPM
introduced. Caught during a `WECC_SW-baseline` vs. `WECC_SW-dcload` comparison
run, 2026-08-21; the script's per-section `try`/`except` meant this only
dropped one slide rather than aborting the comparison.

### Files changed:

- `postprocessing/compare_cases.py` — the "Flexibly Sited Demand" slide's call
  changed from `reeds.results.add_to_pptx(...)` to
  `reeds.report_utils.add_to_pptx(...)`.

### Reference:

n/a

### What to test in new releases:

- Has upstream fixed this typo itself? If so, drop our patch and take
  upstream's version to shrink the diff.
- Confirm `add_to_pptx` still lives in `reeds/report_utils.py` under that name
  after a rebase — if upstream moves or renames it, this call site needs
  updating again regardless of which module it points at.

## parse_caselist TypeError with a prefix-glob caselist

### Description of issue:

`compare_cases.py` crashed immediately with
`TypeError: expected str, bytes or os.PathLike object, not list` whenever called
with a single shared-casename-prefix argument (e.g. `runs/<BatchName>_`) and no
explicit `--titleshorten` — exactly the invocation `run_cepm.ps1`'s new
`-x/--compare-cases` step uses. In `reeds/report_utils.py`'s `parse_caselist()`,
the prefix-glob branch derives a default `titleshorten` from the prefix's
basename length, but passed the whole `_caselist` list to `os.path.basename()`
instead of `_caselist[0]`, the single string it expects.

### Files changed:

- `reeds/report_utils.py` — `parse_caselist()`: `os.path.basename(_caselist)`
  changed to `os.path.basename(_caselist[0])`.

### Reference:

[`known-reeds-issues.md`](known-reeds-issues.md)

### What to test in new releases:

- Has upstream fixed this typo itself? If so, drop our patch and take upstream's
  version to shrink the diff.
- Re-run `compare_cases.py` with a single shared-prefix argument and no
  `--titleshorten` (the `run_cepm.ps1 -x` invocation style) after any rebase that
  touches `parse_caselist()`.

## compare_cases.py hardcodes 2020 instead of --startyear

### Description of issue:

Several `compare_cases.py` plots/slides failed (each caught individually by the
script's own per-section `try`/`except`) whenever a batch's model years don't
include 2020 — e.g. `ValueError: 2020 is not in list` from `reeds/plots.py`'s
`annotate()`, and `KeyError: 2020` from `reeds/reedsplots.py`'s
`plot_trans_diff()`. `compare_cases.py` already resolves a `startyear` variable
from its `--startyear` argument and uses it correctly almost everywhere, but five
call sites — two `plots.annotate(...)` calls and a `df[case][2020]` lookup in the
transmission-resolution slide, plus `subtract_baseyear=2020` in two of the
transmission-maps calls — still had a literal `2020`. Every CEPM case models
years starting at 2026, so this reliably broke those slides once `--startyear`
started actually varying per batch (see `run_cepm.ps1`'s new
`-x`/`--compare-cases` auto-detected `--startyear`, below).

### Files changed:

- `postprocessing/compare_cases.py` — replaced the five hardcoded `2020` literals
  with the existing `startyear` variable; also fixed a stale
  `### Annotate the 2020 value` comment on an unrelated line that was already
  using `startyear` correctly.

### Reference:

[`known-reeds-issues.md`](known-reeds-issues.md)

### What to test in new releases:

- Has upstream fixed these literals itself? If so, drop our patch and take
  upstream's version to shrink the diff.
- Re-run `compare_cases.py` (or `run_cepm.ps1 -x`) against a batch whose
  `yearset` does not include 2020 after any rebase that touches these plotting
  functions, since upstream's own default `--startyear` is 2020 and won't
  exercise this path.

## Minor and cosmetic

### Description of issue:

Small changes with no effect on model results.

### Files changed:

- `reeds/resource_adequacy/reeds2pras/README.md` — corrects the test-run paths
  (`ReEDS/reeds2pras/test` to `ReEDS/reeds/resource_adequacy/reeds2pras/test`)
  after upstream relocated the vendored ReEDS2PRAS tree without updating its
  README.
- `cases_small.csv` — `endyear` 2030 to 2029.

### Reference:

n/a

### What to test in new releases:

- If upstream fixes its own reeds2pras README paths, drop our version to keep the
  vendored tree byte-identical to upstream. That tree is otherwise nearly
  pristine, which is what keeps future ReEDS2PRAS syncs cheap — see Issue 4 of
  [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md).

# Custom CEPM inputs and changes to ReEDS files

We also implement several custom inputs to our CEPM scenarios, which add new
input files and also change some underlying ReEDS files. These should all have
documentation in [`preprocessing/`](preprocessing/), and must meet the criteria
in [`preprocessing/input-requirements.md`](preprocessing/input-requirements.md).

## Updated CAPEX for gas resources

### Description:

Regression-based 2026-2032 capex forecast for CCGT and CT gas plants built from
the Halcyon Gas Power Plant Tracker (17 July 2026), replacing ATB's cost
trajectory with one drawn from the current project pipeline. `capcost` is
overwritten for `Gas-CC` and `Gas-CT` in 2026-2032 only; all other gas
technologies and years keep their ATB values, and `gas_ATB_2024_moderate.csv` is
left unmodified.

### Input files created:

- `inputs/plant_characteristics/gas-ccgt_CEPM_low.csv` — CCGT low-cost scenario
- `inputs/plant_characteristics/gas-ccgt_CEPM_high.csv` — CCGT high-cost scenario
- `inputs/plant_characteristics/gas-ccgt_CEPM_all.csv` — CCGT all-data (mid /
  reference) scenario

Gas-CT uses the same CT forecast in all three. Selected via `plantchar_gas`.

### Underlying ReEDS files changed:

- `cases.csv` — `plantchar_gas` description amended to note that upstream options
  start with `gas_` while RMI/CEPM options start with `gas-ccgt_`. The `Choices`
  pattern already admitted the new names, so no validation change was needed.
- `inputs/plant_characteristics/dollaryear.csv` — three new rows registering all
  three files as `2022` dollars.

`runfiles.csv` needed no change: its
`inputs/plant_characteristics/{plantchar_gas}.csv` template resolves these by
name.

### Reference:

[`preprocessing/gas_capex_forecast/`](preprocessing/gas_capex_forecast/)

### What to test in new releases

- Does `dollaryear.csv` still exist in the same location and format, and are our
  three rows still present after the rebase? A dropped row stays silent until
  costs come out wrong by an inflation factor.
- Has the `Choices` pattern for `plantchar_gas` in `cases.csv` become stricter
  (an explicit list rather than a prefix pattern)? If so, our filenames must be
  added to it.
- Has upstream changed the ATB vintage, or the columns/units in
  `gas_ATB_2024_moderate.csv`? Our files are derived from that shape, so a schema
  change means regenerating them.
- Confirm the notebooks still run and reproduce the committed CSVs.

## Updated load forecasts for data centers

### Description:

State-level data center load-site inputs for all 48 contiguous states, built from
EPRI Powering Intelligence projections in three scenarios (Low / Medium / High),
extended to 2032. These are the load-site inputs the national CEPM cases actually
run with — `cases_cepm.csv` currently selects
`st_epri_medium_extended_to_2032`.

### Input files created:

- `inputs/load/loadsite_st_epri_low_extended_to_2032.csv`
- `inputs/load/loadsite_st_epri_medium_extended_to_2032.csv`
- `inputs/load/loadsite_st_epri_high_extended_to_2032.csv`

Long format (`*loadsitereg,t,MW`), 48 states, 2026-2032. Selected via
`GSw_LoadSiteTrajectory`, and only staged when `GSw_LoadSiteCF > 0`.

Also added as reference fixtures for the large-load-site feature:
`inputs/load/loadsite_st_NMtest1.csv` and
`inputs/load/loadsite_transreg_WCtest1.csv` (single-region test cases for
optimized large-load placement).

A New-Mexico-only variant exists in
[`preprocessing/dc_load_nm/`](preprocessing/dc_load_nm/) but is superseded by the
all-states pipeline; its output is not committed and no case selects it.

### Underlying ReEDS files changed:

None. `runfiles.csv`'s existing `loadsite_{GSw_LoadSiteTrajectory}.csv` template
picks these up by name, and that switch's `Choices` entry is a generic pattern
(`^(nercr|transreg|transgrp|cendiv|st|interconnect|country|usda_region)_.*$`)
that already admits any `st_*` identifier. No `dollaryear.csv` entry is needed —
load sites are MW, not monetary values.

### Reference:

[`preprocessing/datacenter_load_forecast/`](preprocessing/datacenter_load_forecast/)

### What to test in new releases:

- Has loadsite's compatibility changed? Specifically: is the
  `loadsite_{GSw_LoadSiteTrajectory}.csv` template still in `runfiles.csv`, is
  the `Choices` pattern still permissive, and does `GSw_LoadSiteCF` still gate
  staging?
- Are we changing the underlying load forecast / would that double-count data
  center loads? Check whether upstream's default load projection has absorbed
  data center growth, which would double-count against our load sites.
- Is the expected long-format schema (`*loadsitereg,t,MW`) unchanged?

## Cumulative tech-group investment caps (`GSw_CEPM_TgCap`)

### Description:

Two purpose-built GAMS equations that cap **cumulative** new investment by
technology group at a ceiling harvested from a *reference* ReEDS run — the
mechanism behind the two-step `*_baseline` → `*_limitre` + `*_optimized` workflow,
where `_limitre` is held to the baseline's own wind/solar/storage buildout while
`_optimized` runs free.

Everything is **additive**: no upstream line is edited. The equations are modeled
line-for-line on `eq_interconnection_queues`, which already has the right shape
(cumulative over `tt`, guarded by `tmodel(tt) or tfix(tt)` so it behaves in
ReEDS' sequential solve). Two scopes, either of which may be left empty:
`eq_cepm_tg_cap_sys(tg)` system-wide and `eq_cepm_tg_cap_reg(tg,r)` per-region;
if both are populated, both bind.

Three things distinguish these from upstream's `eq_growthlimit_absolute`, which
was the obvious candidate and cannot do this job:

- **Cumulative, not per-year**, so there is no year-gap arithmetic — and
  therefore none of the final-year infeasibility documented in
  [`known-issues.md`](known-issues.md).
- **Written in MW_ac** — `INV` is divided by `ilr(i)` inside the sum — so the cap
  CSV, `cap_new_out`, and every comparison plot are in the same units and the
  harvest script does no conversion. `INV` itself is MW_dc for UPV
  (`ilr_utility = 1.34`).
- **Counts what `cap_new_out` counts**: `INV + INV_REFURB` *plus* the
  upgrade-derate-weighted `UPGRADES − UPGRADES_RETIRE`. Copying
  `eq_interconnection_queues`' `INV + INV_REFURB` alone would have left a real
  hole, since upgrade techs inherit `tg` membership from the tech they upgrade
  *to* and `upgrade_link.csv` contains `hydED → pumped-hydro` — a storage ceiling
  could have been evaded by upgrading hydro instead of building batteries.

**A cap value of 0 means "no cap", not "no builds"** — GAMS stores no record for
a zero, so an explicit `0` is indistinguishable from an absent row and the
equation's `$` guard drops it. `make_tg_cap.py` writes a `0.001` MW floor
instead. For a genuine permanent zero, use `bannew(i)`.

Two `abort` guardrails in `b_inputs.gms`, both gated on `Sw_CEPM_TgCap` so they
can never affect an unrelated run: one for `ilr(i) = 0` on an investable tech
(the equations divide by it), and one for "switch on but both cap files empty",
which is exactly what a failed or skipped harvest step looks like and would
otherwise solve happily and completely uncapped. **Both need
`$onImplicitAssign`** — in a healthy run the diagnostic parameter has no records
and the unused cap file is legitimately empty, and referencing an all-empty
symbol is GAMS error 141. Without the directive these guardrails abort *every*
run.

### Input files created:

- `inputs/growth_constraints/cepm_tg_cap_sys_none.csv` — header-only (`*tg,MW`)
- `inputs/growth_constraints/cepm_tg_cap_reg_none.csv` — header-only (`*tg,r,MW`)

`none` is the default `cepmtgcapscen` and the pair every non-capped case uses.
Real ceilings are **generated per batch** by
[`scripts/make_tg_cap.py`](scripts/make_tg_cap.py) from a completed reference run
and deleted afterwards, so they are deliberately not committed.

### Underlying ReEDS files changed:

- `reeds/core/setup/c_model.gms` — +2 equation declarations (near line 176) and
  one equation-definition block immediately after `eq_interconnection_queues`.
- `reeds/core/setup/b_inputs.gms` — +2 `$onempty` parameter blocks next to the
  existing growth limits, plus the two guardrail `abort`s described above.
- `reeds/input_processing/runfiles.csv` — +2 rows staging
  `cepm_tg_cap_{sys,reg}_{cepmtgcapscen}.csv` into `inputs_case/`.
- `cases.csv` — +3 rows: `cepmtgcapscen` (default `none`), `GSw_CEPM_TgCap`
  (default `0`), `GSw_CEPM_TgCapStartYear` (default `2026`).

No `copy_files.py` hook, deliberately: `runfiles.csv` changes by *added rows*
across releases, while `copy_files.py` is the most-churned file in the tree.
The two `GSw_` switches need no GAMS plumbing at all —
`reeds.io.write_gswitches` auto-emits `scalar Sw_X` for every numeric `GSw_X`.

### Departure from convention worth knowing: both rows are non-region rows

The regional file carries an `r` column but is registered with `region_col`
**blank** and `aggfunc`/`disaggfunc` both `ignore`, putting it on
`copy_files.py`'s plain-copy path rather than the region pipeline. This is
deliberate and was reversed from an earlier draft that used
`region_col=r, aggfunc=sum, fix_cols=tg, wide=1`.

The region machinery exists to roll **county-resolution upstream inputs** up to a
run's zones: `write_region_indexed_file` calls
`reeds.spatial.upscale_from_county_to_zone` unconditionally whenever
`aggfunc != 'ignore'`, and that function maps the region column through a
five-digit-FIPS county index. Our cap file is the opposite kind of artifact — it
is harvested from a **completed run at that run's own resolution**, so its
regions are already model regions (`p27`, `z28`, …). The `.map()` would return
`NaN` for every row and the following `groupby` would drop them all, delivering
an **empty** file to `inputs_case/`. Worse, that failure is silent: if the run
also has a system-scope cap, the empty-file guardrail does not fire, and the run
reports success while capping less than asked.

A related consequence: the regional GAMS symbol is a long-format `parameter` in
list form, not a `table`, so both CSVs are long and a header-only file stays
trivially valid under `$onempty`.

**General rule for this fork:** `runfiles.csv`'s region columns are for upstream
county-resolution inputs. Any CEPM file harvested from a finished run is already
at model resolution and belongs on the non-region path.

### Reference:

[`guidance/two-step-re-limited-runs.md`](guidance/two-step-re-limited-runs.md)
(design, decisions D1-D8, and the full test record),
[`guidance/tech-limit-options.md`](guidance/tech-limit-options.md) (why the three
existing mechanisms don't fit), [`known-issues.md`](known-issues.md) (the
`eq_growthlimit_absolute` final-year infeasibility),
[`scripts/make_tg_cap.py`](scripts/make_tg_cap.py) (the harvest script)

### What to test in new releases:

- **Is the non-region/region split still keyed on `region_col` being
  blank/`ignore`?** Verified byte-identical at `2026.08.03` and at
  `upstream/main` (`1f73bd23`, 2026-09-01), but this is the single load-bearing
  assumption behind both `runfiles.csv` rows. If upstream ever routes every row
  through the region pipeline, our regional cap goes silently empty.
- **Does `row['filepath'].format(**sw)` still perform the `{cepmtgcapscen}`
  substitution?** That is how a per-batch ceiling reaches a case at all.
- **Is `eq_interconnection_queues` unchanged?** It is both the template these
  equations copy and the anchor they are inserted after. Byte-identical at
  `upstream/main` as of 2026-09-01.
- **Is `cap_new_out`'s definition unchanged?** The equations deliberately mirror
  it term for term; if upstream changes what counts as new capacity, the ceiling
  and the reported quantity stop measuring the same thing. Also byte-identical at
  `upstream/main`.
- **Is `ilr(i)$[valcap_i(i)] = 1` still assigned to every investable tech?** The
  ilr guardrail's premise, and the reason a division by `ilr(i)` is safe.
- **Expect `b_inputs.gms` merge conflicts.** 1,210 lines were touched between our
  base and `upstream/main`; both insertion points will likely need re-placing by
  hand. `c_model.gms` is far calmer (164 lines) and should apply cleanly.
- **Watch the `inputs.h5` migration.** `GAMStype=parameter` rows in
  `runfiles.csv` went 1 → 1 → 11 across `2026.06.18` → `2026.08.03` →
  `upstream/main`, with `write_non_region_file` now routing
  `GAMStype in ['set','parameter']` to `write_csv_to_inputs_h5`. The
  growth-constraint parameters have not moved yet, so the `$include` block is
  still idiomatic. If they do, converting is mechanical: fill
  `GAMStype`/`GAMSname` on our two rows and drop the `$include`.
- **Re-run T2 and T3** from
  [`guidance/two-step-re-limited-runs.md`](guidance/two-step-re-limited-runs.md)
  (test T10). T2 — switch off, byte-identical to a pre-change baseline — is the
  cheap one and catches any accidental coupling. T3 — a run capped at its own
  harvested buildout must reproduce itself — is the one that proves units,
  tech-group mapping and upgrade inheritance all still line up.

# CEPM documentation and functionality

## GitHub repo-level ENABLE_GAMS_CI variable and workflow changes

### Description:

The `run-ReEDS` and `run-R2X` CI jobs need a GAMS license, which GitHub-hosted
runners do not have. Both jobs are gated on a repo-level **configuration
variable** so they can be toggled without a commit; those checks are instead
reproduced on-prem per
[`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md).

The gate reads `vars.ENABLE_GAMS_CI`, which is populated **only** from
GitHub-side configuration (Settings → Secrets and variables → Actions →
Variables, or `gh variable set`) — never from anything declared in the workflow
file. It is currently `false`, so both jobs skip on every push and PR.

Two footguns worth knowing. An unset variable evaluates to an empty string rather
than erroring, so deleting it silently skips both jobs while still reporting a
green check. And the comparison is a case-sensitive string match against
`'true'`, so `True`, `TRUE`, or `1` will not enable it.

Note that workflow files seem to automatically change the commit SHA that accompanies some of the workflow steps--this is not something we need to worry about when updating ReEDS releases.

### Files included:

- `.github/workflows/python-app.yaml` — `if:` conditions on the `run-ReEDS` and
  `run-R2X` jobs, plus a comment in the workflow-level `env:` block recording
  where the variable actually lives. (An earlier revision also set
  `ENABLE_GAMS_CI: 'false'` as a workflow `env:` value; that had no effect,
  since `env:` populates the `env` context and not `vars`, and it has been
  replaced by the comment.)

### Reference:

[`guidance/internal-ci-testing.md`](guidance/internal-ci-testing.md); current
value via `gh variable list --repo RMI/ReEDS-CEPM`

### What to test in new releases:

- Did upstream rename, split, or add GAMS-dependent jobs? Any new job needing
  GAMS must get the same `vars.ENABLE_GAMS_CI` gate, or it will fail on every PR.
- Do the existing `if:` conditions survive the rebase? A merge that takes
  upstream's side restores unconditional execution and turns CI red.
- Does the variable still exist at the repo level? It is not version-controlled,
  so it can be deleted without leaving any trace in the repo.
- Don't worry about changes to the alphanumeric SHAs after the steps in the workflow files.

## Using uv instead of mamba for environment/package management

### Description:

CEPM manages the Python environment with [uv](https://docs.astral.sh/uv/) rather
than conda/mamba. Upstream ships `environment.yml`; we keep that file for
reference and upstream parity but resolve dependencies from `pyproject.toml` /
`uv.lock`, pinned to Python 3.11. Because ReEDS itself expects conda-style
environment variables, `run_cepm.ps1` sets `CONDA_DEFAULT_ENV=reeds2` and
`CONDA_PREFIX` to the uv venv path so the model's own checks pass.

`environment.yml` and `pyproject.toml` are kept in sync **by hand**, with drift
reported by [`scripts/check_env_sync.py`](scripts/check_env_sync.py) against a
known-accepted allowlist.

### Files included:

- `pyproject.toml` — project metadata and dependencies
  (`requires-python = "==3.11.*"`)
- `uv.lock` — resolved lockfile
- `.python-version` — `3.11`, written by `uv python pin`. Note this file is both
  committed *and* listed in `.gitignore`; because it is tracked, the ignore rule
  has no effect. Worth reconciling one way or the other.
- `hourlize/pyproject.toml` — trailing-whitespace cleanup only
- `.gitignore` — ignores `.python-version` and `ReEDS.egg-info/`
- [`scripts/check_env_sync.py`](scripts/check_env_sync.py) — drift checker
- [`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md) — the sync procedure
  and accepted-drift list

### Reference:

[`guidance/UV_MAMBA_GUIDE.md`](guidance/UV_MAMBA_GUIDE.md),
[`scripts/check_env_sync.py`](scripts/check_env_sync.py)

### What to test in new releases:

- Does the environment still resolve? Run `uv sync --extra dev` on a clean
  checkout.
- Did Python version expectations change? If upstream's `environment.yml` moves
  off 3.11, update `requires-python` and re-pin.
- Did upstream add, remove, or re-pin any dependency in `environment.yml`? Each
  change has to be mirrored into `pyproject.toml` by hand; run
  `check_env_sync.py` and reconcile anything not on the allowlist.
- Has upstream adopted its own root `pyproject.toml`? If so, ours conflicts
  directly and needs merging rather than overwriting.
- Does ReEDS still read `CONDA_DEFAULT_ENV` / `CONDA_PREFIX`? If upstream drops
  those checks, the shims in `run_cepm.ps1` can go.

## run_cepm helper script

### Description:

A PowerShell wrapper that runs the whole CEPM setup-and-launch sequence in one
command: verifies GAMS is on `PATH` and licensed, verifies Julia is exactly
1.12.1, sets the conda-style environment variables ReEDS expects, pins Python
3.11 and runs `uv sync --extra dev`, instantiates Julia dependencies (offline
fast path first, full instantiate as fallback), warns on `environment.yml` to
`pyproject.toml` drift, then launches `runreeds.py` forwarding all remaining
arguments. It also sends best-effort ntfy.sh notifications (topic
`rmi-cepm-runs`) before and after the run.

It intercepts `-b/--BatchName` and `-c/--cases_suffix` so it can name them in
notifications, then forwards them to `runreeds.py` unchanged. Bootstrap-only
flags: `-y/--bypass` (skip `uv sync` and Julia instantiate), `-q/--quiet` (no
notifications), `-u/--user <name>`, `-x/--compare-cases`, `-o/--compare-only`,
and `-m/--multistep <stem>` (plus `--harvest-args`).

`-m/--multistep` replaces the single `runreeds.py` call with the two-phase
baseline-constrained sequence — run `<stem>_baseline`, harvest a capacity ceiling
from its outputs, then run `<stem>_limitre` and `<stem>_optimized` under one batch
name — using the tech-group caps documented above. Two behaviors of
`runreeds.py` make this less trivial than it looks, and both are worked around
rather than fixed: it **returns exit code 0 even when a case's solve aborted**, so
phase A is gated on `outputs/outputs.h5` existing rather than on the exit code;
and it **prompts interactively for a worker count** whenever more than one case is
requested, which would hang a background run, so phase B is given
`--simult_runs 2` explicitly. Per-batch generated files (the cap CSVs and a cases
file) are deleted in a `finally`.

### Files included:

- [`../run_cepm.ps1`](../run_cepm.ps1) — the script; lives at the repo root so it
  is callable as `.\run_cepm.ps1`
- [`scripts/check_env_sync.py`](scripts/check_env_sync.py) — invoked at step 7

### Reference:

[`../run_cepm.ps1`](../run_cepm.ps1), [`scripts/`](scripts/), and the quick-start
section of the [root README](../README.md)

### What to test in new releases:

- Does the environment still resolve? Did Python version expectations change? Do
  we need to change the environment variables that the script automatically
  sets?
- Has the required Julia version moved off 1.12.1? The script hard-fails on any
  other version; check `JULIA_VERSION` in `.github/workflows/python-app.yaml`
  and upstream's install docs.
- Have `runreeds.py`'s flags changed — particularly `-b/--BatchName` and
  `-c/--cases_suffix`, which the script parses itself, and any new short flag
  that could collide with `-y`, `-q`, or `-u`?
- Is `runreeds.py` still the entry point, still at the repo root, still under
  that name?

## CEPM documentation

### Description:

CEPM-specific documentation is collected under [`CEPM/`](./README.md) rather than
scattered through the upstream tree, so the fork's surface area stays reviewable
against upstream. Two documentation files nonetheless live in upstream locations,
because that is where readers and tools look for them.

### Files included:

- `README.md` (repo root) — rewritten as "ReEDS for CEPM": what CEPM is and how
  it differs from ReEDS, a CEPM quick-start (uv/Python, GAMS, Julia, environment
  setup, large input files, PowerShell runtime, running the model), and a
  troubleshooting section.
- `AGENTS.md` (repo root) — coding-agent guide: project structure, environment,
  build/run commands, testing, run flow, code style, debugging notes, key
  subsystems, data handling, and git workflow.
- `CONTRIBUTING.md` (repo root) - Added a short preamble to guide CEPM contributors.
- [`CEPM/`](README.md) — everything else, indexed by
  [`CEPM/README.md`](README.md).

### Reference:

[`CEPM/README.md`](README.md)

### What to test in new releases:

- Did upstream substantially rewrite the root `README.md`? It will conflict every
  time; decide deliberately whether to re-apply the CEPM version or merge
  upstream's new content into it.
- Has upstream added its own `AGENTS.md` or `CLAUDE.md`? If so, merge rather than
  overwrite.
- Do the quick-start steps still work end to end on a clean clone — particularly
  the install commands, the Julia version, and the large-input-file instructions?
- Do the CEPM docs still describe reality? On a rebase, re-check
  [`known-reeds-issues.md`](known-reeds-issues.md)'s "Fixed upstream?" verdicts, which are
  pinned to a specific upstream tag.
- Is the `CONTRIBUTING.md` guidance still up-to-date?

## Custom cases files, including cases_cepm.csv

### Description:

CEPM's own case definitions, kept in a separate file rather than as edits to
upstream's `cases.csv`. `runreeds.py` already supports this through its
`cases_{suffix}.csv` convention, so the file is picked up with `-c cepm` /
`--cases_suffix cepm` and needs **no upstream code change** — `cases.csv` stays
as the untouched switch-defaults reference.

Current cases: `WECC-SW_{baseline,limitre,optimized,dcloco2}`,
`SERTP_{baseline,limitre,optimized,dcloco2}`,
`NM_optimized_{2yrs,3yrs,LLtest}`, `USA_gas_mvp_NOTE-DEPRECATED`, and
`USA_optimized_mvp`. Set a case's `ignore` row to `1` to skip it.

**`_dcload` was removed for both stems, 2026-09-03.** `<stem>_optimized` — added
for the two-step workflow — was an exact copy of `<stem>_dcload`: the same
scenario under two names, because the `_optimized` convention postdates
`_dcload`. `_optimized` is the surviving name. The `_dcloco2` columns are
independent and unaffected; completed runs under the old names are untouched.

Both `WECC-SW` and `SERTP` therefore support `run_cepm.ps1 -m <stem>` as of
2026-09-03. The remaining stems (`NM_*`, `USA_*`) do not, and `-m` will refuse
with a clear message naming the missing columns.

Two things to know about the two-step columns. They are reached through
`run_cepm.ps1 -m`, which uses `-s` and therefore overrides `ignore`, so they are
marked `ignore=1` and never picked up by an ordinary `-c cepm` batch.
`WECC-SW_limitre` also ships with `GSw_CEPM_TgCap=1` and `cepmtgcapscen=none`,
which means running it *without* `-m` (i.e. without a harvested ceiling)
deliberately aborts at the empty-cap-files guardrail rather than solving
uncapped — that is the safety property, not a misconfiguration.

**`cleanup_level` is deliberately 0 for every case — do not raise it.**
`runreeds.py:959-967` blocks on `input('Proceed? y/[n]: ')` (defaulting to `n`,
which quits) whenever **any** case in the file has `cleanup_level >= 1` and
`--skip_checks` was not passed. The check runs at launch, and because `-s`
leaves ignored cases in `df_cases` (`runreeds.py:899-905`) it scans *every*
column — not just the ones being run. So a single `cleanup_level=2` anywhere in
this file hangs a background or CI run, including any `-m` batch, on a prompt
that is never displayed.

### Files included:

- `cases_cepm.csv` — the case definitions
- `cases.csv` — unchanged apart from the `plantchar_gas` description noted above

### Reference:

[`preprocessing/`](preprocessing/) for the inputs these cases select;
[`guidance/reeds-data-sources.md`](guidance/reeds-data-sources.md) for how a
switch value becomes an input file path

### What to test in new releases:

- Did any switch we set get **renamed, removed, or have its `Choices`
  tightened**? `runreeds.py` validates every requested case's switches up front,
  so one stale switch name blocks the entire launch batch.
- Did upstream change a switch's **default**? Blank cells in `cases_cepm.csv`
  inherit from `cases.csv`, so an upstream default change silently changes our
  cases.
- Is the `cases_{suffix}.csv` convention still supported by `runreeds.py`?
- Re-run at least one case through `copy_files.py` to confirm the switch
  combination still initializes; see
  [`guidance/SUBNATIONAL_REGION_SUPPORT.md`](guidance/SUBNATIONAL_REGION_SUPPORT.md)
  for which `GSw_ZoneSet`/`GSw_Region` combinations are known to work.

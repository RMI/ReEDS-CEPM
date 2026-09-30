# How `GSw_LoadSite{CF,RA,Trajectory}` wire together

**Scope:** how the three `GSw_LoadSite*` switches drive ReEDS's "optimally
sited load" feature (used by CEPM for data-center/large-load growth) — what
each one actually controls, how the trajectory input file is selected and
scoped, and what happens if that file's regions don't match the run's own
`GSw_Region`/`GSw_ZoneSet`.

**Short version:** all three switches gate one mechanism — the GAMS
variables `CAP_LOADSITE`/`INV_LOADSITE`/`OP_LOADSITE`
(declared in `reeds/core/setup/c_model.gms`). `GSw_LoadSiteTrajectory` picks *what
and where* load to site (a file plus an implied hierarchy level);
`GSw_LoadSiteCF` picks *whether/how* the optimization sites it (off /
flexible / inflexible); `GSw_LoadSiteRA` picks *whether* the result counts
toward PRAS resource-adequacy accounting, and only matters when
`GSw_LoadSiteCF=1`. The hierarchy level implied by `GSw_LoadSiteTrajectory`
does **not** need to match the run's `GSw_Region`/`GSw_ZoneSet`, and a
trajectory file with regions outside the run's own scope won't break the
run — those rows are silently dropped during input processing.

## The three switches

| Switch | Type | Default | What it does |
|---|---|---|---|
| `GSw_LoadSiteTrajectory` | string, regex-constrained (`cases.csv`) | `country_test` | Selects `inputs/load/loadsite_{value}.csv` and, via the prefix before its first `_`, the hierarchy level (`GSw_LoadSiteReg`) siting is constrained at. |
| `GSw_LoadSiteCF` | float | `0` | `0` = feature off. `(0,1)` = flexible load (must average this capacity factor annually, can shift hourly). `1` = inflexible load (flat capacity, no hourly variable). |
| `GSw_LoadSiteRA` | 0/1 | `1` | Only has an effect when `GSw_LoadSiteCF=1`: whether the solved `CAP_LOADSITE` gets added into PRAS's resource-adequacy load. No GAMS presence at all — Python/PRAS-only. |

In `cases_cepm.csv` every `_limitre`/`_optimized` case runs `GSw_LoadSiteCF=1`,
`GSw_LoadSiteRA=1` with `GSw_LoadSiteTrajectory=st_epri_medium_extended_to_2032`;
`_baseline` cases leave load siting off.

## `GSw_LoadSiteCF`: the master on/off + behavior switch

Numeric, so it becomes the GAMS scalar `Sw_LoadSiteCF` via the generic
`write_gswitches()` mechanism (`reeds/io.py`). It gates:

- The load balance (`eq_loadcon` in `c_model.gms`) — adds `OP_LOADSITE` (if
  `0<CF<1`) or `CAP_LOADSITE` (if `CF=1`) to total system load.
- `eq_loadsite_inv` (`c_model.gms`) — `CAP_LOADSITE` accumulates
  from `INV_LOADSITE` like any other capacity stock. Active whenever
  `Sw_LoadSiteCF` is nonzero.
- `eq_loadsite_cap`/`eq_loadsite_op` (`c_model.gms`) — active only
  for `0<Sw_LoadSiteCF<1`: cap hourly `OP_LOADSITE` by `CAP_LOADSITE`, and
  force the annual-average utilization up to the target CF (obeying
  stress-period weighting via `hours(h)`).
- `eq_loadsite_siting` (`c_model.gms`, see below) — active whenever
  `Sw_LoadSiteCF` is nonzero.
- the `loadsite_annual.csv` row's `required_if` in `runfiles.csv` — `loadsite_annual.csv` is only
  required/copied when `float(sw.GSw_LoadSiteCF) > 0`.
- `reeds/resource_adequacy/prep_data.py` (`main()`) — PRAS only folds
  `CAP_LOADSITE` into its load series when `GSw_LoadSiteCF` is (numerically)
  exactly `1` **and** `GSw_LoadSiteRA` is on; PRAS can't represent a
  time-varying flexible load, so a fractional CF is invisible to it
  regardless of `GSw_LoadSiteRA`.
- `reeds/results.py` (`calc_sited_load()`, `calc_annualload()`),
  `postprocessing/single_case_plots.py`, `postprocessing/compare_cases.py` — reporting/plotting only
  activated when this switch is nonzero.

## `GSw_LoadSiteRA`: PRAS-only, and conditional on `GSw_LoadSiteCF=1`

Its own description says as much ("if set to 1 and `GSw_LoadSiteCF`=1"), and
the code enforces it literally:

```python
# reeds/resource_adequacy/prep_data.py, main()
if (
    np.isclose(float(sw.GSw_LoadSiteCF), 1)
    and len(ra_cap_loadsite)
    and int(sw.GSw_LoadSiteRA)
):
    pras_load += ra_cap_loadsite
```

There is no `Sw_LoadSiteRA` scalar anywhere in the `.gms` files — this
switch never reaches GAMS. If `GSw_LoadSiteCF` is `0` or fractional,
`GSw_LoadSiteRA`'s value is inert.

## `GSw_LoadSiteTrajectory`: file selection and region scoping

### The filename's structure

`inputs/load/loadsite_{GSw_LoadSiteTrajectory}.csv`, where the switch value
is `{level}_{anything}` and only the `{level}` prefix (before the first
`_`) is ever parsed:

```python
# reeds/inputs.py, add_intermediate_switches()
new_switches[case]['GSw_LoadSiteReg'] = sw['GSw_LoadSiteTrajectory'].split('_')[0]
```

`{level}` must be one of `nercr|transreg|transgrp|cendiv|st|interconnect|
country|usda_region` (enforced by the regex in `cases.csv`). Everything
after the first `_` — `epri_medium_extended_to_2032`, `NMtest1`, `test`,
`WCtest1` — is free text with **no programmatic role**; it only has to make
the full string resolve to a real file. Existing files in `inputs/load/`:

- `loadsite_country_test.csv` — default, single-region (`USA`) test fixture.
- `loadsite_st_NMtest1.csv`, `loadsite_transreg_WCtest1.csv` — single-region
  test fixtures for New Mexico / WestConnect.
- `loadsite_st_epri_{low,medium,high}_extended_to_2032.csv` — real
  48-contiguous-state data-center peak-load forecasts derived from EPRI
  Powering Intelligence data by
  [`CEPM/preprocessing/datacenter_load_forecast/`](../preprocessing/datacenter_load_forecast/README.md).
  CEPM's active cases select the `medium` variant.

All share the schema documented in their own header comments:
`*loadsitereg,t,MW` — one row per (region, year).

### Pre-flight validation only checks the level, not the run's own scope

`reeds/checks.py` (`check_GSw_LoadSiteReg`, run from `check_switches`)
confirms the file exists and that every region label in it is valid **at
that hierarchy level nationally** (via `reeds.io.get_hierarchy()`, the full
national hierarchy). It does **not** check the labels against this
particular run's `GSw_Region` selection — a region that's a legitimate
national-level label but outside this run's modeled scope passes this check
without complaint.

### `copy_files.py` silently drops out-of-scope regions

`'loadsitereg'` is never one of the real hierarchy column names built from
this run's own subsetted hierarchy (`levels`, built in
`reeds/input_processing/copy_files.py`'s `get_regions_and_agglevel()`), so the `*loadsitereg` column falls through every
special-cased branch in `filter_data()` and hits the generic final one:

```python
# reeds/input_processing/copy_files.py, filter_data()
else:
    df = df.loc[df[region_col].isin(val_r_all)]
```

`val_r_all` (`get_regions_and_agglevel()` in `copy_files.py`) is the union of every label across
every hierarchy column (`r`, `st`, `cendiv`, `nercr`, `transreg`,
`transgrp`, `interconnect`, `country`, `usda_region`) — but restricted to
this run's own `hier_sub`, i.e. only the regions actually in scope for
`GSw_Region`/`GSw_ZoneSet`. Any trajectory row whose region label doesn't
belong to the run's own scope is dropped from `inputs_case/
loadsite_annual.csv` before it's ever written — **silently, with no log
message at any stage.**

The GAMS side stays consistent with this filtering rather than fighting it:
the `st`/`nercr`/etc. sets that `loadsitereg` aliases
(`alias(%GSw_LoadSiteReg%, loadsitereg)` in `reeds/core/setup/b_inputs.gms`) are themselves populated only from
that same run-scoped hierarchy data, so there's never a domain mismatch or
an `eq_loadsite_siting` equation forced to equal a nonzero value over an
empty region sum.

### The trajectory's hierarchy level is independent of `GSw_Region`/`GSw_ZoneSet`

Every model zone `r`, at *any* zoneset resolution, belongs to exactly one
label at every hierarchy level simultaneously, via the single joint set
`hierarchy(r,nercr,transreg,transgrp,cendiv,st,interconnect,country,
usda_region,h2ptcreg,hurdlereg,gasreg,ccreg)` (`b_inputs.gms`), from which every
`r_<level>(r,level)` mapping is derived generically
(`b_inputs.gms`) — including `r_st(r,st)`, regardless of what
`GSw_ZoneSet` produced `r`. `GSw_LoadSiteReg` just selects one of these:

```gams
* b_inputs.gms
r_loadsitereg(r,%GSw_LoadSiteReg%) = r_%GSw_LoadSiteReg%(r,%GSw_LoadSiteReg%) ;
```

This is the same idiom other region-level switches already use independent
of the run's own zoneset — `GSw_TransRestrict`, `GSw_PRMTRADE_level`,
`GSw_OpResTradeLevel` (`b_inputs.gms`) all do the identical
`r_%level%(r,%level%)` substitution. So a state-level (`st_...`) trajectory
works fine for a `GSw_Region=nercr/...` run at any zoneset — mixing hierarchy
levels between the trajectory and the run's own region/zoneset selection is
normal and supported, not a special case.

**Practical implication when mixing levels:** combined with the silent-drop
behavior above, only states with at least one zone inside the run's scope keep
their trajectory rows; states entirely outside it are dropped. If a state
straddles the run's boundary, `eq_loadsite_siting` still enforces that state's
**full** trajectory total, summed only over whichever of its zones are in scope
— concentrating the whole state target onto a subset of its zones rather than
diluting or erroring.

**Former WECC-SW case (cautionary example).** That run (`GSw_Region=nercr/WECC_SW`,
state-level trajectory) included only one Texas zone, `p59` (El Paso), so all of
Texas's statewide trajectory — 13,047.7 MW in 2032, ~76% of the run's load-site
demand — landed there; see the `v20260903h2qoff` entry in
[`../batch-log.md`](../batch-log.md). Current `st/` stems contain whole states,
so the state trajectory can't concentrate this way.

## `eq_loadsite_siting`: where trajectory and CF meet

```gams
* c_model.gms
eq_loadsite_siting(loadsitereg,t)
    $[tmodel(t)$Sw_LoadSiteCF$(not Sw_PCM)]..

    sum{r$[r_loadsitereg(r,loadsitereg)$val_loadsite(r)], CAP_LOADSITE(r,t) }
    =e=
    loadsite_annual(loadsitereg,t)
;
```

Total sited capacity within a `loadsitereg` bucket must equal the trajectory
file's number for that bucket/year exactly — the model is only free to
choose *which zone(s) within that bucket* host the capacity. `val_loadsite(r)`
(`b_inputs.gms`) is the set of zones eligible to host sited load at
all: any zone mapping into a `loadsitereg` bucket with nonzero trajectory
demand.

## Related

See [reeds-data-sources.md](reeds-data-sources.md) for the general
`runfiles.csv`/`copy_files.py` mechanism this switch relies on to turn a
switch value into an input file path.

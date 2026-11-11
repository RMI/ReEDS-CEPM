# Allocating state data-center forecasts to partial states by LPF
Written Date: 2026-11-11

**Scope:** a design for how CEPM could apportion its state-level data-center
load forecasts (`loadsite_st_*`) when a run includes only part of a state,
using ReEDS's own state-to-region load participation factors (`state_lpf`). It
covers the problem, the data ReEDS already has, the proposed rule, and the
files that would change. **Not implemented yet.** Read
[`loadsite-mechanism.md`](loadsite-mechanism.md) first for how load sites work.

**Short version:**

- Today, a run includes a state's **full** forecast even if only part of the
  state is in the run, and lets the model place all of it in whichever of the
  state's regions it likes. The worst case so far: WECC-SW put all of Texas's
  13 GW in El Paso (`p59`).
- ReEDS already computes each region's share of its state (`disagg_state_lpf.csv`
  in `inputs_case/`), normalized over **all** CONUS counties. So within a run, a
  state's shares sum to 1 if the whole state is present and to less than 1 if
  part of it isn't. That is the test for a partial state.
- **Proposed rule:** for a partial state only, (1) scale the state's forecast to
  the in-run share and (2) fix each in-run region's load sites at its share of
  the statewide forecast. States entirely in the run are left alone, so their
  load stays freely sited, as upstream does.
- Small change: one Python step that writes the shares, about 30 lines of GAMS
  in marked CEPM blocks, and one line in `runreeds.py`.
- **This doesn't fix p47** in the AZNM runs. New Mexico is entirely in those
  runs, so the rule leaves it alone (§6).

---

## 1. The problem

`eq_loadsite_siting` (`c_model.gms`) requires each state's load-site capacity to
equal its forecast, summed over whichever of its regions are in the run. The
model is free to choose the regions. Two consequences:

| Run | What happens |
|---|---|
| WECC-SW (`nercr/WECC_SW`) | Only `p59` (El Paso) of Texas is in the run. It receives Texas's **entire** statewide forecast: 13,047.7 MW in 2032, about 76% of the run's load-site demand, against El Paso Electric's real peak of about 2 GW. See [`loadsite-mechanism.md`](loadsite-mechanism.md). |
| AZNM (`st/AZ.NM`) | New Mexico is entirely in the run, but the model puts 98% of its forecast in `p47`, the small SPP region tied to the rest of the run by 200 MW. See [`st-AZNM/p47-stress-period-nonconvergence.md`](st-AZNM/p47-stress-period-nonconvergence.md) §6.2. |

This doc addresses the first. The second needs the extension in §6.

The current workaround for partial states is to scope the trajectory file by
hand ([`loadsite-mechanism.md`](loadsite-mechanism.md)), which has to be redone
for every region and forecast.

## 2. What ReEDS already provides

`copy_files.py`'s `write_disagg_data_files()` writes
`inputs_case/disagg_{population,state_lpf,geosize}.csv`. Each has one row per
county, with its model region `r`, its `state`, and `state_frac`: the county's
share of its state's total.

- **`state_lpf`** comes from `inputs/disaggregation/county_state_lpf.csv`: bus-level
  load participation factors from the NARIS nodal network (Energy Visuals),
  summed by county. It follows where load sits on the grid, including
  industrial load. `population` uses 2021 Census county estimates.
- **`state_frac` is normalized over all CONUS counties** (from the z134 county
  map), and counties outside the run are dropped afterward
  (`calculate_county_fractions()`). So summing `state_frac` by `(state, r)` over
  a run's rows gives each in-run region's share of the **whole** state, and the
  total for a state is the share of it that's in the run.
- `hourly_load.py`'s `reaggregate_to_model_regions()` already does exactly this
  sum, to split regular state load (`GSw_LoadAllocationMethod`). `reeds.io.get_disagg_data()`
  reads the file.

Example, AZNM (`v20261026drshed`):

| Share of state | p27 | p29 | z28 | p31 | p47 | Sum |
|---|---:|---:|---:|---:|---:|---:|
| AZ, `state_lpf` | 0.036 | 0.006 | 0.958 | | | 1.0 (whole state) |
| NM, `state_lpf` | | | | 0.648 | 0.352 | 1.0 (whole state) |
| NM, `population` | | | | 0.87 | 0.13 | 1.0 |

**Caveats on `state_lpf`:**

- `docs/sources_documentation.md` lists `county_state_lpf.csv` with no
  description, so its vintage is unknown.
- Counties without a high-voltage load bus have a share of 0. That doesn't
  matter at zone resolution, but at county resolution (`z3109`) some regions
  would get no data-center load.
- Data centers follow land, power, fiber and incentives. LPF (existing load) and
  population are both proxies.

## 3. The proposed rule

Applies only when the forecast is at state level (`GSw_LoadSiteReg=st`) and a
new switch is on.

For each state `s` with `in_run(s) = Σ_r share(s,r) < 1`, a **partial state**:

1. **Scale the target.** `loadsite_annual(s,t) ← loadsite_annual(s,t) × in_run(s)`.
   The run gets only the part of the forecast that belongs in it.
2. **Fix the regional split.** `CAP_LOADSITE(r,t) = share(s,r) × statewide(s,t)`
   for each in-run region `r` of `s`, where `statewide` is the unscaled
   forecast. These sum to the scaled target, so `eq_loadsite_siting` still holds.

States with `in_run(s) = 1` are untouched: one target, freely sited, as today.

**WECC-SW example:** if El Paso's `state_lpf` share of Texas is about 0.1 (to be
checked), `p59` gets about 1.3 GW in 2032 instead of 13 GW. The other 90% of
Texas's forecast belongs to ERCOT, which isn't in the run.

**Why fix the split rather than cap it?** A partial state's in-run regions are
usually few (often one), so there's little siting choice to keep. A fixed split
is transparent and makes a run reproducible from the forecast alone. A cap
(`≤ share × statewide × (1 + headroom)`) is a small variant if some freedom is
wanted later.

**Feasibility.** `CAP_LOADSITE` only accumulates `INV_LOADSITE ≥ 0`
(`eq_loadsite_inv`), so it can never decrease. A fixed split needs each state's
forecast to be non-decreasing, which `eq_loadsite_siting` already requires
upstream. Shares are fixed across years, so a non-decreasing forecast gives a
non-decreasing split.

**Tolerance.** Treat `in_run(s) ≥ 0.999` as whole, to absorb rounding.

## 4. Implementation

### 4.1 Switches (`cases.csv`)

| Switch | Values | Default |
|---|---|---|
| `GSw_CEPM_LoadSitePartial` | `0` = upstream behavior; `1` = apply §3 to partial states | `0` |
| `GSw_CEPM_LoadSiteBasis` | `state_lpf`, `population` | `state_lpf` |

The first is numeric, so `write_gswitches` makes `Sw_CEPM_LoadSitePartial`
available to GAMS with no other plumbing. The second is only read by the Python
step.

### 4.2 Python: write the partial-state shares

A new script, `CEPM/scripts/loadsite_partial_shares.py`, run after `copy_files.py`
(which writes the disagg files):

```python
import os, sys
import pandas as pd
sys.path.append(sys.argv[1])  # reeds_path
import reeds

reeds_path, inputs_case = sys.argv[1], sys.argv[2]
casedir = os.path.dirname(inputs_case)
sw = reeds.io.get_switches(casedir)
out = os.path.join(inputs_case, 'cepm_loadsite_share.csv')

rows = pd.DataFrame(columns=['st', 'r', 'share'])
if int(sw.get('GSw_CEPM_LoadSitePartial', 0)) and sw.GSw_LoadSiteReg == 'st':
    d = reeds.io.get_disagg_data(casedir, sw.GSw_CEPM_LoadSiteBasis)
    share = d.groupby(['state', 'r'])['state_frac'].sum().rename('share').reset_index()
    in_run = share.groupby('state')['share'].transform('sum')
    rows = share.loc[in_run < 0.999].rename(columns={'state': 'st'})
    for st, g in rows.groupby('st'):
        print(f'[cepm_loadsite] partial state {st}: {g.share.sum():.3f} in run, '
              + ', '.join(f'{r}={v:.3f}' for r, v in zip(g.r, g.share)))

# Always write the file (header-only when off), so the GAMS $include never fails
with open(out, 'w') as f:
    f.write('*st,r,share\n')
    rows[['st', 'r', 'share']].round(6).to_csv(f, header=False, index=False)
```

It logs every partial state it finds, so a run's `gamslog.txt` shows the
split. That also fixes the silent behavior noted in
[`loadsite-mechanism.md`](loadsite-mechanism.md).

### 4.3 Hook: `runreeds.py`

Input-processing scripts are listed in `runreeds.py` (the loop starting
`for s in ['copy_files', ...`), and each is run from the case's copy of
`reeds/input_processing/`. Two ways in:

- **Recommended:** after that loop writes the `copy_files` call, add one line
  that writes `python {reeds_path}/CEPM/scripts/loadsite_partial_shares.py
  {reeds_path} {inputs_case}` plus its error check. The script stays in `CEPM/`.
  The drawback is that it runs from the repo, not from the case's snapshot.
- Put the script in `reeds/input_processing/` and add its name to the list.
  The case snapshot then covers it, but it's a new file in the upstream tree.

Either way it's an upstream-file change, to be logged in
[`../reeds-to-cepm-log.md`](../reeds-to-cepm-log.md). `runfiles.csv` doesn't
need a row, since the script writes straight to `inputs_case/`, as
`make_tg_cap.py`'s outputs reach it.

### 4.4 GAMS: `b_inputs.gms`

In a marked CEPM block right after `val_loadsite` is defined:

```gams
*>>> BEGIN CEPM ADDITION ======================================================
* Partial-state load-site allocation (GSw_CEPM_LoadSitePartial). See
* CEPM/guidance/loadsite-partial-state-allocation.md.
$onempty
parameter cepm_loadsite_share(st,r) "--fraction-- CEPM: in-run region's share of a partial state"
/
$offlisting
$ondelim
$include inputs_case%ds%cepm_loadsite_share.csv
$offdelim
$onlisting
/ ;
$offempty

$onImplicitAssign
parameter cepm_loadsite_statewide(st,allt) "--MW-- CEPM: statewide load-site forecast before scaling" ;
cepm_loadsite_statewide(st,t)$sum{r, cepm_loadsite_share(st,r) } = loadsite_annual(st,t) ;
* scale partial states to their in-run share
loadsite_annual(st,t)$sum{r, cepm_loadsite_share(st,r) }
    = loadsite_annual(st,t) * sum{r, cepm_loadsite_share(st,r) } ;
$offImplicitAssign
*<<< END CEPM ADDITION ========================================================
```

`loadsite_annual` is declared over `loadsitereg`, an alias of `st` when
`GSw_LoadSiteReg=st`, so indexing it by `st` is valid in that case only. Guard
the block with `$ifthen %GSw_LoadSiteReg% == st` so a run at another level still
compiles. The Python step writes no rows in that case anyway.

### 4.5 GAMS: `c_model.gms`

A declaration in the CEPM equation-declaration block, and the equation in the
main CEPM block:

```gams
eq_cepm_loadsite_partial(r,t)
    $[tmodel(t)$Sw_LoadSiteCF$Sw_CEPM_LoadSitePartial$val_loadsite(r)
      $sum{st, cepm_loadsite_share(st,r) }$(not Sw_PCM)]..

    CAP_LOADSITE(r,t)

    =e=

    sum{st, cepm_loadsite_share(st,r) * cepm_loadsite_statewide(st,t) }
;
```

Each region is in one state, so the sum has one term.

### 4.6 Nothing else

PRAS picks up `CAP_LOADSITE` as before (`prep_data.py`), and reporting
(`loadsite_cap.csv`) is unchanged.

## 5. Testing

1. **Setup (`a_createmodel.gms`) on a WECC-SW copy.** Check the log line for
   Texas (only `p59`, and its share), the scaled `loadsite_annual('TX',t)`, and
   that AZ and NM aren't listed. Then repeat with the switch off: no rows, and
   `loadsite_annual` unchanged.
2. **A WECC-SW solve.** `p59`'s `loadsite_cap.csv` should equal share × Texas's
   statewide forecast in every year. Total load-site demand drops by Texas's
   out-of-run share.
3. **A whole-state run (AZNM) with the switch on.** It should match the switch
   off exactly: no partial states, no new rows, no change.

## 6. Open questions

- **p47 and whole states.** p47 is a partial `transgrp`, not a partial state, so
  this rule leaves New Mexico alone, and the model can still place 98% of New
  Mexico's load in p47. If that should change, the same machinery extends to
  whole states with a third switch value (`2` = apply the split to every state).
  That makes all load-site placement exogenous, a bigger modeling change, so it
  should be a deliberate choice. A cap (`≤ share × statewide × (1 + headroom)`)
  would keep some siting freedom. With `state_lpf`, p47 would get about 35% of
  New Mexico's forecast (about 228 of 649 MW in 2032) instead of 98%.
- **`state_lpf` or `population`.** They differ a lot where industrial load is
  large: 35% versus 13% for p47. Default to `state_lpf`, and note which was used
  in each batch.
- **Partial states in national runs.** None: every state is whole, so the switch
  does nothing there.
- **Upstream?** The partial-state problem isn't CEPM-specific. Any regional
  ReEDS run with a state-level load-site file hits it. Worth raising upstream
  once it's tested.

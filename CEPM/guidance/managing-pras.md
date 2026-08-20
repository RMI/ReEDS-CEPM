# Switch combinations for managing PRAS

**Scope:** which switches determine whether PRAS (`run_pras.jl`, via
`reeds/resource_adequacy/ra_calcs.py`) runs for a given solve year, how often,
and how expensive it is — and which switches people often *expect* to control
that but don't.

**Short version:** `GSw_PRM_CapCredit` does not disable PRAS. As long as a
solve year isn't skipped by `GSw_SkipRAyear`, `run_pras.jl` runs on **every**
solved iteration of that year regardless of `pras`, `GSw_PRM_CapCredit`, or
`GSw_PRM_StressModel` — because of how `GSw_PRM_StressIterateMax` gates both
the per-year iterate loop in `solve.py` and the PRAS-run condition in
`ra_calcs.py`. The only switch that reliably skips PRAS's actual Monte Carlo
compute while leaving everything else untouched is `pras_samples=0`.

## Where PRAS sits in the pipeline

```
solve.py:main()                         -- per solve year
  for iteration in range(GSw_PRM_StressIterateMax):   [solve.py:96]
    run_reeds(...)                      -- GAMS LP solve, then:
      ra_calcs.main()                   -- gated by GSw_SkipRAyear [solve.py:81]
        capacity_credit.reeds_cc()      -- only if GSw_PRM_CapCredit=1
        run_pras()                      -- gated below [ra_calcs.py:155]
        stress_periods.main()           -- gated below [ra_calcs.py:170-173]
```

Two independent subsystems live inside `ra_calcs.main()`:

1. **Capacity credit (ELCC)** — `capacity_credit.py`, controlled by
   `GSw_PRM_CapCredit`. Computes a marginal capacity-credit value for VRE/
   storage from load and CF time series alone. It never reads a PRAS output
   file.
2. **PRAS reliability simulation** — `run_pras()` plus `stress_periods.py`.
   Runs an hourly multi-year reliability simulation and uses its per-region
   EUE (expected unserved energy) output to (a) pick new "stress periods" —
   specific days added to the *next* solve year's temporal representation —
   and (b) decide which regions get a planning-reserve-margin (PRM) increment.

These two are not alternatives. Turning on (1) does not turn off (2).

## Switch reference

| Switch | Default | What it actually does |
|---|---|---|
| `GSw_SkipRAyear` | `2020` | Any solve year with `tnext <= this` skips *all* of `ra_calcs.main()` — capacity credit, PRAS, and stress periods — entirely (`solve.py:81`). This is the only clean "don't run any RA machinery yet" gate, typically used for early historical-ish years. |
| `GSw_PRM_StressIterateMax` | `5` | Max number of extra ReEDS↔PRAS iterations per solve year, used to add stress periods until `GSw_PRM_StressThreshold` is met. **Also gates whether the solve year runs at all** via `solve.py:96`'s `for iteration in range(int(sw.GSw_PRM_StressIterateMax))` — a value of `0` makes that loop execute zero times, so `run_reeds()` (the GAMS solve itself) is never called for that year via this path. `cases_test.csv` is the only case file in this repo observed setting it to `0`, and only for specific quick-test columns — don't set it to `0` for a case that needs a normal full solve without first confirming the run path you're using doesn't depend on this loop. |
| `pras` | `2` | Looks like it should gate PRAS (0=never, 1=final solve year only, 2=always), and it partly does — but see "The `pras` switch doesn't do what it looks like" below. |
| `pras_samples` | `100` | Number of Monte Carlo samples PRAS runs. **If `0`, the `.pras` file is still generated but the simulation itself is skipped** — this check lives inside `run_pras.jl`, independent of all the Python-level gating above, so it's the one lever that reliably skips PRAS's actual compute no matter how the other switches are set. |
| `GSw_PRM_StressModel` | `pras` | `'pras'` or a string starting with `'user'` (reads `inputs/temporal/stressperiods_{value}.csv` instead of running PRAS-based selection). Only affects whether `stress_periods.main()` derives new periods from PRAS's EUE output — it does not stop `run_pras()` itself from being called (see below). |
| `GSw_PRM_UpdateMethod` | `0` | `0`=no PRM update; `1`=static increment (`GSw_PRM_UpdateFraction`) applied to regions PRAS found failing; `2`/`3`=increment sized dynamically from PRAS's own shortfall-sample output. Even at `1`, *which* regions get the increment is still identified from PRAS's EUE results — only the increment's *size* is independent of PRAS. |
| `GSw_PRM_CapCredit` | `0` | `1`=value VRE/storage capacity toward the PRM constraint via ELCC (`capacity_credit.py`); `0`=rely on stress periods alone. Does not touch whether `run_pras()` or `stress_periods.main()` execute, beyond one narrow case (see below). |

## The `pras` switch doesn't do what it looks like

`ra_calcs.py:150-156`:
```python
pras_this_solve_year = {0: False, 1: True if t == max(solveyears) else False, 2: True}[int(sw['pras'])]
if pras_this_solve_year or int(sw.GSw_PRM_StressIterateMax):
    result = run_pras(...)
```
The `or int(sw.GSw_PRM_StressIterateMax)` clause is the catch: this code only
ever executes from inside the loop at `solve.py:96`, `for iteration in
range(int(sw.GSw_PRM_StressIterateMax))` — which only runs its body at all
when `GSw_PRM_StressIterateMax >= 1`. So at the point `ra_calcs.py:155` is
evaluated, `int(sw.GSw_PRM_StressIterateMax)` is guaranteed truthy (it's the
same fixed switch value that let the loop start in the first place) — meaning
`run_pras()` fires unconditionally, and `pras`'s own value never gets a chance
to matter. This is upstream's own code, byte-identical to
`upstream/main` — not something introduced by this fork.

Practical consequence: **setting `pras=0` or `pras=1` does not reduce how
often PRAS actually runs**, as long as the case solves normally (i.e.
`GSw_PRM_StressIterateMax` is at its default `5` or any other positive value).
`GSw_PRM_StressModel` and `GSw_PRM_CapCredit` don't help either — they only
affect the separate `stress_periods.main()` call just below, not the
`run_pras()` call itself.

## What actually changes PRAS's footprint

| Goal | Switch(es) | Caveat |
|---|---|---|
| Skip RA (and PRAS) for early years | `GSw_SkipRAyear` | Clean, no side effects — this is the intended mechanism. |
| Skip PRAS's Monte Carlo compute but keep the rest of the pipeline running | `pras_samples=0` | The `.pras` file (ReEDS2PRAS conversion) still gets built; only the simulation itself is skipped. The most reliable single-switch lever here. |
| Reduce how many ReEDS↔PRAS iterations happen per solve year | `GSw_PRM_StressIterateMax` (lower than default `5`) | Each iteration re-runs the full GAMS LP *and* PRAS, so this is usually the bigger cost lever than sample count — but see the "gotcha" above before setting it to `0`. |
| Reduce PRAS's per-run cost | `pras_samples` (fewer MC samples), `resource_adequacy_years` (fewer weather years), `pras_singlethread=0` (use available threads) | Standard PRAS-runtime knobs; don't change *whether* or *how often* it runs, just how long each run takes. |
| Value VRE/storage capacity via ELCC instead of (or in addition to) stress periods | `GSw_PRM_CapCredit=1` | Independent of all of the above — does not reduce PRAS usage. |

## One narrow case where `GSw_PRM_CapCredit` does matter

`ra_calcs.py:170-173`:
```python
if (
    ('user' not in sw['GSw_PRM_StressModel'].lower())
    or ((int(sw.GSw_PRM_StressIterateMax)) and int(sw['GSw_PRM_CapCredit']))
):
    reeds.resource_adequacy.stress_periods.main(sw=sw, t=t, iteration=iteration)
```
With the default `GSw_PRM_StressModel='pras'`, the first clause is already
true, so `stress_periods.main()` (and its read of PRAS's EUE output) runs
regardless of `GSw_PRM_CapCredit`. The only way `GSw_PRM_CapCredit` affects
this call is if `GSw_PRM_StressModel` is switched to a `'user...'` file *and*
`GSw_PRM_CapCredit=0` — in that combination alone, `stress_periods.main()` is
skipped entirely. `run_pras()` itself is unaffected either way (see above) —
PRAS still executes, its output just goes unused by the stress-period logic.

## Recipe: get as close as possible to "no PRAS"

There is currently no single switch that stops `run_pras.jl` from being
invoked on a normally-solving case. The closest achievable combination:

- `GSw_SkipRAyear` set past your last modeled year, if you don't need RA at
  all for the run — this is the only combination that skips PRAS outright.
- Otherwise, `pras_samples=0` (skip the Monte Carlo compute, keep the
  pipeline intact) plus `GSw_PRM_StressIterateMax=1` (only one ReEDS↔PRAS
  cycle per solve year instead of up to 5) is the practical minimum-PRAS
  configuration for a case that still needs the rest of the RA pipeline
  (capacity credit, stress-period bookkeeping, gdx handoff) to run normally.

## Related

See [SUBNATIONAL_REGION_SUPPORT.md](SUBNATIONAL_REGION_SUPPORT.md) Issue 4
for a separate, unrelated PRAS bug (crashes on genuinely single-zone
regions) — not a switch issue, a vendored-Julia-code gap.

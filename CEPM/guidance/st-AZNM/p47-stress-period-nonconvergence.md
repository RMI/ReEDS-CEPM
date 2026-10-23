# st-AZNM: p47 (SPP_South) stress-period non-convergence
**Written Date:** October 23, 2026

This note covers a problem in the `st/AZ.NM` CEPM runs. The PRAS stress-period loop never meets its reliability threshold, and that makes year-to-year results unstable. It started as a question about the baseline cases of two batches:

- `v20261009postcapex_st-AZNM_baseline` (commit `8b7a2652`)
- `v20261020tfnewq_st-AZNM_baseline` (commit `1c1fba68`)

Between them, 2032 onshore wind roughly halved, from 1,611 MW to 817 MW. That raised the question of why a change to interconnection-queue exemptions would move 2032 builds.

**Short answer:** the queue change doesn't act on 2032 directly. It slightly changes the 2029 fleet. In both runs, the stress-period loop runs to its iteration cap without converging, so which stress days it happens to add depends on that fleet. Those days drive the 2032 mix. The loop fails to converge because of a single region, **p47**.

## 1. What changed between the two runs

The only switch that differs is `GSw_CEPM_QueueExempt=3` in the newer run. The code diff between the two commits only touches the `Sw_CEPM_QueueExempt` block in `reeds/core/setup/b_inputs.gms`. See [`../interconnection-queue-and-prescribed-builds.md`](../interconnection-queue-and-prescribed-builds.md) §5.8.

| | `v20261009postcapex` | `v20261020tfnewq` |
|---|---|---|
| `CAP_ABOVE_LIM` (queue overage), 2026 | ~22 GW across tech groups, e.g. wind-ons p31 5,202 MW, PV z28 4,987 MW, battery z28 4,285 MW | none |
| `CAP_ABOVE_LIM`, 2029 | wind-ons p31 3,867 MW, p47 277 MW, coal p29 762 MW, ... | none |
| 2029 new gas-cc / gas-ct | 408 / 123 MW | 478 / 52 MW |
| 2032 new wind-ons (all in p31) | 1,611 MW | 817 MW |
| 2032 new upv / pumped-hydro / gas-ct | 1,387 / 566 / 326 MW | 1,533 / 626 / 422 MW |

The 2026 builds are identical. The 2029 builds differ only slightly.

### The queue constraint doesn't exist in 2032

`inputs_case/cap_limit.csv` only has columns for 2026–2030. `eq_interconnection_queues` is guarded by `sum{(tgg,rr), cap_limit(tgg,rr,t)}`, so the constraint isn't generated for 2032. The CEPM exemption also only raises the limit in `queue_years(t)`. Neither run is queue-constrained in 2032. The queue only affects 2032 through what happened earlier.

## 2. How the difference reaches 2032

Both runs use `timetype=seq` with `yearset 2026..2032..3`, `GSw_PRM_StressModel=pras`, and `GSw_PRM_StressIterateMax=5`. In each solve year, ReEDS solves, runs PRAS on the result, adds the worst days as stress periods, and solves again. It repeats until NEUE is at or below the threshold or the iteration cap is reached.

Both runs start 2032 with the same six seed days. From iteration 1 on, PRAS has a slightly different 2029 fleet to evaluate, so it picks different days:

- **Old run:** Feb 2011 cold snap (`y2011d034/035`), Dec 2009, Jul 2007, Dec 2011 / Jan 2013, ...
- **New run:** Dec 2012 / late Dec 2019, Feb 2021, Sep 2018, Jul 2021, ...

These day sets value wind differently, and the final 2032 solve uses whatever accumulated by iteration 5. Neither run met the threshold in 2029 or 2032. So the final mix is the result of a path-dependent, unconverged loop, not a converged reliability answer.

NEUE for SPP_South by iteration (from `gamslog.txt`, threshold `transgrp_1` = 1 ppm):

| Year | Old run (i0 → i4) | New run (i0 → i4) |
|---|---|---|
| 2029 | 6.4, 6.4, 6.4, 6.4, 8.1 | 17.7, 17.7, 17.7, 17.7, 17.7 |
| 2032 | 29.7, 18.4, 18.4, 18.4, 18.4 | 9.5, 9.5, 9.5, 16.9, 16.9 |

WestConnect_South passes in every iteration.

## 3. Why SPP_South fails

### 3.1 SPP_South is one small region

From `inputs_case/hierarchy.csv`:

| r | transgrp | interconnect | st |
|---|---|---|---|
| p27, z28, p29 | WestConnect_South | western | AZ |
| p31 | WestConnect_South | western | NM |
| **p47** | **SPP_South** | **eastern** | NM |

p47 is eastern New Mexico (Lea County: Hobbs, Maddox, Cunningham). It's the only SPP region and the only Eastern Interconnection region in this run. Because `GSw_PRM_StressThresholdNEUE` is set at the `transgrp` level, p47 is checked against 1 ppm on its own.

Its only connection to the rest of the run is a **200 MW back-to-back DC tie to p31** (`trancap_init_prm.csv`, `trancap_init_energy.csv`), and no expansion is planned (`trancap_fut.csv` is empty). In the national model, p47 sits inside SPP. Its other neighbors are SPP regions that the `st/AZ.NM` cut drops.

Peak load (`peakload.csv`): 800 MW in 2026, 823 MW in 2029, 846 MW in 2032. Annual load is about 4.6 TWh, so **1 ppm ≈ 4.6 MWh/yr of EUE**. One 40 MW shortfall lasting a few hours, somewhere in the 15 weather years PRAS samples, is enough to fail.

### 3.2 The model retires p47's peakers in 2029

Existing p47 thermal capacity (`outputs/cap_ivrt.csv`, newer run):

| Unit | 2026 MW | 2029 MW | Exogenous `RetireYear` |
|---|---:|---:|---|
| gas-cc init-1 (Hobbs) | 574 | 574 | 2063 |
| gas-ct init-1 (Cunningham CTs) | 207 | 0 | **2040** |
| gas-ct new5 | 43.5 | 0 | **2067** |
| o-g-s init-1 (Maddox ST) | ~117 | 0 | 2028 (forced) |
| o-g-s init-1 / new3 (Cunningham ST etc.) | ~88 | 0 | **2034–2035** |

So in 2029 the model chooses to retire about **340 MW of firm capacity** (`GSw_Retire=5`, `GSw_RetireYear=2027`) on top of the scheduled Maddox retirement. What's left is 575 MW of gas-cc, a 36 MW battery (60 MW by 2032), plus 1,752 MW of wind and 572 MW of upv.

Gas can't come back during the queue window: p47's **gas queue limit is 0 MW in every year from 2026 to 2030** (`cap_limit.csv`), so any new gas there costs the $10M/MW penalty. Battery has headroom (447 MW in 2029), but the model doesn't use it, for the reason in §3.3. PRAS EUE in p47 goes from **0 in 2026 to about 81 MWh/yr in 2029**.

### 3.3 GAMS doesn't see the shortfall PRAS reports

All PRAS EUE in both years and every iteration is in p47 (`handoff/PRAS/PRAS_<year>i<n>.h5`, newer run):

| | 2029 i0–i4 | 2032 i0–i2 | 2032 i3–i4 |
|---|---|---|---|
| p47 EUE (MWh/yr) | 81.2 (each) | 45.3 | 80.9 |
| p47 hours with EUE (of 131,400) | 174 | 154 | 192 |
| all other regions | 0 | 0 | 0 |

Within a year, EUE is often exactly the same from one iteration to the next. **Adding stress days doesn't change the p47 solution at all.**

The PRAS shortfalls are small (at most **42 MW** in any hour). They're spread across many days in winter (Dec–Feb) and early summer, mostly at hours 19–23 and 0–8. That pattern points to two gas-cc units tripping during a low-wind hour.

On those same stress days, the GAMS stress-period dispatch (`outputs/gen_h_stress.csv`, `load_stress.csv`, `net_import_h_stress.csv`) shows p47 with 30–300 MW of unused gas-cc capacity, while **exporting the full 200 MW to p31** in most hours. That's true even though GAMS stress load already includes the 12% PRM (2032 peak stress load of 948 MW = 846 × 1.12). The two models disagree for two reasons:

| | GAMS stress dispatch | PRAS |
|---|---|---|
| Thermal outages | Average availability derate (`GSw_PRM_StressOutages=1`) | Random outages on units capped at the zonal PRM, 102 MW in p47 (`pras_max_unitsize_prm=1`, `handoff/reeds_data/max_unitsize_<year>.csv`) |
| Time resolution | 4-hour blocks (`GSw_HourlyChunkLengthStress=4`). Load is the block maximum (`GSw_PRM_StressLoadAggMethod=max`); VRE is the block mean | Hourly |

A loss-of-two-units event can't happen in a model that applies an average derate. However many stress days the loop adds, GAMS still sees p47 as having surplus, so it never builds or retains anything there. That's why the loop can't converge.

### 3.4 The knock-on effect elsewhere

Each iteration does add stress days, and those days do change dispatch and builds in WestConnect, mainly p31, where the wind is. So the loop doesn't fix p47, but it does shuffle the AZ/NM mix. With the cap at 5 iterations, the final 2032 mix depends on which days were picked. That's the noise behind the 2032 wind difference in §1.

## 4. Options

None of these have been run yet.

1. **Turn on PRM updating (most targeted).** `GSw_PRM_UpdateMethod=2` or `3` raises the PRM for regions that keep failing the PRAS threshold (`reeds/resource_adequacy/stress_periods.py`, around line 730). That gives GAMS a lever that responds to outage-driven shortfalls in p47. `3` waits until no new stress periods are being added. `1` uses a fixed increment (`GSw_PRM_UpdateFraction=0.02`).
2. **Re-scope or relax the threshold.** A `transgrp` threshold on a 4.6 TWh island tied to the run by 200 MW is mostly an artifact of the regional cut. Options include a laxer ppm value for SPP_South, or a hierarchy level that pools p47 with more load. `interconnect` won't do that, because p47 is alone on the Eastern Interconnection.
3. **Check the early peaker retirements.** If the study expects Cunningham's CTs and steam units to run to their scheduled dates, restricting endogenous retirement in p47 would remove most of the EUE. It would also make the 2029 fleet less sensitive to small changes elsewhere.
4. **Isolate the queue effect (diagnostic only).** To confirm §2, rerun the two baselines with identical stress periods (for example, freeze them with `stressperiods_user.csv`, or turn the loop off) and check whether the 2032 wind gap closes.

The 2032 blind spot in the queue data (see [`../interconnection-queue-and-prescribed-builds.md`](../interconnection-queue-and-prescribed-builds.md)) and this non-convergence compound each other: 2032 is the year with no queue constraint *and* the year with the noisiest stress-period outcome.

## 5. Reproducing the checks

All paths are under `runs/<batch>_st-AZNM_baseline/`.

- Switch diff: `diff <(sort A/inputs_case/switches.csv) <(sort B/inputs_case/switches.csv)`
- Region membership: `inputs_case/hierarchy.csv`
- NEUE per iteration: search `gamslog.txt` for `transgrp_1 (passed|failed)` and the `neue` lines that follow
- Stress days per iteration: `inputs_case/stress<year>i<n>/period_szn.csv`
- PRAS EUE by region: datasets `<r>_EUE` in `handoff/PRAS/PRAS_<year>i<n>.h5` (hourly, 15 weather years × 8760)
- GAMS stress dispatch: `outputs/gen_h_stress.csv`, `load_stress.csv`, `net_import_h_stress.csv`, filtered to `r == "p47"`
- Retirements vs. schedule: `outputs/cap_ivrt.csv` vs. `inputs_case/retirements.csv`
- Queue limits: `inputs_case/cap_limit.csv`

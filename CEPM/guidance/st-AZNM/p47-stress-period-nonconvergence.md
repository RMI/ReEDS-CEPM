# st-AZNM: p47 (SPP_South) stress-period non-convergence
**Written Date:** October 23, 2026
**Updated:** November 11, 2026. §6 adds findings from every AZNM batch since October 9, and §4 now lists two candidate fixes. Corrections from that work are marked inline.

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

Its only connection to the rest of the run is a **200 MW back-to-back DC tie to p31** (`trancap_init_prm.csv`, `trancap_init_energy.csv`), and the tie can't grow within the horizon. *(Corrected November 2026: `trancap_fut.csv` isn't empty. It has SunZia, `p31,z28,certain,VSC,2026,3000`, but nothing for p47. With `GSw_TransInvNearTerm=0`, no interface can be expanded endogenously before 2033. See §6.6.)* In the national model, p47 sits inside SPP. Its other neighbors are SPP regions that the `st/AZ.NM` cut drops.

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

> **November 2026:** the retirements are a symptom, not the cause. GAMS retires the peakers because it sees p47 as reliable without them (§3.3), and it wouldn't rebuild them for the same reason, queue penalty or not. `_limitre` and `_optimized`, where the penalty multiplier applies, did build gas in p47 and still failed. See §6.2.

### 3.3 GAMS doesn't see the shortfall PRAS reports

All PRAS EUE in both years and every iteration is in p47 (`handoff/PRAS/PRAS_<year>i<n>.h5`, newer run):

| | 2029 i0–i4 | 2032 i0–i2 | 2032 i3–i4 |
|---|---|---|---|
| p47 EUE (MWh/yr) | 81.2 (each) | 45.3 | 80.9 |
| p47 hours with EUE (of 131,400) | 174 | 154 | 192 |
| all other regions | 0 | 0 | 0 |

Within a year, EUE is often exactly the same from one iteration to the next. **Adding stress days doesn't change the p47 solution at all.**

The PRAS shortfalls are small (at most **42 MW** in any hour). They're spread across many days in winter (Dec–Feb) and early summer, mostly at hours 19–23 and 0–8. That pattern points to two gas-cc units tripping during a low-wind hour.

> **Corrected November 2026:** 42 MW is an average over PRAS's 10 samples. In individual samples the shortfalls are rare but large, up to 354 MW, and they cluster in cold snaps such as February 3, 2011, when about half of p47's firm capacity is out at once. That fits ReEDS2PRAS's hourly, temperature-dependent outage rates more than a two-unit trip. See §6.3.

On those same stress days, the GAMS stress-period dispatch (`outputs/gen_h_stress.csv`, `load_stress.csv`, `net_import_h_stress.csv`) shows p47 with 30–300 MW of unused gas-cc capacity, while **exporting the full 200 MW to p31** in most hours. That's true even though GAMS stress load already includes the 12% PRM (2032 peak stress load of 948 MW = 846 × 1.12). The two models disagree for two reasons:

| | GAMS stress dispatch | PRAS |
|---|---|---|
| Thermal outages | Average availability derate (`GSw_PRM_StressOutages=1`) | Random outages on units capped at the zonal PRM, 102 MW in p47 (`pras_max_unitsize_prm=1`, `handoff/reeds_data/max_unitsize_<year>.csv`) |
| Time resolution | 4-hour blocks (`GSw_HourlyChunkLengthStress=4`). Load is the block maximum (`GSw_PRM_StressLoadAggMethod=max`); VRE is the block mean | Hourly |

A loss-of-two-units event can't happen in a model that applies an average derate. However many stress days the loop adds, GAMS still sees p47 as having surplus, so it never builds or retains anything there. That's why the loop can't converge.

### 3.4 The knock-on effect elsewhere

Each iteration does add stress days, and those days do change dispatch and builds in WestConnect, mainly p31, where the wind is. So the loop doesn't fix p47, but it does shuffle the AZ/NM mix. With the cap at 5 iterations, the final 2032 mix depends on which days were picked. That's the noise behind the 2032 wind difference in §1.

## 4. Options

Rewritten November 2026 in light of §6. None of these have been run yet.

The root cause is that GAMS sees p47 as reliable and PRAS doesn't (§3.3, §6.3). New stress days can't close that gap, because on those days GAMS's own dispatch still shows p47 in surplus. A fix has to either turn PRAS's verdict into a constraint GAMS must meet in p47, or give p47 a way to draw on the surplus next door. These two candidates do one each, and they work best together:

1. **`GSw_PRM_UpdateMethod=2`: turn PRAS's verdict into a GAMS constraint.** This raises the reserve margin for regions that keep failing the PRAS threshold (`reeds/resource_adequacy/stress_periods.py`, around line 730). It's the only switch that gives GAMS a reason to act in p47: keep or build firm capacity there, add storage, or place data-center load elsewhere (§6.2). It's indirect, since it raises a derated capacity requirement and still doesn't model correlated outages, but it keeps rising until PRAS is satisfied. More gas in p47 would also be exposed to the same cold-weather outages, so watch whether the model meets the higher reserve margin with gas or with storage. `3` behaves the same but waits until no new stress days are being added. `1` uses a fixed step (`GSw_PRM_UpdateFraction=0.02`).
2. **`GSw_TransInvNearTerm=1`: let the p31–p47 tie grow before 2033.** The per-sample test (§6.3) shows p47 imports the full 200 MW every time it's short while p31 has 1,400+ MW to spare. The tie is the bottleneck. This switch allows endogenous expansion on every existing interface from 2026, capped at `GSw_TransInvMaxNearTerm` (1.4 TW-mile/yr). It's a run-wide modeling decision, not specific to p47 (§6.6). GAMS will only expand the tie if it sees value in it, and it doesn't see p47's risk on its own, so pair it with option 1. A narrower variant is a `possible` row for p31–p47 in a CEPM `hvdc_planned-<scenario>.csv` file selected by `GSw_TransScen`. That allows early expansion on that one interface, but it needs a new input file.

Suggested test: one AZNM two-step batch with three variants, (1), (2), and (1)+(2). Compare p47's NEUE across iterations (whether it falls, not just whether it passes), p47's fleet and storage, data-center load placement, and the tie's capacity.

Other options, in order of preference:

- **Keep data-center load out of p47, or limit its share.** No switch does this. Every region in the state is eligible (`val_loadsite` in `b_inputs.gms`), and the load-site level can't be `r` (`GSw_LoadSiteTrajectory` allows only `nercr`, `transreg`, `transgrp`, `cendiv`, `st`, `interconnect`, `country` and `usda_region`). ReEDS's state-to-region allocation shares (`reeds.io.get_disagg_data`, as used by `hourly_load.py` for `GSw_LoadAllocationMethod`) give p47 13% of New Mexico by `population` and 35% by `state_lpf`, against the 98% the model chose in 2032. Options: (a) a CEPM constraint capping each region's load sites at its share of the state total (recommended; a switch, about 20 lines of GAMS and one input file); (b) a `hurdlereg`-level load-site file, which splits New Mexico at p31/p47 but also splits Arizona into WAPA and APS, and needs `hurdlereg` added to the switch's allowed values in `cases.csv`; (c) pooling at `transgrp`, which merges Arizona's and western New Mexico's pools. `GSw_LoadSiteRA=0` also makes the failures go away, but only by hiding that load from PRAS.
- **Check the early peaker retirements.** If the study expects Cunningham's CTs and steam units to run to their scheduled dates, restricting endogenous retirement would remove most of the baseline's EUE. `GSw_Retire` and `GSw_RetireYear` apply run-wide, though, and this doesn't help `_limitre` or `_optimized` (§6.2).
- **Finer GAMS stress dispatch: `GSw_HourlyChunkLengthStress=1`.** This closes the time-resolution half of the gap in §3.3 but not the outage-sampling half, and it slows the solve.
- **A state-level threshold (`GSw_PRM_StressThresholdNEUE=st_1`): not a fix.** It changes the yardstick, not the model, and the existing runs would mostly still fail it (§6.4). Consider it only as a reporting choice, if p47's standalone number is judged an artifact of the cut.
- **Isolate the queue effect (diagnostic only).** To confirm §2, rerun the two baselines with identical stress periods (for example, freeze them with `stressperiods_user.csv`, or turn the loop off) and check whether the 2032 wind gap closes.

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
- Reliability metrics at every hierarchy level (`r`, `st`, `transgrp`, ...), per iteration: `outputs/ra_metrics_<year>i<n>.csv`
- Data-center load placement: `outputs/loadsite_cap.csv`
- Transmission: `inputs_case/trancap_fut.csv`, `trancap_init_energy.csv`, and `scalars.csv` (`firstyear_trans_nearterm`, `firstyear_trans_longterm`)
- Per-sample PRAS shortfall, flow and surplus: the method is in §6.3

## 6. Findings from November 2026

### 6.1 It fails in every run since October 9

SPP_South NEUE from each `gamslog.txt`, for all 21 AZNM runs in batches `newcapexqoff`, `postcapex`, `precapex`, `noqpen`, `tfnewq`, `tfrecaps` and `drshed`:

- **2026 always passes.** NEUE is 0.0 in baseline cases and 0.445 in `_limitre` and `_optimized`.
- **2029 and 2032 fail in every run and every case,** from 1.3 to 29.7 ppm.
- **NEUE barely moves across the five iterations,** and is often identical in all of them. Adding stress days doesn't change p47.

`v20261026drshed` (no batch-log entry) has the same baseline switches and results as `v20261020tfrecaps`. Its changes only affect `_limitre` and `_optimized`.

### 6.2 `_limitre` and `_optimized` put New Mexico's data-center load in p47

Load sites are placed endogenously among each state's regions (`GSw_LoadSiteReg=st`), and they count in PRAS (`GSw_LoadSiteRA=1`). The baseline has no state load sites. GAMS sees p47 as reliable, so it places most of New Mexico's data-center load there (`outputs/loadsite_cap.csv`, `v20261026drshed`):

| MW in p47 | 2026 | 2029 | 2032 | NM total, 2032 |
|---|---:|---:|---:|---:|
| `_limitre` | 284 | 523 | 636 | 649 |
| `_optimized` | 284 | 352 | 478 | 649 |

That takes p47's 2032 peak in `_limitre` from 846 MW to about 1,480 MW. The model does build firm capacity there: 2032 `_limitre` has about 1,300 MW of gas-cc, gas-ct and o-g-s, against 575 MW in the baseline. It still fails, at 7.3 ppm. Unlike the baseline, these cases aren't failing because of retirements.

### 6.3 Per-sample PRAS: the tie is the bottleneck

The averaged PRAS flow output looked as if p47 wasn't importing much when short. In `_limitre` 2032, the mean flow into p47 never exceeds 83 MW, even in its worst hours. To check, PRAS was rerun for that system with per-sample output, meaning each sample's shortfall, flow and surplus. The method: copy the run to a scratch folder, regenerate the handoff CSVs with `reeds.resource_adequacy.prep_data.main(2032, casedir, 4)` (the originals are deleted at the end of a run), build the system with `run_pras.jl --samples=0`, then run `SequentialMonteCarlo(samples=10, seed=1)` with `ShortfallSamples`, `FlowSamples` and `SurplusSamples`. It reproduces the run's own result exactly: 75.9 MWh/yr of p47 EUE.

| In the 146 sample-hours where p47 is short | Result |
|---|---|
| Flow into p47 | **200 MW, the tie limit, in every one** |
| p31's spare capacity at the same time | Large: 1,416–1,874 MW in the worst hours |
| Shortfall in individual samples | Up to **354 MW** (the averaged peak is 40 MW) |

So p47 imports everything the tie can carry, and p31 has plenty to spare. The averages were misleading because one short sample importing 200 MW is averaged with nine that aren't. PRAS isn't misallocating anything. ReEDS2PRAS doesn't model transmission outages (`FOR = 0.0` in `reeds2pras/src/utils/reeds_data_parsing.jl`), so the tie is always available.

The events are rare but large: 44 sample-days in 150 sample-years, and the worst three account for about a third of the total. The largest is **February 3, 2011**, the Southwest cold snap. Up to 354 MW is short at a p47 load of about 1,250 MW, so after importing 200 MW, p47 had only about 690 MW of its roughly 1,300 MW of firm capacity available. That fits ReEDS2PRAS's hourly, temperature-dependent outage rates: in a deep cold snap, many gas units in one small region fail together. Next are January 25, 2007 and January 15, 2013, plus some summer evenings.

So the shortfall is real given the outage data, and the binding constraint is the tie. One case and year (`_limitre` 2032) was checked. The baseline has less load in p47, but the mechanism should be the same.

### 6.4 A state-level threshold wouldn't make the runs pass

`ra_metrics_<year>i<n>.csv` already reports NEUE for New Mexico (p31 + p47). The peak shortfall in MW is the same as p47's, so all of New Mexico's unserved energy is p47's. A state-level threshold just divides it by more load (`v20261026drshed`, last iteration):

| NEUE, ppm | p47 (current test) | NM (`st_1` test) |
|---|---:|---:|
| baseline 2029 / 2032 | 17.7 / 16.9 | 2.30 / 2.20 (fail) |
| `_limitre` 2029 / 2032 | 1.35 / 7.33 | 0.31 / 1.78 (pass / fail) |
| `_optimized` 2029 / 2032 | 2.13 / 5.37 | 0.41 / 1.13 (pass / fail) |

Under `st_1`, most years would still hit the iteration cap. GAMS's view of p47 wouldn't change, and Arizona would be tested on its own instead of as WestConnect_South.

### 6.5 Why it's worse here than in ReEDS generally

- **An average derate is only accurate for large fleets.** With many units, outages average out. With p47's handful of units (each 102 MW or less in PRAS), correlated or multiple outages are large compared with load, and the 12% reserve margin is tuned for big, diverse systems.
- **p47 is an island in this cut.** In a national run it sits inside SPP. Here its only connection is the 200 MW tie.
- **The threshold is tiny in absolute terms.** 1 ppm of p47's 4.6 TWh is about 4.6 MWh/yr. For a typical reliability group with 50–100+ TWh of load, it's 50–100+ MWh.
- **Data-center load placement makes it worse** (§6.2).

Upstream's usual runs are national, so they rarely hit this. Expect it in any CEPM cut that leaves a small, weakly tied region from a different grid or market at the edge. When setting up a new region, check `hierarchy.csv` for reliability groups (`transgrp`) with only one or two regions and small interties.

### 6.6 Transmission can't grow before 2033

`trancap_fut.csv` lists planned HVDC lines (`hvdc_planned-baseline.csv`, plus `hvdc_planned-<GSw_TransScen>.csv` if `GSw_TransScen` is set, plus offshore links), built by `transmission.py`'s `get_trancap_fut()`. Rows marked `certain` are built exogenously. Rows marked `possible` make an interface eligible for early expansion. Otherwise every existing interface, including p31–p47, can be expanded within `GSw_TransRestrict`, but only from `firstyear_trans_longterm` (2033), unless `GSw_TransInvNearTerm=1` (`routes_inv` in `b_inputs.gms`). Both that switch's default and CEPM's setting are `0`, and CEPM runs end in 2032. So **no CEPM run builds endogenous transmission**. Interfaces between regions with no existing line only become candidates through `GSw_TransScen` (`NTP_MT`, `NTP_P2P`).

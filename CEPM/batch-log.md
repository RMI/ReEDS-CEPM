# Batch Change Log

This doc logs notable CEPM batches we've run and catalogues what happened.
Not every batch needs to go in here--but ones that move our work forward do.
We should be able to build a chain from the present back to when we started
using these batch files.

Only runs that successfully complete should be logged here.

Run outputs are archived to **VM_Outputs**, a SharePoint folder on the run VM -
we copy each run's output folder there so results are viewable off the VM and
shareable with colleagues. `runs/` is gitignored (`.gitignore:9`), so
VM_Outputs is the only durable copy. That is why this log matters: once a batch
is archived and cleaned off the VM,these entries are the in-repo record of what
was run and what it showed.

Loosely inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## TEMPLATE Batch entry: {Batch name here, e.g., v20260903}**
**Author: Tyler Fitch**

Summary: What'd we change, why, what'd we find, what's next

### Batch details

- **Built from:** `{Release tag, relevant batch name, or today's date}`
- **Space and Time:** `{e.g., WECC-SW, 2026-2032 every 3 years}`
- **Cases:** `{e.g., baseline, limitre, optimized}`
- **Run comments:** Optional. How long did this take?

### Change log

- **ReEDS change:** Changed `{file}` in order to do `{XYZ}`
- **Case change:** Changed `{Switch}` in `{Case}`
- **Case change:** Added `{Case}`

### Results

- Where's the compare cases file
- What changes does it show

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** We should do XYZ moving forward.
- **DOCUMENTATION:** A new file in `CEPM/guidance` shows XYZ
- **NEXT STEP:** We will implement that through XYZ, catalogued in (github/JIRA)
- **ISSUE:** We found XYZ and didn't address it.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [ ] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

Batch entry: 20261106gt_DRConditionalPeak
Author: Gabriella Tosado

Summary: Updated DR so it can participate in representative and stress hours while respecting daily/event-duration limits and targeting peak hours. Replaced the earlier mandatory peak requirement tied to installed DR capacity with a conditional requirement tied to actual daily DR use. This preserved ~4.2 GW of DR while ensuring DR was used at the peak on all representative days. PVB remains enabled.
Batch details
- Built from: 20261106gt_AllHourDR
- Space and Time: st-AZNM, 2026–2032 every 3 years, 1-hour representative periods
- Cases: baseline, limitre, optimized
- Run comments: All three cases completed successfully.
Change log
- ReEDS change: Made DR available during both representative and stress hours.
- ReEDS change: Added a maximum of 8 equivalent full-output hours of DR per representative day.
- ReEDS change: Added a maximum of 4 equivalent full-output hours within any rolling 5-hour window.
- ReEDS change: Added conditional peak targeting: Peak DR >= (10% / 8) × total daily DR dispatch. If DR is used during a representative day, some DR must therefore occur during the peak hour.
- ReEDS change: Replaced the previous 10% × installed DR capacity peak requirement, which caused the model to stop building DR.
- Case change: GSw_PVB = 1.
Results
- Compare cases file: 20261106gt_DRConditionalPeak_st-AZNM_baseline/outputs/comparisons/results-st-AZNM_baseline,st-AZNM_limitre,st-AZNM_optimized.pptx
- 2032 DR capacity: 4.156 GW Baseline, 4.265 GW LimitRE, 4.140 GW Optimized.
- Baseline DR operates during 79 representative + 114 stress hours.
- DR is used on all 7 representative days and occurs at the peak on 7/7, compared with 5/7 without conditional peak targeting.    Pasted text(20261106-194934)
- Baseline total gas capacity: 16.483 GW.
- Baseline system NPV: $246.319B.    Pasted text(20261106-195012)
- Conditional peak targeting materially changes DR timing without materially changing the capacity solution.
Documentation, decisions, next steps, & issues
- PROPOSED DECISION: Use Conditional Peak rather than the mandatory installed-capacity peak constraint for DR modeling.
- DOCUMENTATION: Conditional peak targeting requires peak DR based on actual daily DR use, not installed DR capacity.
- NEXT STEP: Use the NoPVB version as the primary DR sensitivity against Base to remove the PVB confounder.
- ISSUE: The previous mandatory 10% × installed DR capacity peak requirement caused DR builds to fall to zero and should not be used.
Checklist
- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment
Batch entry: 20261106gt_DRConditionalPeak_NoPVB
Author: Gabriella Tosado

Summary: Reran the finalized Conditional Peak DR formulation with PVB disabled. This provides a cleaner comparison with Base because both runs exclude PVB. DR remains ~4.2 GW across scenarios, indicating the DR build is robust to removing PVB.
Batch details
- Built from: 20261106gt_DRConditionalPeak
- Space and Time: st-AZNM, 2026–2032 every 3 years, 1-hour representative periods
- Cases: baseline, limitre, optimized
- Run comments: All three cases completed successfully.
Change log
- Case change: Changed GSw_PVB from 1 to 0 for st-AZNM_baseline, st-AZNM_limitre, and st-AZNM_optimized.    Pasted text(20261106-195012)
- ReEDS change: None relative to DRConditionalPeak; retained all-hour DR, daily/rolling duration limits, and conditional peak targeting.
Results
- Compare cases file: 20261106gt_DRConditionalPeak_NoPVB_st-AZNM_baseline/outputs/comparisons/results-st-AZNM_baseline,st-AZNM_limitre,st-AZNM_optimized.pptx    Pasted text(20261106-204819)
- 2032 DR capacity: 4.156 GW Baseline, 4.265 GW LimitRE, 4.198 GW Optimized.
- Compared with Base, Baseline builds 0.515 GW more total gas but 0.641 GW less total capacity.
- Baseline system NPV falls from $251.978B → $248.039B, a $3.939B (1.56%) reduction.
- LimitRE system NPV falls by $5.899B (2.00%).
- Optimized system NPV falls by $7.962B (2.69%).    Pasted text(20261106-204958)
- Removing PVB does not materially reduce DR builds, suggesting the ~4.2 GW DR result is not dependent on PVB availability.    Pasted text(20261106-204958)
Documentation, decisions, next steps, & issues
- PROPOSED DECISION: Use DRConditionalPeak_NoPVB as the primary DR sensitivity against Base because PVB is disabled in both.
- DOCUMENTATION: Describe cost differences as the effect of the DR/hourly modeling package, not DR alone, because temporal treatment also differs from Base.
- NEXT STEP: Use this run for the primary Base-vs-DR capacity and cost comparisons.
- ISSUE: None identified in this run.
Checklist
- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: `20261105gt_AZNM_RA`
**Author: Gabriella Tosado**

Summary: Changed the AZ/NM resource-adequacy criterion so PRAS evaluates the combined AZ/NM study system against **1 ppm NEUE**, rather than requiring the WestConnect-South and SPP-South portions to independently meet 1 ppm. This reduced the number of stress periods required while leaving the capacity portfolio largely unchanged and modestly reducing system costs.

### Batch details

- **Built from:** `v20261105gt_DRshed_1hr_PVB`
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years`
- **Cases:** `baseline, limitre, optimized`
- **Run comments:** Completed successfully. Results moved to `C:\Users\gtosado\OneDrive - RMI\Runs\`.

### Change log

- **Case change:** Changed `GSw_PRM_StressThresholdNEUE` from the ReEDS default `transgrp_1` to `country_1` for the three AZ/NM cases.
- **Reliability change:** PRAS now requires the **combined AZ/NM modeled system** to achieve NEUE ≤ 1 ppm instead of separately applying the criterion to `WestConnect_South` and `SPP_South`.
- **Case change:** Retained the **12% initial planning reserve margin** with `GSw_PRM_UpdateMethod = 0`, so PRAS does not increase the PRM.
- **Case change:** Retained `GSw_PRM_StressIterateMax = 5`.
- **Case change:** Retained the prior **1-hour DR + PVB** configuration.
- **Geography:** No change to the `z132` physical transmission geography. NM `p47` remains physically mapped to SPP; only the geographic level used to evaluate the PRAS reliability criterion changed.

### Results

- Compared against `v20261105gt_DRshed_1hr_PVB`, which used the default `transgrp_1` reliability criterion.
- The `country_1` treatment substantially reduced the number of stress periods required to satisfy the reliability criterion.
- The 2032 capacity portfolio remained largely unchanged.
- System costs decreased modestly relative to the `transgrp_1` run.
- The results indicate that requiring each transmission group to independently satisfy 1 ppm was more restrictive than evaluating reliability across the combined AZ/NM study system.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Use `country_1` as the AZ/NM PRAS reliability criterion when the modeling question concerns reliability of the combined AZ/NM study system.
- **DOCUMENTATION:** `country_1` changes the geographic level at which NEUE ≤ 1 ppm is evaluated; it does **not** alter the underlying physical transmission geography.
- **NEXT STEP:** Carry the combined AZ/NM reliability treatment forward into subsequent AZ/NM DR and hourly-modeling sensitivities.
- **ISSUE:** `transgrp_1` effectively requires both `WestConnect_South` and `SPP_South` to independently satisfy 1 ppm, which can generate substantially more stress periods than the combined-system criterion.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment


## Batch entry: `20261105gt_1hrRep`
**Author: Gabriella Tosado**

Summary: Changed the normal representative periods used for capacity-expansion and dispatch optimization to **1-hour temporal resolution**. This tests the effect of hourly operating conditions throughout the capacity-expansion problem separately from the later change that allows DR to operate during representative hours. DR remains restricted to stress/reliability periods in this batch.

### Batch details

- **Built from:** `v20261105gt_DRshed_1hr_PVB`
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years, 1-hour representative periods`
- **Cases:** `baseline, limitre, optimized`
- **Run comments:** Completed successfully. Results moved to `C:\Users\gtosado\OneDrive - RMI\Runs\`.

### Change log

- **ReEDS change:** Changed normal representative-period granularity to **1 hour**, allowing capacity-expansion and dispatch optimization to see hourly operating conditions rather than multi-hour representative chunks.
- **Case change:** Retained **1-hour stress-period granularity**.
- **Case change:** Retained the existing **DR shed + PVB** configuration.
- **DR treatment:** DR remains restricted to stress/reliability periods; it is not yet available during normal representative hours.
- **Reliability change:** Retained the updated AZ/NM reserve-margin treatment from `20261105gt_AZNM_RA`.

### Results

- 2032 Baseline DR capacity: **3.880 GW**.
- DR operates during **63 stress hours** and zero representative hours.
- Baseline system NPV: **$249.68B**.
- Compared with the prior `1hr DR + PVB` run, DR capacity is essentially unchanged while DR is called during fewer stress hours.
- This run provides the control for the subsequent `AllHourDR` change: differences between `1hrRep` and `AllHourDR` can be attributed primarily to making DR operational during representative hours rather than changing representative-period resolution.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Retain 1-hour representative-period resolution for subsequent AZ/NM DR sensitivities.
- **DOCUMENTATION:** This batch changes temporal resolution for the broader capacity-expansion problem but does **not** change where DR is allowed to dispatch.
- **NEXT STEP:** Allow DR to participate in normal representative hours and compare against this batch to isolate the operational value of all-hour DR.
- **ISSUE:** None identified in this run.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: `20261106gt_AllHourDR`
**Author: Gabriella Tosado**

Summary: Extended DR shed from a reliability/stress-only resource into an **operational demand-side resource available during normal representative hours**. This is the first run where DR can directly reduce generation requirements during normal modeled operations and serves as the unconstrained all-hour DR benchmark for subsequent DR operating restrictions.

### Batch details

- **Built from:** `20261105gt_1hrRep`
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years, 1-hour representative periods`
- **Cases:** `baseline, optimized`
- **Run comments:** Completed successfully. Baseline and Optimized moved to `C:\Users\gtosado\OneDrive - RMI\Runs\`. No LimitRE folder was present locally when the batch was moved.

### Change log

- **ReEDS change:** Added representative-period hourly DR availability through `dr_shed_out_rep.csv`.
- **ReEDS change:** Modified `avail(i,r,h)` so DR shed is available during both representative hours (`h_rep`) and reliability/stress hours (`h_stress`).
- **ReEDS change:** Representative-hour DR availability is selected for the active solve year using `tmodel(t)`.
- **ReEDS change:** DR dispatch now enters the normal hourly `GEN` supply-demand balance, allowing dispatched DR to directly offset generation required to serve load in that hour.
- **ReEDS change:** Retained the existing stress-period DR treatment separately.
- **Case change:** Retained **1-hour representative-period and stress-period granularity**.
- **Case change:** Retained PVB.
- **DR treatment:** No daily event-count, mandatory peak-event, or representative-period event-duration constraints were imposed.

### Results

- 2032 Baseline DR capacity: **4.156 GW**, up from 3.880 GW in `1hrRep`.
- Baseline DR operates during **189 modeled hours: 73 representative + 116 stress hours**.
- Baseline system NPV: **$246.32B**, compared with $249.68B in `1hrRep`.
- Moving from `1hrRep` to AllHourDR therefore reduced Baseline system cost by approximately **$3.37B**.
- The run demonstrates that DR has additional value when it can participate in normal operations rather than being limited to reliability/stress events.
- This run provides the **unconstrained all-hour DR benchmark** for subsequent daily-duration, rolling-event, and peak-targeting constraints.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Allow DR to participate in representative hours in subsequent DR sensitivities rather than restricting it to stress periods.
- **DOCUMENTATION:** Representative-hour DR is modeled through normal hourly `GEN`, so DR directly offsets the generation required to satisfy the hourly supply-demand balance.
- **NEXT STEP:** Add realistic daily/event-duration and peak-targeting restrictions while testing whether they materially change DR investment or dispatch.
- **ISSUE:** This run does not constrain how frequently or for how long DR can operate during representative periods, so it should be treated as an unconstrained operational DR benchmark.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: `v20261105gt_DRshed_1hr_PVB`
**Author: Gabriella Tosado**

Summary: Tested DR shedding at **1-hour stress-period granularity with PVB enabled** for the AZ/NM cases. This tests whether preserving hourly DR availability during reliability stress periods changes capacity expansion and system costs relative to the prior 4-hour DR + PVB representation. DR capacity remained similar, but the optimized portfolio shifted substantially and system NPV fell by $5.36B relative to the 4-hour representation.

### Batch details

- **Built from:** Prior CEPM DR/PVB work, including `v20261102gt_DRshed_PVB` and `v20261104gt_DRshed_1hrStress`
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years`
- **Cases:** `baseline, limitre, optimized`
- **Run comments:** Completed successfully. PVB enabled and DR shedding represented at 1-hour stress-period granularity.

### Change log

- **ReEDS change:** Changed DR shed availability during reliability stress periods from the previous **4-hour aggregation to 1-hour granularity**.
- **Case change:** Enabled PVB alongside DR shedding.
- **Case change:** Retained the **12% initial planning reserve margin**.
- **Reliability change:** Retained PRAS stress-period iteration with `GSw_PRM_StressThresholdNEUE = transgrp_1`.
- **DR treatment:** DR remains a reliability/stress-period resource in this batch; it is not yet available during normal representative hours.
- **DR treatment:** No 4-hour maximum event-duration constraint was imposed, allowing this batch to isolate the effect of hourly DR availability with PVB enabled.

### Results

Comparison runs:
- Base: `v20261030gt_base`
- 4-hour DR + PVB: `v20261102gt_DRshed_PVB`
- 1-hour DR + PVB: `v20261105gt_DRshed_1hr_PVB`

**2032 optimized capacity [GW]:**

| Technology | Base | 4hr DR + PVB | 1hr DR + PVB |
|---|---:|---:|---:|
| DR | 0.00 | 3.81 | 3.85 |
| PVB | 0.00 | 1.37 | 1.37 |
| Gas CC | 12.67 | 12.81 | 12.82 |
| Gas CT | 4.67 | 7.04 | 5.82 |
| Solar | 23.92 | 19.68 | 18.01 |
| Wind | 14.20 | 14.48 | 14.79 |
| Battery | 7.98 | 7.33 | 7.37 |
| Pumped Hydro | 3.97 | 2.01 | 0.81 |

Relative to 4-hour DR + PVB, the 1-hour representation produces approximately **1.22 GW less gas CT, 1.67 GW less solar, and 1.20 GW less pumped hydro**, while DR and PVB capacity remain essentially unchanged.

**System NPV [billion $]:**

| Case | Base | 4hr DR + PVB | 1hr DR + PVB | 1hr vs Base | 1hr vs 4hr |
|---|---:|---:|---:|---:|---:|
| Baseline | 251.978 | 248.249 | 251.151 | -0.827 | +2.902 |
| LimitRE | 295.722 | 292.658 | 292.939 | -2.782 | +0.281 |
| Optimized | 296.498 | 296.129 | **290.766** | **-5.732** | **-5.363** |

The strongest result is in Optimized: moving from 4-hour to 1-hour DR stress-period representation reduces system NPV by **$5.36B**, despite similar DR capacity.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Retain 1-hour DR availability in reliability/stress periods for subsequent AZ/NM DR runs.
- **DOCUMENTATION:** This batch changes the temporal representation of DR during stress periods only; DR is not yet an operational resource during normal representative hours.
- **NEXT STEP:** Test 1-hour granularity in the normal representative periods (`20261105gt_1hrRep`) before allowing DR to dispatch during those periods.
- **ISSUE:** No explicit representative-period event-duration constraint is included, so this run should not be treated as the final DR operating formulation.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I

## Batch entry: v20261104gt_DRshed_1hrStress
**Author: Gabriella Tosado**

**Summary:** Tested demand response shedding using 1-hour rather than 4-hour stress-period resolution to better preserve hourly DR availability during reliability events. The higher-resolution representation materially changed the resulting capacity portfolio and generally reduced system costs relative to the base run. This run does not impose an explicit maximum DR event duration or event-frequency constraint and serves as the reference case for unconstrained hourly DR.

### Batch details

- **Built from:** `v20261030gt_DRshed`
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years`
- **Cases:** `baseline`, `limitre`, `optimized`
- **Run comments:** Sequential CEPM run with hourly stress periods and DR shed enabled.

### Change log

- **Case change:** Set `GSw_DRShed = 1` for all three AZNM cases.
- **Case change:** Changed `GSw_HourlyChunkLengthStress` from `4` to `1` to represent reliability stress periods at hourly resolution.
- **Case change:** `GSw_PVB = 0`.
- **ReEDS change:** No DR event-duration or event-frequency constraint was imposed in this run. DR availability continues to be determined by the hourly `dr_shed_out` availability profile.

### Results

- Compare-cases results are located in:
  `runs/v20261104gt_DRshed_1hrStress_st-AZNM_baseline/outputs/comparisons/results-st-AZNM_baseline,st-AZNM_limitre,st-AZNM_optimized.pptx`
- 2032 DR capacity:
  - Baseline: **3.88 GW `dr_shed_1`**
  - LimitRE: **3.81 GW `dr_shed_1` + 0.23 GW `dr_shed_2` = 4.03 GW**
  - Optimized: **3.81 GW `dr_shed_1`**
- Moving from 4-hour to 1-hour stress resolution materially changed the capacity mix even though total DR capacity remained similar.
- Relative to the original 4-hour DR run, the 1-hour formulation generally reduced solar and pumped-hydro capacity and substantially reshuffled gas and wind builds.
- In the optimized case, the 1-hour run reduced gas CT capacity by approximately **1.14 GW**, solar by **1.16 GW**, and pumped hydro by **0.44 GW** relative to the 4-hour DR run, while changing the mix of wind resources.
- Hourly stress resolution better preserves when DR is actually available during system peaks rather than averaging availability across 4-hour stress chunks.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Use 1-hour stress resolution when evaluating DR because it better represents the hourly coincidence between DR availability and system reliability needs.
- **ISSUE:** This run does not explicitly constrain how long or how frequently DR can be dispatched. DR can therefore potentially be called repeatedly during long or multi-day reliability events as long as the hourly availability profile permits it.
- **NEXT STEP:** Test a more operationally constrained hourly DR representation that limits DR to four equivalent full-output hours per reliability event.
- **NEXT STEP:** Test hourly DR jointly with PVB to evaluate whether DR and hybrid solar-storage act as substitutes or complements in the capacity portfolio.
- **DOCUMENTATION:** This run should be retained as the unconstrained hourly-DR reference case for comparison with the original 4-hour stress run and subsequent event-limited DR sensitivities.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the VM-Outputs/OneDrive results folder
- [ ] I added any issues we found to the JIRA issues epic
- [ ] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: v20261103gt_PVB_BIR
**Author: Gabriella Tosado**

Summary: Expanded the PVB sensitivity to allow ReEDS to choose among three PV+battery configurations with different battery-to-inverter ratios (BIR). ReEDS consistently selected the original 25% BIR configuration; allowing larger batteries did not change the capacity portfolio.

### Batch details

- **Built from:** `v20261029gt_PVB6`
- **Space and Time:** `AZ/NM, 2026–2032 every 3 years`
- **Cases:** `st-AZNM_baseline`, `st-AZNM_limitre`, `st-AZNM_optimized`
- **Run comments:** Run completed successfully.

### Change log

- **Case change:** Set `GSw_PVB_Types = 1_2_3`.
- **Case change:** Set `GSw_PVB_BIR = 25_50_75`, allowing 25%, 50%, and 75% battery-to-inverter ratios.
- **Case change:** Set `GSw_PVB_ILR = 134_134_134`, holding ILR constant at 1.34.
- **Case change:** Held battery duration constant at 4 hours.
- **Case change:** `GSw_DRShed = 0` and `GSw_EFS_Flex = 0`.
- **ReEDS change:** No additional ReEDS code or cost changes. PVB costs scale automatically with BIR.

### Results

- Comparison file: `runs/v20261103gt_PVB_BIR_st-AZNM

## Batch entry: v20261102gt_DRshed_PVB
**Author: Gabriella Tosado**

Summary: Enabled both demand-response shedding and hybrid PV+battery resources to test how the two solutions interact and whether their combined availability changes gas and other capacity needs relative to the base, DR-shed-only, and PVB-only cases.

### Batch details

- **Built from:** `v20261030gt_base`, incorporating the tested DR-shed and PVB configurations
- **Space and Time:** `AZ/NM, 2026–2032 every 3 years`
- **Cases:** `st-AZNM_baseline`, `st-AZNM_limitre`, `st-AZNM_optimized`
- **Run comments:** Run completed successfully.

### Change log

- **Case change:** Set `GSw_DRShed = 1` for baseline, limitre, and optimized.
- **Case change:** Set `GSw_PVB = 1` for baseline, limitre, and optimized.
- **Case change:** Kept `GSw_EFS_Flex = 0`.
- **PVB assumptions:** PVB type 1 with `GSw_PVB_BIR = 25`, `GSw_PVB_Dur = 4`, and 1.34 ILR.
- **DR assumptions:** Uses ReEDS' default DR-shed potential, costs, and hourly availability.
- **ReEDS change:** No additional ReEDS code changes for this sensitivity.

### Results

- Comparison results are under `runs/v20261102gt_DRshed_PVB_st-AZNM_baseline/outputs/comparisons/`.
- The run successfully allows **DR shedding and PV+battery hybrids to compete simultaneously** with conventional generation, standalone renewables, and storage.
- The DR input represents finite modeled DR potential rather than unrestricted load shedding: the underlying inputs contain ~4.32 GW of `dr_shed_1` and ~2.21 GW of `dr_shed_2` potential across AZ and NM before year-specific adjustments.
- PVB type 1 represents a hybrid configuration with a 25% battery/inverter ratio and four-hour battery duration.
- **Capacity impacts relative to the base, DR-shed-only, and PVB-only runs still need to be quantified.**

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Use the combined case to evaluate whether DR shedding and PV+battery hybrids are complementary or substitutive solutions for meeting load growth and reducing conventional capacity needs.
- **NEXT STEP:** Compare 2032 capacity, particularly DR, PVB, standalone solar, standalone battery, gas CC, and gas CT, against `v20261030gt_base`, `v20261030gt_DRshed`, and `v20261029gt_PVB6`.
- **ISSUE:** No run-breaking issue identified in the combined sensitivity.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the OneDrive Runs folder
- [ ] I added any issues we found to the JIRA issues epic
- [x] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: v20261030gt_DRshed
**Author: Gabriella Tosado**

Summary: Enabled ReEDS' default demand-response shedding resource to test how allowing load curtailment changes the AZ/NM capacity mix. ReEDS selected ~3.8 GW of DR shed by 2032 and materially changed capacity builds relative to the base case.

### Batch details

- **Built from:** `v20261030gt_base`
- **Space and Time:** `AZ/NM, 2026–2032 every 3 years`
- **Cases:** `st-AZNM_baseline`, `st-AZNM_limitre`, `st-AZNM_optimized`
- **Run comments:** Run completed successfully.

### Change log

- **Case change:** Set `GSw_DRShed = 1` for baseline, limitre, and optimized.
- **Case change:** Kept `GSw_PVB = 0`.
- **Case change:** Kept `GSw_EFS_Flex = 0`.
- **ReEDS change:** None for this sensitivity.

### Results

- Comparison results are under `runs/v20261030gt_DRshed_st-AZNM_baseline/outputs/comparisons/`.
- ReEDS builds approximately **3.8 GW of `dr_shed_1`** by 2032 across the modeled AZ/NM system. LimitRE additionally builds ~94 MW of `dr_shed_2`.
- Relative to the base case, the baseline DR-shed case has approximately **463 MW less gas CC, 17 MW less gas CT, and 242 MW less pumped hydro**, while adding ~660 MW solar and ~212 MW wind.
- The default DR inputs provide finite, region- and hour-specific DR potential rather than allowing unrestricted load shedding. The underlying supply curve includes ~4.32 GW of `dr_shed_1` and ~2.21 GW of `dr_shed_2` potential across AZ and NM before year-specific adjustments.
- DR costs and hourly availability vary by resource tier and geography.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Treat `GSw_DRShed = 1` as a full-default-DR-potential sensitivity, not as an assumption that 100% of demand can be shed.
- **NEXT STEP:** Compare this run with the combined DR-shed + PVB sensitivity to understand whether demand response and PV+battery hybrids complement or substitute for one another.
- **ISSUE:** None identified that prevented DR shedding from operating; unlike EFS load flexibility, DR shedding successfully enters the capacity optimization.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the OneDrive Runs folder
- [ ] I added any issues we found to the JIRA issues epic
- [x] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: v20261029gt_PVB6
**Author: Gaby Tosado**

Summary: Tested enabling PV+battery hybrid (PVB) builds in the AZNM CEPM cases. Enabling PVB exposed two existing ReEDS compatibility issues: PVB renewable profiles were looking for a standalone `recf_upv.h5` that is not produced by the current preprocessing workflow, and zero-valued PVB component VOM parameters were treated as missing by the input checker. After addressing both issues, the baseline, limitre, and optimized cases completed successfully with PVB enabled.

### Batch details

- **Built from:** `dr_testing`, based on clean `dev` synced October 29, 2026
- **Space and Time:** `st-AZNM, 2026–2032 every 3 years`
- **Cases:** `st-AZNM_baseline`, `st-AZNM_limitre`, `st-AZNM_optimized`
- **Run comments:** Successful three-case run after debugging PVB preprocessing and VOM handling.

### Change log

- **ReEDS change:** Updated `reeds/input_processing/recf.py` so that when PVB uses the same ILR as UPV, it reuses the UPV profile already calculated in memory rather than attempting to read a nonexistent `recf_upv.h5`. PVB columns are also renamed from the UPV resource naming convention to the corresponding PVB resource names.
- **ReEDS change:** Updated `reeds/core/setup/b_inputs.gms` to assign a small `0.01 $/MWh` VOM to the PV and battery components of PVB for valid PVB `valgen` combinations. This avoids the input checker interpreting legitimate zero-valued PVB VOM parameters as missing.
- **Case change:** Set `GSw_PVB = 1` for `st-AZNM_baseline`, `st-AZNM_limitre`, and `st-AZNM_optimized`.
- **Case change:** PVB type 1 uses an ILR of `1.34`, matching the utility-scale PV ILR.

### Results

- Comparison PowerPoint and the three completed run folders were copied to `C:\Users\gtosado\OneDrive - RMI\Runs`.
- All three AZNM cases completed successfully with PVB enabled.
- The run demonstrates that PVB can be enabled in the current CEPM workflow once the PVB profile and VOM compatibility issues are addressed.
- Compare the PVB6 results against the corresponding PVB-off base run to quantify changes in PVB builds, standalone PV/storage builds, gas capacity, system cost, and generation.

### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** Retain PVB as an available resource for the VPP/DER sensitivity work, while treating the two ReEDS modifications as testing fixes until they are reviewed for integration into `dev`.
- **NEXT STEP:** Run an otherwise identical PVB-off case and compare capacity, generation, system costs, and gas builds against `v20261029gt_PVB6`.
- **ISSUE:** Current PVB preprocessing expects `recf_upv.h5` when PVB and UPV share an ILR, although the current workflow calculates the UPV profile directly rather than retaining that standalone file.
- **ISSUE:** UPV VOM is explicitly zero in the ATB plant-characteristic inputs. Because GAMS does not retain zero-valued parameter records, the derived PVB component VOM parameters are empty and `check_inputs.py` interprets them as missing. For this test, both PVB components were assigned `0.01 $/MWh`.
- **ISSUE:** These fixes should be reviewed before being merged into `dev`; the `0.01 $/MWh` PVB VOM should be treated as a numerical/input-checking workaround rather than a substantive cost assumption.

### Checklist

- [ ] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with the PVB run-breaking issues encountered
- [ ] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with the `recf.py` and `b_inputs.gms` changes
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [x] I moved batch results to the OneDrive `Runs` folder
- [ ] I added any issues we found to the JIRA issues epic
- [x] I edited LLM-generated text to keep this entry short and to the point
- [ ] Open a pull request and add results of a recent run as an attachment

## Batch entry: v20261009postcapex**
**Author: Tyler Fitch**

**Summary:** Implements a minor update to our gas capex calculations -- mostly
normalizing on 2022 dollars.

### Batch details

- **Built from:** `v20261001gt`
- **Space and Time:** st/AZ.NM 2026-2032, every 3 years
- **Cases:** `baseline, limitre, optimized`

### Change log

- **ReEDS change:** Changed `gas-ccgt_cepm_all` in order to use inflation-adjusted capex

### Results

- Compare files are on VM-Ouputs --
- Compare files show marginally less CCs and CTs procured in all cases

### Documentation, decisions, next steps, & issues

- No changes needed -- this is a minor inputs change.

### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [X] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point
- [/] Open a pull request and add results of a recent run as an attachment

## Batch name: `v20261006gt_AEO`
**Author: Gaby**


Summary: Ran the st-AZNM baseline, limit-RE, and optimized cases using the AEO case assumptions to compare results against the previous AZNM runs. This batch is intended to isolate the impact of the AEO assumptions while keeping the existing baseline/limit-RE/optimized case structure consistent.

### Batch details

- **Built from:**  v20261001gt`
- **Space and Time:** `WECC-SW, 2026-2032 every 3 years`
- **Cases:** st/AZ.NM`, 2026–2032 every 3 years
- **Run comments:**

### Change log

- **ReEDS change:** No ReEDS code changes.
- **Case change:** Added `st-AZNM_AEO_baseline`, `st-AZNM_AEO_limitre`, and `st-AZNM_AEO_optimized`to use AEO gas assumptions
- **Case change:** Added `{Case}`

### Results
When compared to previous results that use Anna's capex calculations, this run has much more gas build out and more wind retirements


### Documentation, decisions, next steps, & issues

- **PROPOSED DECISION:** We continue using Anna's Capex calculations
- **DOCUMENTATION:** no need, just probing two capex numbers
- **NEXT STEP:** We continue using Anna's Capex calculations
- **ISSUE:** no need, just probing two capex numbers

### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [X] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point
- [X] Open a pull request and add results of a recent run as an attachment
---
## Batch entry: `v20261001gt`
**## Author: Gaby**

Summary:  Re-ran the st-AZNM baseline, limit-RE, and optimized cases to test a fix for a pandas 3.x issue that caused ReEDS to drop buildable onshore wind in landlocked regions. The fix ensures wind supply-curve bins retain the correct data type, preventing onshore wind from being removed during input processing. The corrected runs successfully restored onshore wind as a build option.

### Batch details

- **Built from:** 20260925-test
- **Space and Time:** st/AZ.NM, 2026–2032 every 3 years
- **Cases:** st-AZNM_baseline, st-AZNM_limitre, st-AZNM_optimized
- **Run comments:** Successful run of all three cases on fix/wind-rsc-pandas3.

### Change log

- **ReEDS change:** Changed reeds/input_processing/writesupplycurves.py in agg_supplycurve() so an empty supply curve's bin column is explicitly assigned int64 rather than being created from a bare [].
- **Reason for change:** Under pandas 3.x, an empty offshore-wind supply curve could cause the populated onshore-wind bin values to be upcast from integers to floats during pd.concat. This changed labels such as wsc1 to wsc1.0, causing ReEDS to silently drop the onshore-wind cap and cost rows. This was occurring for st/AZ.NM because the region has no offshore-wind resource while GSw_OfsWind=1.
- **Case change :No substantive case-setting changes; this batch re-runs the existing AZNM baseline, limit-RE, and optimized cases with the wind supply-curve fix.

### Results
All three cases completed successfully.

Compare-cases output:
runs/v20261001gt_st-AZNM_baseline/outputs/comparisons/

Onshore wind returned as a build option after the fix. Before the fix, all three AZNM cases remained at roughly 0.7 GW of existing onshore wind through 2032, with effectively no new wind builds.

After the fix, substantial new onshore wind is built. By 2032, onshore wind capacity increases to roughly 11 GW in the baseline, 12 GW in limit-RE, and 20 GW in the optimized case.

The effect is largest in the optimized case, where restoring the wind supply curve results in roughly 19 GW of additional onshore wind capacity by 2032 relative to the broken run.


The corrected wind availability also changes the broader capacity mix, confirming that the pandas 3.x supply-curve bug was materially affecting the model's resource-selection results.

### Documentation, decisions, next steps, & issues

- **DOCUMENTATION:** The pandas 3.x wind supply-curve issue and fix are documented in CEPM/known-reeds-issues.md and CEPM/reeds-to-cepm-log.md.
- **NEXT STEP:** Merge fix into dev
- **ISSUE:** The underlying bug also exists upstream and can affect other landlocked regions when offshore wind is enabled but the offshore supply curve is empty.
### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [X] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point
-
## Batch name: `v20260929_st-AZNM...`, `v20260929v2_st-MSALGA`, `v20260929v3_st-VA`

This batch implements state-level regions (while still using z134 zones) to
align with our data center load forecasts. It also is the first to use the
underlying ReEDS repo synced with the August 2026 release. Finally, we also
create a few additional testing geographies for st/MS.AL.GA and st/VA.

### Batch details

- **Built from:** n/a, new upstream sync
- **Space and Time:** `st/AZ.NM, 2026-2032, every 3 years`
- **Cases:** ` baseline, limitre, optimized`
- **Run comments:** ~30 minutes per case~

### Change log

- **ReEDS change:** Underlying repo is synced with August ReEDS release
- **Case change:** Changed `GSw_Region` to `st/AZ.NM`

### Results

- Run outputs are in VM-Outputs

### Documentation, decisions, next steps, & issues

- **DECISION:** Case regions will be defined at state boundaries moving forward. See [20260929-state-regions](/CEPM/decisions/20260929-state-regions.md).
- **ISSUE**: An underlying ReEDS issue is causing onshore wind to not be selectable for the AZNM runs, which is distorting results.
- **ISSUE**: An underlying ReEDS issue is causing the VA-limitre runs to be infeasible.
- **ISSUE**: If you run several multistep CEPM runs with the same batch name, by default the run_cepm.ps1's will compare all of them instead of isolating comparisons to the thrhee youu're looking at.


### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [X] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point

---
## Batch name: `v20260903qoff` / `v20260903h2off` / `v20260903h2qoff`

These three batches explore the impacts of the interconnection queue penalty
and allowance for hydrogen-combusting generation.
With the previous run, these batches from a 2x2 testing whether the
interconnection-queue penalty and H2-burning capacity were distorting the
two-step RE-ceiling result.
**Finding:** the queue penalty matters a lot (10 percentage points) for costs,
less for technologies; H2 combustion doesn't matter at all (hydrogen by-default
is priced the same as gas), and the two don't interact.

### Batch details

- **Built from:** `v20260902t7` (the first end-to-end two-step batch)
- **Space and Time:** WECC-SW, 2026-2032 every 3 years
- **Cases:** `baseline`, `limitre`, `optimized` — 3/3 produced `outputs.h5` in
  every batch (checked directly; `runreeds.py` exits 0 even when a case fails)
- **Run comments:** ~45-50 min per batch, phase B's two cases concurrent

### Change log

- **ReEDS change:** added `GSw_CapPenaltyMult` (`b_inputs.gms`, `cases.csv`) to
  scale the interconnection-queue penalty. Default `1`, so inert. How it
  works and why an epsilon rather than `0`: guidance §5.6.
- **Case change:** `GSw_CapPenaltyMult = 0.000001` on the three WECC-SW cases
  in `qoff` and `h2qoff` — queue constraint effectively off.
- **Case change:** `GSw_H2Combustion = 0` and `GSw_H2CombinedCycle = 0` as the
  `cases_cepm.csv` default, for `h2off` and `h2qoff`. *(commit "Disable H2
  combustion in CEPM cases; 2x2 shows it changes nothing")*

### Results

- Compare cases deck (6-run, no-H2, penalty on vs off): `runs/
  v20260903h2off_WECC-SW_baseline/outputs/comparisons` (note that our script
  renamed these cases!)
- `_limitre` vs `_optimized` 2032 objective gap — the headline RE-ceiling cost:

  |                       | penalty on | penalty off |
  |-----------------------|-----------:|------------:|
  | **H2 combustion on**  | +33.38%    | +43.43%     |
  | **H2 combustion off** | +33.39%    | +43.43%     |

- The queue penalty suppresses onshore wind and favours PV: turning it off
  moves the WECC-SW baseline by -14.9% PV, +12.6% wind-ons, and shifts
  `wind-ons` in `p31` from 3,867 MW over its queue limit to 10,570 MW over.
- The model switched pretty freely between regular CCs/CTs and H2 CCs/CTs with
  almost no cost difference.
- Compare cases  deck for  no-H2, IX penalty off, close to our default run
  moving forward: `runs/v20260903h2qoff_WECC-SW_baseline/outputs/comparisons/`.
- Cumulative new capacity 2026-2032, MW_ac, for that run (`v20260903h2qoff`):

  | tech group | `baseline` | `limitre` | `optimized` | `limitre` − `optimized` |
  |---|---:|---:|---:|---:|
  | pv | 17,184.0 | **17,184.0** | 38,014.2 | −20,830.3 |
  | wind-ons | 18,506.0 | **18,506.0** | 22,908.3 | −4,402.3 |
  | battery | 8,164.6 | 8,133.5 | 8,237.4 | −103.9 |
  | pumped-hydro | 1,455.7 | 695.6 | 2,314.8 | −1,619.2 |
  | gas | 7,012.0 | 38,547.3 | 24,495.1 | **+14,052.2** |

- The ceiling binds exactly on pv and wind-ons (`limitre` equals `baseline` to
  the printed digit). Storage sits *below* its cap — battery 8,133.5 against
  8,164.6, pumped-hydro 695.6 against 1,455.7 — so the model declines storage it
  was allowed to build once the RE it would firm is unavailable.
- Denied ~20.8 GW of PV and ~4.4 GW of wind, the model buys ~14.1 GW of gas.
- Note--these numbers are so big because we were mistakenly packing Texas's
  load into el Paso!

### Documentation, decisions, next steps, & issues

- **DECISION:** keep `GSw_H2Combustion = 0` for CEPM cases.
- **DOCUMENTATION:** `CEPM/guidance/interconnection-queue-and-prescribed-builds.md`
  section 4.5 (the measurement) and 4.6 (the 2x2); `GSw_CapPenaltyMult` in
  section 5.6.
- **ISSUE:** We haven't yet resolved how to handle the interconnection queue
  data inputs and penalty--we need to explore where that data comes from,
  how it interacts with prescribed builds, and how we want to handle moving
  forward. There's also an issue with prescribed builds accumulating over time
  between solve years, which has uneven impacts on how the queue exceedance
  penalty hits and what happens. Currently, our `mult` switch is set at very
  low but not zero -- likely we will want to change that.
- **ISSUE:** We just found that Texas's loadsite load was being pushed into
  zone p59, which was distorting a lot of our run.
- **ISSUE:** We don't know what the default transmission expansion options are
  -- makes sense to resolve on that. Likely within-region transmission
  expansion ok?

### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point

---

## Batch name: `v20260902t7`

This run was the final in a series of test runs that developed a two-step
process for run batches that tested an optimized portfolio against one
that was constrained from building new RE beyond the baseline.

| case | data-center load | RE ceiling | description |
| --- | --- | --- | --- |
| `baseline` | off | none | no-data center load, optimized |
| `optimized` | on | none | optimal scenario with data center load |
| `limitre` | on | capped at the baseline's own wind/solar/storage buildout | what gets built when additional renewables aren't available |

**The two-step mechanic:** `limitre`'s ceiling can't be written by hand, because
it has to equal whatever the baseline happened to build. So `run_cepm.ps1 -m`
runs `baseline` first, harvests its `cap_new_out` into a per-batch cap file, and
only then launches `limitre` and `optimized`. The ceiling is enforced by two
purpose-built cumulative GAMS constraints (`GSw_CEPM_TgCap`) written in MW_ac so
the cap file, `cap_new_out` and every plot share units.

### Batch details

- **Built from:** `v20260825_WECC-SW` — `optimized` is that batch's `dcload`
  under the new name, and `limitre` is the case added between it and `baseline`.
- **Space and Time:** WECC-SW, 2026-2032 every 3 years
- **Cases:** `baseline`, `limitre`, `optimized`.
- **Run comments:** ~46 min for all three. One command:
  `.\run_cepm.ps1 -y -x -b v20260902t7 -c cepm -m WECC-SW`

### Change log

- **ReEDS change:** added the two cumulative cap equations (`c_model.gms`), their
  parameters and two guardrails (`b_inputs.gms`), and two `runfiles.csv` rows to
  stage the cap files. All additive — no upstream line edited. Design and
  decisions D1-D8: `CEPM/guidance/two-step-re-limited-runs.md`.
- **CEPM change:** `run_cepm.ps1 -m`, plus `make_tg_cap.py` (harvests the
  ceiling) and `multistep_cases.py` (validates the three cases, generates the
  per-batch cases file).
- **ReEDS change:** added `cepmtgcapscen`, `GSw_CEPM_TgCap`,
  `GSw_CEPM_TgCapStartYear` to `cases.csv` (defaults off)
- **Case inputs change:** Added `WECC-SW_limitre` / `WECC-SW_optimized`
  to `cases_cepm.csv`, `WECC-SW_limitre` uses the new stiches.

### Results

- Compare cases deck:
  `runs/v20260902t7_WECC-SW_baseline/outputs/comparisons/results-WECC-SW_baseline,WECC-SW_limitre,WECC-SW_optimized.pptx`
- Cumulative new capacity 2026-2032, MW_ac:

  | tech group | `baseline` | `limitre` | `optimized` |
  |---|---:|---:|---:|
  | pv | 20,181.2 | **20,181.2** | 41,305.4 |
  | wind-ons | 16,438.9 | **16,438.9** | 18,529.3 |
  | battery | 8,583.0 | **8,583.0** | 9,354.6 |
  | gas | 5,198.5 | 35,929.2 | 22,644.0 |

- **The ceiling binds exactly.** `limitre` lands on its cap to the printed
  precision for pv, wind-ons and battery — the mechanism works through the full
  orchestrated path, with a ceiling nobody wrote by hand.
- **Data-center load leans hard on new RE when allowed to.** `optimized` vs
  `baseline` more than doubles PV, 20.2 -> 41.3 GW.
- **Denied that RE, the model buys thermal.** `limitre` vs `optimized` gives up
  ~21 GW of PV and ~2 GW of wind and replaces them with ~15.5 GW of gas/h2, at a
  **+33.4%** higher 2032 objective.
- The baseline's 2032 objective (40,443,825,903.57) is identical to the
  pre-change baseline, confirming the additive GAMS changed nothing when off.

### Documentation, decisions, next steps, & issues

- **DECISION:** use a three-case factorial (`baseline`/`limitre`/`optimized`)
  rather than a before/after pair, so the load effect and the ceiling effect can
  be attributed separately.
- **DECISION:** harvest the ceiling from the baseline's own `cap_new_out` rather
  than specifying it, and generate the cap file per batch (deleted afterwards)
  so a stale ceiling can never be picked up.
- **DOCUMENTATION:** `CEPM/guidance/two-step-re-limited-runs.md` — design,
  decisions D1-D8, and the T0-T10 test record.
- **ISSUE (Addressed):** We found an issue where ReEDS calculates an
  interconnection penalty  for capacity deployment above a pre-established interconnection queue -- which causes huge costs and may distortt results.
- **ISSUE (Addressed):** We found that our current settings allowed portfolios
  to build H2-burning CCs and CTs.

### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic (we sort of already addressed these?)
- [X] I edited LLM-generated text to keep this entry short and to the point

---

## Batch name: `v20260825_WECC-SW`

The WECC-SW data-center scenario set, and the batch the two-step work grew out
of. Establishes the pair that `limitre` was later inserted between: a no-load
`baseline` and a `dcload` case carrying EPRI medium data-center load.

### Batch details

- **Built from:** n/a — earliest batch recorded here.
- **Geography:** WECC-SW (`nercr/WECC_SW`, `z132`, 2026-2032 in 3-year steps)
- **Cases:** `baseline`, `dcload`, `dcloco2` — 3/3 produced `outputs.h5`
- **Run comments:** ~22 min for the baseline. Branch `mvp-scenario`, commit
  `8292d087` — predates the two-step branch entirely.

### Change log

- **Case change:** `dcload` turns on data-center load — `GSw_LoadSiteCF` and
  `GSw_LoadSiteRA` to `1`, `GSw_LoadSiteTrajectory` to
  `st_epri_medium_extended_to_2032`. `baseline` leaves all three off.
- **Case change:** `dcloco2` is `dcload` plus MGA — `GSw_MGA_CostDelta = 0.05`
  and `GSw_MGA_Objective = co2`, i.e. minimise CO2 subject to staying within 5%
  of least cost.

### Results

- Compare cases deck:
  `runs/v20260825_WECC-SW_baseline/outputs/comparisons/results-WECC-SW_baseline,WECC-SW_dcload,WECC-SW_dcloco2.pptx`
- Cumulative new capacity 2026-2032, MW_ac:

  | tech group | `baseline` | `dcload` | `dcloco2` |
  |---|---:|---:|---:|
  | pv | 20,181.2 | 41,305.4 | 62,646.2 |
  | wind-ons | 16,438.9 | 18,529.3 | 21,302.7 |
  | battery | 8,583.0 | 9,354.6 | 21,410.1 |
  | gas | 5,198.5 | 22,644.0 | 15,246.6 |

- Data-center load roughly doubles PV (20.2 -> 41.3 GW) and quadruples gas
  (5.2 -> 22.6 GW).
- Allowed 5% more cost to chase CO2, the model buys still more PV and a lot more
  battery (9.4 -> 21.4 GW) and backs gas down (22.6 -> 15.2 GW).


### Documentation, decisions, next steps, & issues

- **NEXT STEP (done):** the gap this batch exposed — `dcload` shows what the
  optimizer *would* build, but not what happens if that RE isn't available —
  became the `limitre` case in `v20260902t7`.
- **CHANGE:** This batch ran with `cleanup_level = 2`, which deleted `z_rep.csv`,
  `objfn_raw.csv` and `systemcost.csv` from `outputs/`. And caused batch-runs
  of ./run_cepm.ps1 to fail. The output values survive inside  `outputs.h5` (as
  float32), but the CSVs are gone. CEPM now runs `cleanup_level = 0`.
- **NOTE:** `dcloco2`'s reported 2032 objective (92.3bn) is *lower* than
  `dcload`'s (109.1bn), which is not what you would expect from a run
  constrained to within 5% of least cost. MGA does a second solve minimising
  `MGA_OBJ` (`3_solve_oneyear.gms:267-273`), so `z_rep` likely does not mean
  the same thing here. Unresolved — don't compare `dcloco2`'s objective against
  the others without checking what it records.

### Checklist

- [X] I updated [`known-reeds-issues.md`](CEPM/known-reeds-issues.md) with any run-breaking issues I encountered
- [X] I updated [`reeds-to-cepm-log.md`](CEPM/reeds-to-cepm-log.md) with any changes to ReEDS files
- [ ] I added any decisions to [`CEPM/decisions/`](CEPM/decisions/) and linked to them here
- [X] I moved batch results to the VM-Outputs folder
- [X] I added any issues we found to the JIRA issues epic
- [X] I edited LLM-generated text to keep this entry short and to the point

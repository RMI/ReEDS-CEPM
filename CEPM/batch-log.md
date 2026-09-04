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

## TEMPLATE Batch entry

**## Batch name: TEMPLATE `{Batch name here, e.g., v20260903}`**

Optional summary: What'd we change, why, what'd we find, what's next

### Batch details

- **Built from:** `{Previous batch, e.g., v20260903}`
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

- [ ] I updated known-reeds-issues.md with any run-breaking issues I encountered
- [ ] I updated reeds-to-cepm-log.md with any changes to ReEDS files
- [ ] I updated CEPM/README with any relevant new documents
- [ ] I moved batch results to the VM-Outputs folder
- [ ] I edited LLM-generated text to keep this entry short and to the point

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

### Checklist

- [x] I updated known-reeds-issues.md with any run-breaking issues I encountered
- [x] I updated reeds-to-cepm-log.md with any changes to ReEDS files
- [x] I updated CEPM/README with any relevant new documents
- [/] I moved batch results to the VM-Outputs folder
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

- [x] I updated known-reeds-issues.md with any run-breaking issues I encountered
- [x] I updated reeds-to-cepm-log.md with any changes to ReEDS files
- [x] I updated CEPM/README with any relevant new documents
- [X] I moved batch results to the VM-Outputs folder
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

- [X] I updated known-reeds-issues.md with any run-breaking issues I encountered
- [X] I updated reeds-to-cepm-log.md with any changes to ReEDS files
- [X] I updated CEPM/README with any relevant new documents
- [X] I moved batch results to the VM-Outputs folder
- [X] I edited LLM-generated text to keep this entry short and to the point
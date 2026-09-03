# Interconnection queues and prescribed builds: how they work, and why they collide in 2026

**Status:** investigation, 2026-09-03. Findings verified against
`runs/v20260902t7_WECC-SW_*` (the first end-to-end two-step batch) and against
the code in this fork at `mvp/two-step-runs`.

**Why this doc exists.** Two exogenous mechanisms both constrain what ReEDS
builds in its early years: an **interconnection-queue ceiling** and a set of
**prescribed builds**. In CEPM runs they contradict each other — the queue says
one thing about 2026, the prescriptions say another, and the model resolves the
contradiction by paying a very large penalty. That penalty turns out to be
**~77% of the 2026 objective**, which is worth understanding before anyone reads
a cost number off a CEPM run.

**Short version:**

- The queue ceiling is a **soft** cap. Exceeding it costs a flat
  **$10,000,000/MW**, charged again in every modeled year on a cumulative
  quantity.
- CEPM's 2026 solve must place **32,999 MW** of capacity against a queue
  headroom of **11,794 MW**. The overshoot is structural, not a tuning problem:
  the 2026 solve absorbs **16 years** of accumulated prescriptions (2011-2026)
  while the queue offers **one year** of headroom.
- ~94.5% of the 2026 violation *quantity* is capacity the model was required to
  build. But that does **not** mean the penalty is inert: measured directly
  (§4.5), removing it shifts the WECC-SW buildout by −15% PV, +13% onshore wind
  and +158% h2, and moves the two-step headline result from +33.4% to **+43.4%**.
  The active channel is the per-MW surcharge on *marginal* builds in cells
  already over their limit, which applies in every year.
- The penalty is in the objective (`Z`) but **not** in reported
  `systemcost.csv`. Anyone comparing `z_rep` across cases is comparing mostly
  penalty.
- `GSw_CapPenaltyMult` (§5.6) turns the constraint off for diagnosis. The "off"
  run is **not** a better estimate of reality — it removes something physically
  real — but it bounds how much of a result the queue mechanism is driving.

---

## 1. The two mechanisms at a glance

| | Interconnection queues | Prescribed builds |
|---|---|---|
| Question it answers | "How much *can* physically interconnect here by when?" | "What is already committed and *must* get built?" |
| Direction | Ceiling | Floor |
| Hard or soft | **Soft** — penalized slack `CAP_ABOVE_LIM` | **Soft in one direction** — free slack `EXTRA_PRESCRIP` allows *more*, nothing allows *less* |
| Price of violating | $10,000,000/MW, every modeled year | n/a (can't go under) |
| Indexed by | `(tech group, region, year)` | `(prescription category, region, year)` |
| Years covered | 2026-2030 only | through ~2030, from unit data |
| On/off switch | **none** | `GSw_ForcePrescription` (default 1) |

They are not reconciled anywhere. Nothing checks that the capacity the
prescriptions force into a region fits under the queue ceiling for that region.

---

## 2. The interconnection-queue ceiling

### 2.1 Data source

`inputs/capacity_exogenous/interconnection_queues.csv` — 24,581 data rows.

| column | meaning |
|---|---|
| `r` | **county** FIPS with a `p` prefix (`p01001`), not a model region |
| `tg` | tech group — the 13 members of `inputs/sets/tg.csv` |
| `2026` … `2030` | **cumulative** MW of queue headroom by that year |

The year columns ramp: a county/tech cell rises linearly to its full queue
position by 2030. For example `pv` in `z28` after aggregation runs
6,083 → 12,166 → 28,313 → 44,460 → 60,606 MW.

**Provenance is undocumented.** `docs/sources.csv` has a row for this file
(`/inputs/capacity_exogenous/interconnection_queues.csv`) but every descriptive
field — description, vintage, citation, dollar year — is **empty**. Compare the
unit database on the next row, which at least carries
*"EIA-NEMS database of existing generators"*. So we cannot currently say which
queue snapshot this is, as of when, or how "queue MW" was converted into
"MW that will interconnect by year Y". **That is a gap worth closing before
leaning on these numbers for a CEPM result**, since §4 shows they are binding.

**The data stops at 2030.** There is no 2031 or 2032 column. That has a direct
consequence in §2.3.

### 2.2 How it is wired into the run

`reeds/input_processing/copy_files.py:1403-1433`, inline in `main()` — **not**
via `runfiles.csv`, and with **no scenario switch**:

1. Read the county-level file.
2. Filter to counties in the run's `GSw_Region`.
3. Map county → model region (`r_county`), with separate branches for
   single-resolution, mixed and county resolution.
4. `groupby(['tg','r']).sum()` → write `inputs_case/cap_limit.csv`.

The absence of a switch is why
[`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) §F4 rejected
reusing this mechanism for the RE ceiling: making it case-specific would mean
editing `copy_files.py`, the most-churned file in the tree.

Loaded in GAMS as `cap_limit(tg,r,t)` and consumed by one equation.

### 2.3 How it is wired into the optimization

`reeds/core/setup/c_model.gms:1389`:

```gams
eq_interconnection_queues(tg,r,t)
    $[tmodel(t)$(yeart(t)>=model_builds_start_yr)
    $(sum{(tgg,rr), cap_limit(tgg,rr,t)})
    $sum{(i,newv)$tg_i(tg,i), valinv(i,newv,r,t)}
    $(not Sw_PCM)]..

    cap_limit(tg,r,t) + CAP_ABOVE_LIM(tg,r,t)

    =g=

    sum{(i,newv,tt)$[valinv(i,newv,r,tt)$tg_i(tg,i)
                     $(yeart(tt)>=interconnection_start)
                     $(tmodel(tt) or tfix(tt))],
        INV(i,newv,r,tt) + INV_REFURB(i,newv,r,tt)$[refurbtech(i)$Sw_Refurb] }
;
```

Four things matter here.

**It is cumulative.** The right-hand side sums investment from
`interconnection_start` (**2025**, `inputs/scalars.csv:52`) through the current
year. So an overshoot in 2026 stays on the books and is re-penalized in 2029.

**It is soft.** `CAP_ABOVE_LIM(tg,r,t)` (`c_model.gms:30`) absorbs any excess.
The model is never made infeasible by this constraint — it just pays.

**The price is flat and enormous.** `d_objective.gms:47`:

```gams
+ sum{(tg,r), cap_penalty(tg) * CAP_ABOVE_LIM(tg,r,t) }
```

`cap_penalty` is loaded once at `b_inputs.gms:2024` from
`inputs/financials/cap_penalty.csv` and **never rescaled or deflated**. All 13
rows are identical: **10,000,000** $/MW. For scale, gas-CC capex is roughly
$1.3M/MW — the penalty is ~8× the cost of the plant. The term sits inside
`Z_inv(t)` scaled by `pvf_capital(t)`, which is **1.0** in CEPM runs, so it
enters undiscounted.

**It switches itself off in 2032.** The guard
`$(sum{(tgg,rr), cap_limit(tgg,rr,t)})` requires *some* nonzero cell for that
year. Because the source data ends in 2030, `cap_limit(tg,r,'2032')` is empty,
the sum is zero, and the equation is never generated in the final CEPM solve
year. `CAP_ABOVE_LIM(tg,r,'2032')` is then penalized but unconstrained, so the
optimizer drives it to zero. **Every CEPM run today is unconstrained by
interconnection queues in 2032.**

There is **no switch** to disable the constraint — `cases.csv` contains nothing
queue-related. The only ways to turn it off are `Sw_PCM=1` or an all-zero year.

### 2.4 The optimizer sees it; no cost metric reports it

This is the single most important thing to know before quoting a number off a
CEPM run, so it is worth stating exactly. **The penalty is in the objective and
in no reported cost metric.** Verified end to end:

| where | penalty present? |
|---|---|
| `Z` / `Z_inv(t)` — what the solver minimizes (`d_objective.gms:47`) | **yes** |
| `z_rep.csv`, `objfn_raw.csv` — the objective, dumped | **yes** (inherited) |
| `systemcost.csv` — all 14 cost categories | **no** |
| `systemcost_ba.csv` → `reeds/results.py:calc_systemcost()` → retail rates, bokeh report | **no** (inherits the exclusion) |
| any Python in `reeds/` or `postprocessing/` | **no** — `cap_penalty` and `CAP_ABOVE_LIM` appear in **zero** Python files |
| `report.gms` | **once**, at line 1745, inside `error_check('z')` |
| `cap_above_limit.csv` | the **MW quantity only** — registered in `report_params.csv` as `--MW--`, never priced |

The one appearance in `report.gms` is the tell. It exists precisely because the
objective contains something reported system cost does not, and the check would
not balance without it:

```gams
* account for penalty paid to deploy capacity beyond interconnection queue limits
        + sum{(tg,r), cap_penalty(tg) * CAP_ABOVE_LIM.l(tg,r,t) }
```

Practical consequences:

- **`z_rep` and `systemcost.csv` are not comparable**, and the gap is the penalty
  (quantified in §4.2). Neither is "wrong" — they measure different things.
- The only way to see the penalty in outputs is to take `cap_above_limit.csv`
  and multiply by $10M/MW yourself. Nothing does that for you.
- `error_check('z')` reconciles only the **final** solve year, where §2.3 says
  the penalty is zero. A clean `error_check` therefore says nothing about whether
  large penalties were paid in 2026 or 2029.

"The optimizer sees it" is true but needs the qualifier from §4.3: for ~94.5% of
the penalty the optimizer sees a **constant** — a term with no gradient, because
the capacity it is levied on is forced by `eq_forceprescription`. Only the
voluntary remainder is a live signal that changes a decision.

---

## 3. Prescribed builds

### 3.1 Data sources

Two families, which behave differently and are easy to conflate.

**Non-RSC** (gas, coal, battery, hydro, landfill gas) — derived from the unit
database:

```
inputs/capacity_exogenous/ReEDS_generator_database_final_{unitdata}.csv
   (runfiles.csv:256 -> inputs_case/unitdata.csv;  unitdata = "EIA-NEMS")
        -> reeds/input_processing/writecapdat.py:338-345
        -> inputs_case/prescribed_nonRSC.csv, prescribed_nonRSC_energy.csv
```

**RSC / resource-constrained** (upv, wind-ons, geohydro) — from siting-scenario
files, selected by switch:

| file | switch | runfiles row |
|---|---|---|
| `prescribed_builds_wind-ons_{GSw_SitingWindOns}.csv` | `GSw_SitingWindOns` (default `reference`) | 206 |
| `prescribed_builds_wind-ofs_{GSw_OffshoreFiles}_{GSw_SitingWindOfs}.csv` | `GSw_OffshoreFiles`, `GSw_SitingWindOfs` | 205 |
| `exog_cap_upv_{siting}.csv`, `exog_cap_wind-ons_{siting}.csv`, `exog_cap_geohydro_*.csv` | siting switches | — |

These land in the run as `inputs_case/prescribed_rsc.csv`, plus
`prescribed_builds_wind-{ons,ofs}.csv` and `exog_cap_*.csv`.

**Unit trap:** `prescribed_rsc.csv` is **MW_dc for PV**, while every reported
capacity output is MW_ac. §4.3 uses this to prove a point, but treat it as a
hazard: a prescribed PV number cannot be compared to `cap_new_out` without
dividing by `ilr_utility` (1.34).

**Wind is double-listed.** Onshore wind appears in *both* `prescribed_rsc.csv`
and `prescribed_builds_wind-ons.csv`. Any reconstruction that sums both
double-counts — this is the same trap flagged as F5 in
[`two-step-re-limited-runs.md`](two-step-re-limited-runs.md).

### 3.2 How prescriptions reach a solve year — the 16-year pile-up

This is the single most important mechanism in this document.

`b_inputs.gms:1985-1991`:

```gams
noncumulative_prescriptions(pcat,r,t)$tmodel_new(t)
    = sum{tt$[(yeart(tt)<=yeart(t)
* this condition populates values of tt which exist between the
* previous modeled year and the current year
              $(yeart(tt)>sum{ttt$tprev(t,ttt), yeart(ttt) }))],
          prescribednonrsc(tt,pcat,r,"value") + prescribedrsc(tt,pcat,r,"value") } ;
```

A solve year absorbs **every prescription since the previous solve year**. That
is sensible when solve years are 2 years apart. It is dramatic for CEPM.

CEPM cases use `startyear=2010` (inherited from `cases.csv`) and
`yearset=2026..2032..3`, giving solve years **2010, 2026, 2029, 2032**. The gap
between the first two is **16 years**. So the 2026 solve is required to build
everything prescribed for **2011 through 2026** — sixteen years of committed
projects, landing in a single model year.

`m_required_prescriptions` (`b_inputs.gms:1943-1951`) is the cumulative
counterpart, and adds existing RSC capacity `caprsc` for the RSC categories.

### 3.3 How it is wired into the optimization

`c_model.gms:922`:

```gams
eq_forceprescription_power(pcat,r,t)
    $[tmodel(t)$force_pcat(pcat,t)$Sw_ForcePrescription
    $sum{(i,newv)$[prescriptivelink(pcat,i)], valinv(i,newv,r,t) }
    $(not Sw_PCM)]..

    sum{(i,newv,tt)$[...], INV(i,newv,r,tt) + INV_REFURB(...)}   =e=
    sum{tt$[...], noncumulative_prescriptions(pcat,r,tt)}
    + EXTRA_PRESCRIP(pcat,r,t)$[yeart(t)>=firstyear_pcat(pcat)]
    + EXTRA_PRESCRIP(pcat,r,t)$[r_offshore(r,t)...] ;
```

It is written as an equality, but `EXTRA_PRESCRIP` makes it **a floor, not an
exact target**. `EXTRA_PRESCRIP` appears only in `c_model.gms` (declared line
35, used at 941/944/972) and **never in `d_objective.gms`** — it is genuinely
free slack. So the model may build *more* than prescribed at no charge, but
never less.

Supporting machinery:

- `prescriptivelink(pcat,i)` — `b_inputs.gms:909-922`, maps prescription
  categories to technologies. Upgrades are excluded (line 922).
- `force_pcat(pcat,t)` — `b_inputs.gms:5938-5941`, activates the equation for a
  category in years before `firstyear_pcat` or in any year with a prescription.
- `GSw_ForcePrescription` — `cases.csv`, default **1**. Turning it off "will
  allow unlimited but not free builds in historical years".

---

## 4. Findings

All figures from `runs/v20260902t7_WECC-SW_baseline` (WECC-SW, no data-center
load), which reproduces every other CEPM baseline exactly.

### 4.1 The 2026 collision is structural

| | MW |
|---|---:|
| Total queue headroom available in 2026 (`cap_limit`, all `tg`, all `r`) | **11,794** |
| Total capacity the model builds in 2026 (`cap_new_out`) | **32,999** |

A 2.8× overshoot, and not a tuning problem or a bad region.

#### The asymmetry, stated precisely

The two sides of `eq_interconnection_queues` accumulate on **different clocks**,
and that is the whole bug:

| | how it treats calendar years before 2026 |
|---|---|
| **Build side (RHS)** | `INV(…,2026)` has absorbed every prescription since the previous solve year — for CEPM, all of **2011-2026** (§3.2) |
| **Ceiling side (LHS)** | `cap_limit(tg,r,2026)` is a plain parameter lookup of the queue data's 2026 column. It accumulates nothing from before 2026, and there is nothing to accumulate — the file starts at 2026 (§2.1) |

So sixteen calendar years of committed capacity are compressed onto the build
side of a constraint whose ceiling side represents a single year's queue
position. Nothing in the equation reconciles the two.

#### Why `interconnection_start` does not save us

ReEDS *does* have a mechanism intended to exclude old commitments —
`interconnection_start = 2025`, which drops investment before that year from the
sum. **But it filters on the solve year `tt`, not on the calendar year the
prescribed project actually belongs to:**

```gams
sum{(i,newv,tt)$[... $(yeart(tt)>=interconnection_start) $(tmodel(tt) or tfix(tt))],
    INV(i,newv,r,tt) + ... }
```

CEPM's solve years are 2010, 2026, 2029, 2032. `yeart(2010) = 2010 < 2025`, so
the 2010 solve is correctly excluded — but every 2011-2024 prescription was never
*in* the 2010 solve. §3.2 put it in the **2026** solve, whose `yeart` is 2026 and
therefore passes the filter. Compressing the prescriptions past the previous
solve year **smuggles pre-2025 commitments through a filter designed to exclude
them.**

This is why upstream never sees the problem. With a dense yearset (2010-2050 in
2-year steps) each prescription lands in a solve year at or near its own calendar
year, so 2011-2024 commitments sit in solve years below 2025 and the filter drops
them exactly as intended. CEPM's sparse early yearset is what breaks the
correspondence.

#### How much capacity is affected

Prescriptions landing in the 2026 solve, split at `interconnection_start`
(PV converted from MW_dc at `ilr_utility = 1.34`; §3.1):

| bucket | MW_ac | should it count against the 2026 queue? |
|---|---:|---|
| 2011-2024 commitments | **~16,468** | **no** — before `interconnection_start` |
| 2025-2026 commitments | ~12,810 | yes |
| voluntary/endogenous builds | ~3,721 | yes |
| total 2026 build | ~32,999 | |

Against 11,794 MW of 2026 headroom, the ~16,468 MW of pre-2025 commitments
account for roughly **three-quarters of the 22,669 MW excess**. Had they stayed in
solve years below 2025, most of the penalty in §4.2 would not exist.

Treat those as aggregate estimates: the constraint binds per `(tg, r)` cell, so
the per-cell arithmetic differs and the buckets do not map one-to-one onto the
violations in §4.3. The direction and rough magnitude are solid; the exact split
is not.

This also explains why §5.3d works: adding a solve year before 2025 restores the
correspondence between a prescription's calendar year and the solve year it lands
in, letting `interconnection_start` do the job it was written to do.

The aggregate does resolve later — cumulative builds through 2029 are 42,438 MW
against a 2029 ceiling of 88,713 MW — but per-cell violations persist regardless
of aggregate headroom.

### 4.2 The penalty is real, and it dominates the early-year objective

Reconstructed from reported components rather than taken on faith. Reported
system cost is `raw_inv_cost(t) + pvf_onm(t) × raw_op_cost(t)` with
`pvf_capital = 1.0`, `pvf_onm = 14.764506`:

| year | pvf-weighted `systemcost` | `z_rep` | gap | penalty = `CAP_ABOVE_LIM` × $10M | penalty share of `z_rep` |
|---|---:|---:|---:|---:|---:|
| 2026 | $68,868,357,240 | $295,579,593,787 | $226,711,236,547 | **$226,690,889,150** | **76.7%** |
| 2029 | $41,265,781,781 | $101,691,820,211 | $60,426,038,430 | $66,528,774,040 | 65.4% |
| 2032 | $43,207,677,729 | $40,443,825,904 | −$2,763,851,825 | $0 | 0% |

The 2026 row matches to **0.009%**. The 2032 row is the control: no penalty, and
a −$2.76bn residual from the other reconciliation terms (`cost_cap_fin_mult` vs
`_out`, retirement penalty, curtailment revenue). 2029's shortfall relative to
its penalty is the same terms at the same order of magnitude. The 2026 agreement
is therefore not an artifact of how the check is built.

Excess capacity by year: **22,669 MW** (2026), **6,653 MW** (2029), **0** (2032,
per §2.3).

### 4.3 Most of the 2026 *quantity* is prescribed — but the penalty still changes the answer

> **Corrected 2026-09-03.** This section originally concluded that because ~94.5%
> of the 2026 violation is prescribed capacity, the penalty "inflates the
> objective without changing any decision." **The quantity split below is still
> correct; that inference was wrong.** A direct measurement (§4.5, run
> `v20260903qoff`) shows the buildout changes materially when the penalty is
> removed. The error was treating the 2026 violation quantities as the whole
> story and missing the *marginal* channel: in any `(tg,r)` cell already over its
> limit, every **additional** MW in every year costs the full $10M/MW, and that
> does have a gradient. Read §4.5 before relying on anything here.

A penalty on capacity the model is *required* to build cannot change that
capacity — it shifts `Z` with zero gradient for that portion. Comparing each
violating cell in 2026 against prescriptions summed over 2011-2026 (the window
§3.2 says the 2026 solve absorbs):

| violating cell | excess MW | prescribed MW | verdict |
|---|---:|---:|---|
| coal p29 | 762.0 | 762.0 (`coaloldscr`) | exactly prescribed |
| geothermal p31 | 8.6 | 8.6 (`geohydro_allkm`) | exactly prescribed |
| hydro p31 | 3.0 | 3.0 (`hydund`) | exactly prescribed |
| battery ×3 regions | 5,111.4 | 7,852.6 (`battery_li`) | within prescription |
| pv ×5 regions | 7,048.7 | 15,307.3 MW_dc (`upv`) | within prescription |
| wind-ons ×3 regions | 6,308.7 | 6,759.1 | within prescription |
| gas z28 | 1,473.4 | 1,651.6 | within prescription |
| **gas p59** | **1,953.3** | **694.8** | **1,258.5 MW voluntary** |

So **~94.5% of the penalty is unavoidable** and **~5.5% is a live economic
signal**.

A clean confirmation of the prescribed reading, which also demonstrates the
MW_dc trap from §3.1:

```
prescribed_rsc upv, 2011-2026 : 15,307.25 MW_dc
        / ilr_utility (1.34)  : 11,423.32 MW_ac
cap_new_out upv, 2026         : 11,423.32 MW_ac     <- exact match
```

2026 PV is 100% prescribed, to the last kilowatt. (Wind is messier —
6,759.1 prescribed against 6,708.2 built — because of the double-listing noted
in §3.1; don't reconstruct wind from `prescribed_rsc` alone.)

The 2029 violations are mostly the 2026 overshoot carried forward, not new
builds. `wind-ons` in `p31` is the clean example: 2026 excess 5,202.30, 2029
excess 3,867.47, and the ceiling grew by exactly 1,734.33 − 399.50 = 1,334.83
over that span. 5,202.30 − 1,334.83 = 3,867.47. No new wind was built there at
all; the excess simply decayed against a rising cap.

### 4.4 The one voluntary violation is worth a second look

`gas` in `p59` is the exception, and it does not look like an artifact:

| tech | prescribed 2011-2026 | built 2026 | voluntary |
|---|---:|---:|---:|
| gas-ct | 579.8 | 579.8 | 0 — exact |
| gas-cc | 115.0 | 1,373.5 | **1,258.5 MW** |

The queue table gives `p59` **zero** gas headroom in *every* year, so every MW
of gas there is penalized. The model chose to build ~1.26 GW of gas-CC anyway,
paying **$12.6bn** in 2026 and again on the cumulative total in 2029
(**$20.1bn**), against a capex of roughly $1.6bn. It also added 61.5 MW more in
2029.

A model pays ~8× capex in penalties only when the alternative is worse — here,
presumably dropped load. Two readings, and they have different fixes:

- **The queue data is wrong or too coarse for `p59`.** A zero-in-every-year gas
  entry for a region that evidently needs dispatchable capacity is a suspicious
  input, especially given the undocumented provenance (§2.1).
- **The region is genuinely capacity-short** and the queue is correctly telling
  us so — in which case the $10M/MW penalty is silently substituting for a real
  adequacy conversation.

Either way it deserves a look before any CEPM result leans on `p59`.

**Resolved by §4.5.** With the penalty removed the model builds essentially the
*same* gas-CC in `p59` — 1,373.5 → 1,250.8 MW. The decision was never
penalty-driven, so this is a genuine local requirement, not an artifact of the
constraint. The queue entry for `p59` may still be wrong (§5.2 stands), but the
model is telling us the region needs dispatchable capacity either way.

### 4.5 Measured: turning the penalty off changes the answer

`GSw_CapPenaltyMult` (§5.6) makes this testable rather than arguable. Run
`v20260903qoff` is the T7 three-case two-step batch re-run with
`GSw_CapPenaltyMult = 0.000001`, i.e. the queue constraint effectively removed
and nothing else changed.

**The §4.2 penalty quantification is confirmed, precisely.** The 2026 objective
fell **77.0%** (295.6bn → 67.9bn) against the 76.7% penalty share predicted in
§4.2, and — the stronger check — `z_rep` and pvf-weighted `systemcost` now
reconcile to **0.0%** in 2026 (a $17.9M gap on $67.9bn), where before they
differed by $226.7bn.

**But the buildout changes materially, which refutes §4.3's original
conclusion.** WECC-SW baseline, cumulative 2026-2032 MW_ac:

| tech group | penalty on (T7) | penalty off | change |
|---|---:|---:|---:|
| pv | 20,181.2 | 17,183.8 | **−14.9%** |
| wind-ons | 16,438.9 | 18,504.9 | **+12.6%** |
| h2 | 1,106.1 | 2,849.5 | **+157.6%** |
| battery | 8,583.0 | 8,164.6 | −4.9% |
| gas | 5,198.5 | 4,161.8 | −19.9% |

The mechanism is visible in the 2029 violations. With the penalty on, `wind-ons`
in `p31` sat 3,867.5 MW over its limit; with it off, **10,570.2 MW** over, plus
new violations in `p59` and `p29` that did not exist before. The penalty was
actively suppressing onshore wind in queue-constrained regions and pushing the
model toward PV — the opposite of what one might assume from PV having the
largest *2026* violation, because PV's violation clears by 2029 while
`wind-ons`' persists and is therefore re-priced every year.

**The two-step headline result is sensitive to this.** The `_limitre` vs
`_optimized` 2032 objective gap goes from **+33.4%** to **+43.4%**: the queue
penalty was *compressing* the apparent cost of holding RE at baseline by ~10
percentage points, because `_optimized` (41 GW of PV) incurs more penalty than
`_limitre` (which substitutes gas). Any headline number from a two-step batch
carries this distortion.

**What this does and does not license.** `GSw_CapPenaltyMult = 0.000001` removes
a constraint that represents something real — physical interconnection limits —
so the "off" run is not a better estimate of reality. It is a *diagnostic*
showing how much of a result is attributable to the queue mechanism as currently
parameterised. Given §4.1 (the collision is largely an artifact of CEPM's
yearset), §2.1 (undocumented provenance) and §5.3e (prescribed builds arguably
should not be charged against a queue at all), the honest position is that the
truth lies between the two runs and we cannot yet say where.

---

## 5. Implications for how we set 2026

CEPM is trying to represent **2026 as it actually is**. The current
configuration does not do that cleanly, for a reason that is now precisely
locatable. Options, roughly in increasing order of intrusiveness:

### 5.1 Recognize what the current 2026 number means

Nothing here changes the *physical* buildout: the prescriptions are what get
built, and they are the same in every CEPM case. But **`z_rep(2026)` and
`z_rep(2029)` are not usable as cost figures** — they are 77% and 65% penalty.
Use `systemcost.csv` (which excludes the penalty) for cost reporting, and treat
`z` as an optimization artifact. This costs nothing and should happen
regardless.

Note that comparisons *between* CEPM cases are mostly safe: the penalty was
identical ($298.8bn in 2026, $182.6bn in 2029) across `_limitre` and
`_optimized` in the T7 batch, so it cancels. It does **not** cancel between
`_baseline` and either load case ($226.7bn vs $298.8bn in 2026).

### 5.2 Close the provenance gap on the queue data

`docs/sources.csv` records nothing about `interconnection_queues.csv` — no
vintage, no citation, no method. Given §4.1 shows it binding hard and §4.4 shows
it possibly wrong for a specific region, we should know what snapshot this is
before treating a violation as meaningful. This is the cheapest high-value
action in this list.

### 5.3 Shortening the prescription pile-up — and the traps around `startyear`

The 16-year accumulation (§3.2) exists because CEPM jumps 2010 → 2026. The
obvious response is to raise `startyear`. **Don't reach for it first** — it is
the most trap-laden switch in this area, and there is a cleaner lever (§5.3d).

#### 5.3a Hard ceiling: `startyear` cannot exceed **2022**

The historical hydro capacity-factor data bundled in this repo covers
**2007-2022** — verified directly on both source files staged into a run:

```
inputs_case/net_gen_existing_hydro.csv   min t 2007, max t 2022
inputs_case/cap_existing_hydro.csv       min t 2007, max t 2022
```

`hydcf.py:166-169` filters that data to `t >= startyear`. At `startyear = 2023`
or later the frame empties, `data_endyear = hydcf.index.max()` returns `NaN`
(pandas does not raise on an empty numeric index), and
`np.arange(data_endyear+1, model_endyear+1)` fails with
`ValueError: arange: cannot compute length`. This is the already-logged failure
in [`../known-issues.md`](../known-issues.md) that killed `USA_optimized_mvp` at
`startyear=2026`, and it happens in input processing — before model compile,
let alone a solve.

**That entry's open question is now answered: the cutoff is 2022.** `startyear`
must be ≤ 2022 or `hydcf.py` crashes, full stop.

#### 5.3b Practical ceiling is well below 2022

At `startyear = 2022` exactly one year of hydro data survives the filter. The run
would not crash, but every hydro capacity factor would be derived from a single
year's generation rather than sixteen — a silent quality loss, not an error. Any
value approaching 2022 trades one problem for a worse, quieter one.

#### 5.3c `startyear` also redraws the existing/new capacity boundary

This is the part that reaches beyond hydro. `writecapdat.py` splits the unit
database on `startyear` in several places:

- `create_rsc_wsc` (`writecapdat.py:51-52`) and `poi_cap_init`
  (`writecapdat.py:306-326`) treat `onlineyear < startyear & RetireYear > startyear`
  as **existing capacity**.
- Units with `onlineyear >= startyear` become **prescribed builds** instead.
- hydro techs are reclassified `hydEND`/`hydED` on the same test
  (`writecapdat.py:253-256`).

So raising `startyear` moves units from "prescribed build" into "initial fleet".
That does reduce the pile-up — but it also removes those MW from `cap_new_out`,
which is exactly what the two-step workflow harvests its ceiling from
([`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) §5.3), and what
every "new capacity" plot reports. **Two runs with different `startyear` values
are not comparable on new-capacity metrics.** Not a free knob.

#### 5.3d The better lever: restore an early solve year, leave `startyear` alone

Solve years come from `yearset` and are independent of `startyear` except that
`startyear` is appended to the list and used as a lower bound
(`copy_files.py:1301-1305`). So an **extra early solve year** can split the
prescription window without touching any of the traps above.

**This is not an invention — it is what upstream already does.** ReEDS' default
`yearset` is `2010_2015_2020..2050..3`, which resolves to solve years
**2010, 2015, 2020, 2023, 2026, 2029, 2032, …**. Upstream therefore *has* a 2023
solve year, its 2026 solve carries only 2024-2026 prescriptions, and the
2011-2023 commitments sit in solve years below `interconnection_start` where the
filter drops them. CEPM's `2026..2032..3` deleted the 2015/2020/2023 steps, and
that deletion is what created the collision in §4.1.

#### The extra solve year must be ≤ 2024. **2025 does not work.**

Worth stating explicitly, because 2025 looks like the natural choice and is the
one value that fails:

- The filter is `$(yeart(tt) >= interconnection_start)` with
  `interconnection_start = 2025` — **`>=`, not `>`**. A 2025 solve year is
  therefore *included* in the sum, so the whole pile-up would still be counted.
- It is worse than a no-op. The queue file has **no 2025 column** (it starts at
  2026), so `sum{(tgg,rr), cap_limit(tgg,rr,'2025')}` is zero and the guard drops
  the equation entirely in 2025 — the 2025 builds are unconstrained *in that
  year*. But the 2026 solve sums `tt ∈ {2025, 2026}`, both `>= 2025`, so they
  reappear in full against the 2026 ceiling. The problem is deferred by one
  solve and otherwise unchanged.

So the added year must be **strictly below 2025**. Two sensible choices:

| added solve year | prescriptions still counted in 2026 | vs 11,794 MW headroom |
|---|---:|---|
| none (today) | 2011-2026 → **~29,278 MW_ac** | 2.5× over |
| **2023** (matches upstream's grid) | 2024-2026 → ~17,835 MW_ac | ~6.0 GW over |
| **2024** (aligns with `interconnection_start`) | 2025-2026 → ~12,810 MW_ac | ~1.0 GW over |

**2023** restores upstream's own cadence and is the conservative choice.
**2024** is strictly better at the actual job — it is the largest year still
below `interconnection_start`, so it moves every genuinely pre-2025 commitment
out and leaves exactly the 2025-2026 window the queue data is meant to cover,
very nearly closing the gap. Note even upstream's 2023 grid still counts 2024's
~5.0 GW of prescriptions against a 2026 ceiling, which is a small residual
inconsistency upstream carries too.

Either way it is safe for the two-step workflow: `make_tg_cap.py` defaults to
`--from-year 2026` and `Sw_CEPM_TgCapStartYear` defaults to 2026, so an early
solve year is excluded from both the harvested ceiling and the constraint that
enforces it — no change to the RE-ceiling results.

Cost: one extra solve year of runtime (~25-30 min).

**Untested.** The mechanism and the arithmetic above are verified from the code
and from the run's own prescription files, but no run has been done with an added
early solve year. Worth a single baseline to confirm before adopting — check that
`cap_above_limit.csv` shrinks as predicted and that 2026's `cap_new_out` drops to
genuinely-2026 commitments.

#### 5.3e What no solve-year choice fixes

A solve year narrows the mismatch; it does not remove it. Three things remain,
and they are worth knowing before treating §5.3d as a fix rather than a
mitigation.

**A 2023 solve year still puts three calendar years into one column.** The 2026
solve would carry 2024, 2025 *and* 2026 prescriptions. **Upstream has exactly the
same window** — its default grid puts the prior solve year at 2023, so its 2026
solve also absorbs 2024-2026. Restoring upstream's cadence therefore cures the
*16-year* pathology and inherits upstream's own *3-year* one. A 2024 solve year
narrows it to two years (2025-2026), which is the tightest alignment available
without changing the equation, because `interconnection_start = 2025`.

**The ceiling side is a ramp allocation, not a near-term physical limit.** The
queue file's values rise in **equal annual increments** to 2030 rather than
stepping up in a project's online year — e.g. `p01001 battery`: 0, 0, 26.7,
53.3, 80.0, and nationally the increments are exactly 170,221 / 170,221 /
569,935 / 569,935 / 569,935. That is the signature of each project's MW being
spread linearly across a window ending in 2030. (Inferred from the data shape,
not documented — see §2.1, and treat the *reason* for the ramp as unconfirmed
even though the shape itself is unambiguous.) The consequence is that the early
columns are small by construction:

| | 2026 column | full queue (2030) | 2026 share |
|---|---:|---:|---:|
| WECC-SW (`cap_limit`) | 11,794 MW | 121,276 MW | **9.7%** |
| national (source file) | 170,221 MW | 2,050,246 MW | **8.3%** |

So "the 2026 ceiling" is not "what can interconnect by 2026" — it is roughly a
tenth of the queue, allocated by a smoothing rule. Any build window, however well
aligned, is being measured against a systematically low number in the early
years. This is also why the near-balance quoted in §5.3d for a 2024 solve year
(~12,810 MW against 11,794 MW) should not be read as "correct" — it is two
loosely-related quantities happening to land close.

**Most fundamentally, prescribed builds may not belong in this constraint at
all.** Prescribed builds are projects that are already committed or under
construction; an interconnection queue describes projects *waiting* to
interconnect. If the committed projects have already secured interconnection —
which is normally why they are committed — then charging them against queue
headroom double-counts, and consumes ceiling that should be available to
genuinely endogenous builds. ReEDS cannot currently distinguish the two: both
arrive as `INV`, and `eq_interconnection_queues` sums all of it.

That last point is not fixable by any `yearset`. It would need the equation to
net prescribed capacity out of its right-hand side, or the queue data to exclude
already-committed projects. Which of those is right depends on what the queue
snapshot actually contains — **which we cannot currently answer** (§2.1), and is
the strongest argument for doing §5.2 before any of this.

### 5.4 Align `interconnection_start` with the prescription window

`interconnection_start = 2025` means builds from 2025 onward count against the
queue. Since the 2026 solve is really executing 2011-2026 commitments, we are
charging a 2026 ceiling for sixteen years of work. Options:

- Leave `interconnection_start` alone and accept the penalty as a constant
  (§5.1). Simplest, and honest as long as it is documented.
- Advance `interconnection_start` past 2026 so the constraint governs only
  genuinely-endogenous builds (2029+). This makes the queue mean "what can
  interconnect *beyond* what is already committed", which is arguably what we
  want it to mean, and it removes ~$227bn of noise from 2026. It also silences
  the `p59` signal in §4.4, so do §5.2 first.

### 5.5 Reconsider the 2032 blind spot

Per §2.3, the queue constraint **does not exist in 2032** in any CEPM run,
because the data stops at 2030. So the final year — the one we report from — has
no interconnection limit at all, while 2026 and 2029 are penalized heavily. That
is an inconsistent treatment across the horizon, and it flatters 2032 buildout.
Either extend the queue data past 2030, or state plainly that 2032 buildout is
interconnection-unconstrained.

### 5.6 Measuring the penalty's effect directly: `GSw_CapPenaltyMult`

Everything above reasons about the penalty from the code and from output
arithmetic. `GSw_CapPenaltyMult` (added 2026-09-03) makes it measurable instead:
it scales `cap_penalty` right after the load in `b_inputs.gms`, and defaults to
**1**, so it is inert unless deliberately set.

Setting it to ~0 removes the interconnection queue's influence on the optimizer
**entirely** — which is worth stating precisely, because it is easy to assume a
switch like this only removes a cost. `CAP_ABOVE_LIM` is a slack variable with
**no upper bound** that appears in exactly one constraint
(`eq_interconnection_queues`) and in the objective, and nowhere else in the
model. Zero the penalty and the slack absorbs any violation for free, so the
constraint is non-binding and `INV` is unaffected by it. Both halves of the
penalty's behavioral effect go with it:

- the portion levied on **prescribed** capacity — a constant, since
  `eq_forceprescription` pins `INV`, so it never had a gradient; and
- the per-MW **surcharge on marginal builds** in cells already over their limit,
  which does have a gradient and is the channel most likely to have moved
  results.

**Use a small epsilon, not exactly 0.** At exactly 0 the optimizer has no
incentive to minimize `CAP_ABOVE_LIM`, so it can settle anywhere at or above the
true violation — and `5_varfix.gms:29` then fixes that arbitrary value for every
later solve year, making `cap_above_limit.csv` useless as a record of what the
exceedance was. `0.000001` (→ $10/MW) pins it to the true violation while
contributing a few parts per million of the objective.

```
GSw_CapPenaltyMult = 0.000001    # queue constraint effectively off
GSw_CapPenaltyMult = 1           # default; shipped $10M/MW
```

An intermediate value (say 0.1) adds little: the prescribed portion is
price-insensitive by construction, and for the voluntary portion the informative
direction is *upward* — the model already paid $10M/MW for the `p59` gas in
§4.4, so lowering the price only makes a build it already chose cheaper. If you
want to know what interconnection headroom in `p59` is actually worth, raise the
multiplier until the build stops.

### 5.7 Sanity-check the prescriptions themselves against 2026 reality

The prescriptions come from `ReEDS_generator_database_final_EIA-NEMS.csv` via
`writecapdat.py`. For a 2026-anchored study, the question worth asking is
whether the projects prescribed for 2011-2026 have *actually* been built. Any
that were cancelled are being forced into the model as a floor, and are then
charged a queue penalty on top. Checking the 2024-2026 tail of the prescription
list against reality is a bounded task and directly serves the "grounded in
actual 2026" goal.

---

## 6. Quick reference

### Files

| Path | Role |
|---|---|
| `inputs/capacity_exogenous/interconnection_queues.csv` | queue source, county × tg × 2026-2030 |
| `inputs/financials/cap_penalty.csv` | $10M/MW, uniform across all 13 tech groups |
| `inputs/capacity_exogenous/ReEDS_generator_database_final_EIA-NEMS.csv` | unit database behind non-RSC prescriptions |
| `inputs/capacity_exogenous/prescribed_builds_wind-{ons,ofs}_*.csv` | wind prescriptions by siting scenario |
| `inputs/capacity_exogenous/exog_cap_{upv,wind-ons,geohydro}_*.csv` | exogenous RSC capacity |
| `<run>/inputs_case/cap_limit.csv` | aggregated queue ceiling actually used |
| `<run>/inputs_case/prescribed_{nonRSC,rsc}.csv` | prescriptions actually used |
| `<run>/outputs/cap_above_limit.csv` | `CAP_ABOVE_LIM.l` — the violations |

### Code

| Location | What |
|---|---|
| `copy_files.py:1403-1433` | builds `cap_limit.csv`; no switch |
| `writecapdat.py:338-345` | builds `prescribed_nonRSC.csv` from `unitdata.csv` |
| `c_model.gms:1389` | `eq_interconnection_queues` |
| `c_model.gms:30` | `CAP_ABOVE_LIM` declaration |
| `d_objective.gms:47` | the $10M/MW penalty term |
| `c_model.gms:922` | `eq_forceprescription_power` |
| `c_model.gms:35` | `EXTRA_PRESCRIP` — free slack, never costed |
| `b_inputs.gms:1985-1991` | `noncumulative_prescriptions` — the 16-year pile-up |
| `b_inputs.gms:1943-1951` | `m_required_prescriptions` |
| `b_inputs.gms:909-922` | `prescriptivelink` |
| `b_inputs.gms:5938-5941` | `force_pcat` |
| `b_inputs.gms:2024` | `cap_penalty` load, never rescaled |
| `report.gms:129` | `cap_above_limit` reporting |
| `report.gms:1745` | the only place the penalty enters reporting (an error check) |

### Switches and scalars

| Name | Where | Default | Effect |
|---|---|---|---|
| *(none)* | — | — | **nothing switches the queue constraint on or off** |
| `interconnection_start` | `scalars.csv:52` | 2025 | first year whose builds count against the queue |
| `model_builds_start_yr` | derived, `b_inputs.gms:1248` | — | earliest year the queue equation is generated |
| `GSw_ForcePrescription` | `cases.csv` | 1 | prescriptions as a floor |
| `unitdata` | `cases.csv` | `EIA-NEMS` | selects the unit database |
| `GSw_SitingWindOns` / `GSw_SitingWindOfs` | `cases.csv` | `reference` | selects wind prescription files |
| `startyear` / `yearset` | `cases.csv` / `cases_cepm.csv` | 2010 / `2026..2032..3` | together set the 16-year prescription window |
| `Sw_PCM` | | 0 | disables both equations |

### Related docs

- [`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) — F4 (why the
  queue cap was not reused for the RE ceiling), F5 (prescribed builds as a hard
  floor under any ceiling), and the `cepm_tg_cap` mechanism built instead.
- [`tech-limit-options.md`](tech-limit-options.md) — the menu of capacity-limiting
  mechanisms, of which the queue cap is Option 2.
- [`reeds-data-sources.md`](reeds-data-sources.md) — how a switch value becomes an
  input file path.

# Keeping `GSw_CEPM_TgCap` feasible at prescribed builds: "built + owed" accounting
Written Date: 2026-10-19

**Scope:** why a cumulative tech-group cap (`GSw_CEPM_TgCap`) can make a capped
run infeasible when it meets a prescribed build, and the change to the cap's
accounting that prevents it. Read
[`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) first for what the
caps are and how `run_cepm.ps1 -m` harvests them.

**Short version:**

- A prescription in ReEDS is a cumulative minimum *per region*. Capacity built
  early in a region counts toward that region's later prescriptions. Capacity
  built in another region doesn't.
- ReEDS solves one year at a time. A capped run can spend its budget in one
  region, then be forced in a later year to build a prescription in another
  region that no longer fits under the cap. The cap has no slack, so that solve
  is infeasible.
- **"Built + owed"** (implemented, no switch): in each solve year, each cap at a
  later year must hold the run's builds so far *plus* the prescriptions due by
  then that those builds don't cover. Prescriptions are fixed inputs, so this
  needs no foresight. The cap is still exactly the baseline's system path.
- In the runs checked so far it doesn't bind. AZNM has no prescriptions after
  2026, and Virginia's (offshore wind and PV in `p99`) were covered in both
  `VA_baseline` and `VA_limitre`. It's a guarantee for cases where it would.
  **It hasn't been tested in a solve yet.**

---

## 1. The problem

### How prescriptions work

`eq_forceprescription_power(pcat,r,t)` ([`c_model.gms`](../../reeds/core/setup/c_model.gms),
"Prescribe power capacity") requires, for each prescription category and
region:

> cumulative builds of the category's techs in `r` through `t` = cumulative
> prescriptions in `r` through `t` + `EXTRA_PRESCRIP(pcat,r,t)`

`EXTRA_PRESCRIP` is free and non-negative once the category's first year has
passed, so in effect **cumulative builds ≥ cumulative prescriptions, region by
region**. Everything already built in `r`, including historical builds, counts
toward `r`'s later prescriptions. Nothing built elsewhere does.

### How that breaks a cumulative cap

One tech group, two regions. Region B has an 800 MW prescription due by 2029.

| | 2026 | 2029 |
|---|---|---|
| **Baseline** | builds 1,000 MW in B (which already covers B's 2029 prescription) | builds nothing more |
| Harvested system cap (cumulative) | 1,000 | 1,000 |
| **Capped run** | builds its 1,000 MW in A, which is cheaper with its higher load | is forced to build 800 MW in B: 1,800 against 1,000, so the solve is **infeasible** |

This can happen under both the horizon-total cap (`GSw_CEPM_TgCap=1`) and the
per-year path (`=2`), which has more years in which it can happen.

### What doesn't fix it

| Approach | Why not |
|---|---|
| `--scope region` | Regions where the baseline built nothing get no cap at all, because GAMS reads a missing value as "no cap". It also pins RE to the baseline's locations. |
| Net prescriptions out of the cap | The discretionary path has to be made non-decreasing, which loosens the cap by up to what the baseline built ahead of its prescriptions. |
| `--headroom` > 1 | Loosens every cap to buy slack in the few places that need it. |
| A soft cap (a priced slack in the objective) | Considered and dropped. Each year is solved on its own, so the 2026 solve never sees a 2029 penalty and the penalty can't change the decision that causes the problem. In practice it would only turn the 2029 infeasibility into a forced, reported exceedance. |

Any rule that only looks at what has been built so far has to pick, in the
example, between infeasibility and allowing 1,800 MW. The fix is to look at
what the run is already committed to build.

---

## 2. The rule

In each solve year `t` from `GSw_CEPM_TgCapStartYear` on, for each capped tech
group and each later modeled year `t′` with a cap in force:

> new investment through `t` + Σ over regions of (prescriptions due by `t′` that
> builds through `t` don't cover) ≤ cap(`t′`)

"Don't cover" is `max(0, prescriptions in r through t′ − builds in r through t)`,
with builds counted exactly as in `eq_forceprescription_power`. The cap at `t′`
is the per-year path under `=2`, or the horizon total at the last modeled year.
The existing current-year equations still handle `t′ = t`.

### The example again

| Capped run's 2026 choice | built | owed (B's 800 MW, uncovered) | built + owed vs. 1,000 |
|---|---:|---:|---|
| 1,000 MW in A | 1,000 | 800 | 1,800: **not allowed** |
| 1,000 MW in B | 1,000 | 0 | 1,000: allowed |
| 200 MW in A, nothing in B | 200 | 800 | 1,000: allowed, with 800 held back |

In 2029 the 800 MW in B always fits, and cumulative builds never go above the
baseline's 1,000 MW.

### Why it can't go infeasible because of a prescription

1. **The baseline satisfies it.** The baseline met every prescription within its
   own cumulative path, so its builds plus what was still owed always fit under
   its later totals. This is checked on real runs in section 3.
2. **It stays satisfiable from year to year.** If the rule held after `t−1`, the
   run can build exactly the prescriptions newly due in `t`. That moves the same
   MW from "owed" to "built", leaving built + owed unchanged, so every later cap
   still holds. The current-year cap holds too, since what was owed for `t` was
   already counted within it.
3. **So a prescription can't force the cap over** at `--headroom` ≥ 1, at either
   scope. At headroom below 1, a cap can still be below the prescriptions, as it
   can today, and that would now show up as an infeasible solve in the first
   capped year instead of later.

### What it changes in a run

- **Nothing is loosened.** The cap is still exactly the baseline's path.
- **Early builds are constrained.** The run can't spend, now, budget that a
  later prescription will need, unless it spends it where that prescription is.
  In plain words: *"no more RE than the baseline by year t, counting projects
  already in the pipeline."*
- If no prescriptions are uncovered, the new equations aren't generated, or they
  add nothing. That was the case in every run checked (section 3).

---

## 3. Checked against finished runs

Before writing the equations, the rule was evaluated on finished runs: restart
from each run's last saved state, rebuild built + owed from its own builds
(`INV.l`) and its own prescriptions, and compare with a cap path. Owed values
are MW_ac.

| Run | Prescriptions still owed after a capped solve year | Result |
|---|---|---|
| `v20261009precapex_st-AZNM_baseline` | None. Every prescription from 2026 on is due in 2026 (PV 11,818 MW_ac, battery 7,888.6, wind 8,035.7). | Rule holds everywhere. Inactive. |
| `v20261009precapex_st-AZNM_limitre` | None | Inactive |
| `v20260925_VA_baseline` | 95 MW_ac of PV (127 MW_dc) and 53 MW of offshore wind in `p99`, due by 2029 | Rule holds with positive slack in every row |
| `v20260925_VA_limitre`, 2026 builds, horizon-total cap | 95 MW_ac of PV in `p99` | Holds: PV built + owed is 10,893 against 23,977. Wind-ons and wind-ofs are exactly at their totals, with nothing owed. |

**The Virginia 2029 infeasibility isn't a prescription overflow.** VA's one
large later prescription is 2,640 MW of offshore wind in `p99` in 2027 (CVOW,
from that run's `prescribed_builds_wind-ofs.csv`). `VA_limitre` covered it with
its 2026 offshore builds. This agrees with the "not a prescribed-build
collision" finding in [`known-reeds-issues.md`](../known-reeds-issues.md). What
would have constrained VA is the per-year path (`=2`): `VA_limitre`'s 2026
wind-ons was 11,866 MW against a 2026 path value of 78.

---

## 4. Implementation

No switch. It applies whenever `GSw_CEPM_TgCap` is 1 or 2, because it only
enforces what the cap already means.

### `reeds/core/setup/b_inputs.gms` (after the per-year guardrails)

| Symbol | What |
|---|---|
| `cepm_tg_capped(tg)` | Tech groups with any cap loaded |
| `cepm_tg_pcat(tg,pcat)` | Prescription categories whose buildable techs (`valcap_i`) are in a capped group, through `prescriptivelink` and `tg_i` |
| `cepm_pcat_ilr(pcat)` | `ilr` of the category's buildable techs. Prescriptions are in `INV` units (MW_dc for UPV); the caps are MW_ac. |
| `cepm_presc_cum(pcat,r,t)` | Cumulative `noncumulative_prescriptions` through `t`, the right-hand side of `eq_forceprescription_power` |
| `cepm_tg_cap_sys_at(tg,t)`, `cepm_tg_cap_reg_at(tg,r,t)` | The cap in force at `t`: the per-year path under `=2`, plus the horizon total at the last modeled year |
| Two `abort`s | A category in two capped groups (it would be double-counted), or a category mixing `ilr` values (MW_ac would be ambiguous) |

The block is wrapped in `$onImplicitAssign`, because whichever cap files a run
doesn't use are legitimately empty. The filter to buildable techs matters:
without it, techs that can't be built have `ilr = 0` and the conversion divides
by zero.

### `reeds/core/setup/c_model.gms`

| Symbol | What |
|---|---|
| `CEPM_TGCAP_OWED(pcat,r,t,tt)` | Positive variable: prescriptions due by `tt` not covered by builds through `t` |
| `eq_cepm_tgcap_owed(pcat,r,t,tt)` | `OWED ≥ cumulative prescriptions through tt − the category's builds in r through t` |
| `eq_cepm_tg_cap_sys_owed(tg,t,tt)` | `cap_at(tt) ≥ new investment through t + Σ_(pcat,r) OWED / ilr` |
| `eq_cepm_tg_cap_reg_owed(tg,r,t,tt)` | The same for a region, counting only that region's owed prescriptions |

All three are generated only for solve years from `Sw_CEPM_TgCapStartYear` on,
for later modeled years `tt` with a cap in force, and only where the group has
prescriptions due by `tt`. The start-year limit is essential. From the 2010
solve, every historical prescription from 2011–2025 would count as owed against
a cap that only counts investment from 2026, and the run would be infeasible
straight away. `OWED` has no cost and is non-negative, so it settles at
`max(0, …)`.

"New investment through `t`" uses the same terms as the existing cap equations:
`INV`, `INV_REFURB`, and upgrades, each divided by `ilr`.

### Not added

- **Reporting.** The owed amounts aren't written to `outputs/`. If they're
  needed, add `cepm_tgcap_owed_out(pcat,r,t,tt) = CEPM_TGCAP_OWED.l(...)` to
  `report.gms` and a row to `report_params.csv`. The name needs a suffix such as
  `_out`, because GAMS names aren't case-sensitive and `cepm_tgcap_owed` would
  clash with the variable.
- **Energy prescriptions** (`eq_forceprescription_energy`, MWh for batteries).
  The caps are in MW, so only power prescriptions matter.

---

## 5. Tested, and not yet tested

**Model setup (`a_createmodel.gms`), GAMS 44.4.0:**

- AZNM (a copy of `v20261009precapex_st-AZNM_limitre`'s inputs): `=2` with
  system-scope and region-scope harvests, `=1`, and `=0` all completed normally.
  The data matched the evaluation in section 3: PV maps to `UPV` with ilr 1.34,
  and battery, wind-ons and pumped hydro each map to one category with ilr 1.0.
  The cap in force follows the path under `=2` and is only the 2032 total under
  `=1`. The region-scope run loaded 42 regional values, and `=0` loaded nothing.
- Virginia (a copy of `v20260925_VA_limitre`'s inputs, with a system-scope
  per-year path harvested from `VA_baseline`): `=2` and `=1` completed normally,
  with wind-ofs also mapped. The only prescriptions that grow after 2026 are
  wind-ofs in `p99` (12 MW through 2026, then 2,652 by 2029) and UPV in `p99`
  (7,632 to 7,760 MW_dc).

**Not yet tested: a solve.** Setup doesn't generate equations, so these haven't
been exercised yet: equation generation (domains, the `/ ilr` division), the
start-year limit, and the claim that the new equations don't change a run where
nothing is owed. The tests, in order:

1. **No-change check:** rerun an AZNM `-m` batch. Nothing is owed there, so
   results should match the previous batch with the same switches.
2. **Generation check:** a VA `_limitre` under `=2`. Look in the 2026 `.lst` for
   rows of `eq_cepm_tg_cap_sys_owed` (UPV and wind-ofs in `p99` should generate
   them) and confirm the solve is feasible.
3. **A case where it binds:** a `_limitre` under `--scope system` whose baseline
   built ahead of a later prescription in one region, then built elsewhere.
   Without built + owed it should be infeasible in the prescription's year; with
   it, feasible.

## 6. Open questions

- **The state offshore-wind requirement.** `EXTRA_PRESCRIP` also absorbs
  `offshore_cap_req`, which isn't in `noncumulative_prescriptions`, so it isn't
  counted as owed. A capped run under a binding offshore requirement could still
  be forced over the cap. Whether any CEPM case has a binding offshore
  requirement hasn't been checked.
- **The regional leak** under `--scope region` / `both`. Built + owed makes it
  safe to fix in `make_tg_cap.py` by writing the zero floor for every (tech
  group, region) with no baseline builds: a region with a prescription always
  has baseline builds, so no forced build meets a near-zero cap.
- **Headroom below 1.** A cap below the prescriptions now makes the first capped
  year infeasible rather than a later one. `make_tg_cap.py`'s first-year floor
  warning doesn't cover later years' prescriptions. Extending that warning would
  catch it before the run starts.

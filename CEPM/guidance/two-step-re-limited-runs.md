# Two-step baseline-constrained runs (`*_baseline` → `*_limitre` + `*_optimized`)

**Status (2026-09-02):** **the workflow is built and works end to end.** One
command now produces the three-case factorial and its comparison deck:

```powershell
.\run_cepm.ps1 -y -x -b <batch> -c cepm -m WECC-SW
```

Working branch `mvp/two-step-runs`, everything still in the working tree
(nothing committed).

- Done: the GAMS equations, parameters and guardrails (§4); the `cases.csv` /
  `runfiles.csv` plumbing (§5.1); `make_tg_cap.py` (§5.3); the three
  `cases_cepm.csv` case columns for **both `WECC-SW` and `SERTP`**;
  `run_cepm.ps1 -m` plus `CEPM/scripts/multistep_cases.py` (§5.4); and tests
  **T0 through T9, all of them**.
- The headline result (T9): holding wind/solar/storage at the no-data-center
  baseline forces **+13.3 GW of gas and +2.2 GW of h2** in place of 21 GW of
  foregone PV and 2 GW of wind, at a **+33.4%** 2032 objective.
- Not done: the rebase + **T10**. Docs are complete (§9 step 6) and the
  pre-commit housekeeping is resolved (§9).
- One partial: **T5(d)** proves the zero-vs-floor mechanism decisively at the
  equation level, but its solution-level half could not be exercised — neither
  WECC-SW nor SERTP has economics that would build any of the three zero-build
  groups even when starved (§7).
- Sections §4, §5.1 and §5.4 have been corrected to match what was actually
  built; where the built thing differs from the original proposal, the reason is
  recorded inline rather than the proposal being quietly overwritten (see also
  D8).

**Scope:** a `run_cepm.ps1` mode that runs a CEPM case in two phases — first a
`*_baseline` ReEDS run, then a pair of data-center-load runs where one
(`*_limitre`) is capped at the baseline's own wind/solar/storage buildout and
the other (`*_optimized`) is free — including the ReEDS-side plumbing needed to
inject a per-batch capacity ceiling, the tests that prove it works, and what to
re-check when we rebase onto upstream `2026.08.03`.

**Short version:** the orchestration half is easy — `runreeds.py` already
accepts a comma-delimited case list and blocks until the batch finishes, so
"run A, harvest A, run B and C" is three shell steps. The hard half is the
ceiling itself. `GSw_GrowthAbsCon` (Option 3 in
[`tech-limit-options.md`](tech-limit-options.md)) cannot express what we want
here, for three independent reasons documented below, each verified against
this repo's code and against a completed WECC-SW baseline run. What was built
instead is a pair of purpose-built cumulative-cap equations modeled line-for-line
on `eq_interconnection_queues` — additive GAMS, no upstream lines edited, and
written in the same units as the reported outputs so the harvest script needs no
unit conversion at all.

The "orchestration half is easy" claim above held up, but not quite as written:
`runreeds.py` returns exit code 0 on a failed case and prompts interactively when
given more than one, so both phases needed guarding rather than just sequencing
(§5.4 "As built").

**Decisions (all closed):** D1 purpose-built equations, closed by T0 (§6);
D2 both scopes, switchable (§4); D3 cumulative gross builds from 2026 (§6);
D4 wide group list — `pv`, `wind-ons`, `wind-ofs`, `csp`, `battery`,
`pumped-hydro` — at 100% (§5.3); D5 generated cases file (§5.2b); D6 hard cap,
no slack; D7 `INV + INV_REFURB + UPGRADES − UPGRADES_RETIRE`; D8 non-region
`runfiles.csv` rows (§5.1). §4a records the path not taken.

---

## 1. What we're building

Given a CEPM case stem (say `WECC-SW`), three case columns in `cases_cepm.csv`:

| Case | Data-center load | RE ceiling | Purpose |
|---|---|---|---|
| `WECC-SW_baseline` | off | none | counterfactual; source of the ceiling |
| `WECC-SW_limitre` | on | wind/solar/storage capped at baseline buildout | "what if new load can't lean on new RE" |
| `WECC-SW_optimized` | on | none | "what the optimizer would actually do" |

`WECC-SW_limitre` and `WECC-SW_optimized` differ **only** in the ceiling, and
`WECC-SW_optimized` differs from `WECC-SW_baseline` **only** in the load. That
clean factorial is the whole point, and it constrains several decisions below —
in particular it rules out reusing any mechanism that is already active in the
baseline (see F4).

---

## 2. Orchestration shape

`runreeds.py` gives us everything we need:

- `--single/-s` takes a **comma-delimited list** of case names and overrides the
  `ignore` row for exactly those cases (`runreeds.py:81-95`, `909-918`,
  `1831-1832`).
- On Windows a case is launched with `os.system('start /wait cmd /c ...')`
  (`runreeds.py:1728`), and the worker pool joins, so `runreeds.py` **blocks
  until the whole batch finishes**. `run_cepm.ps1` already relies on this
  (`Invoke-Native { uv run python runreeds.py @ForwardArgs }`), so sequencing
  two invocations needs no new waiting logic.
- Run folders are `runs/{BatchName}_{case}`, so both phases can share one batch
  name and `compare_cases.py "runs/{BatchName}_"` picks up all three cases.

So the flow is:

```
Phase A   runreeds.py -b BATCH -c cepm -s WECC-SW_baseline -r 1
          └── blocks until runs/BATCH_WECC-SW_baseline/outputs/outputs.h5 exists
Harvest   CEPM/scripts/make_tg_cap.py  (reads phase A outputs → writes cap CSV)
Phase B   runreeds.py -b BATCH -c <generated> -s WECC-SW_limitre,WECC-SW_optimized -r 2
          └── blocks until both finish
Compare   postprocessing/compare_cases.py "runs/BATCH_"      (existing -x path)
Cleanup   delete the generated cap CSV + generated cases file (always, in finally)
```

Phase A must hard-fail the whole invocation if `outputs.h5` is missing — a
ceiling harvested from a partial run is worse than no run at all.

**Two corrections from building it** (§5.4 "As built" has the detail). Phase A
needs no `-r`: one case short-circuits `runreeds.py` to `WORKERS=1`. Phase B
*does* need `--simult_runs 2`, because two cases with no worker count makes
`runreeds.py` prompt interactively and hang a background run.

---

## 3. Four findings that shape the design

Each of these was checked against the code in this fork and, where possible,
against `runs/v20260824-2_WECC-SW_baseline`.

### F1 — `eq_growthlimit_absolute` goes **infeasible** in the final solve year

The equation's allowance is the gap to the *next* modeled year
(`c_model.gms:1088-1102`):

```gams
     (sum{tt$[tprev(tt,t)], yeart(tt) } - yeart(t)) * growth_limit_absolute(tg)
     =g=
     sum{(i,v,r)$[valinv(i,v,r,t)$tg_i(tg,i)], INV(i,v,r,t) }
```

`tprev(t,tt)` means "tt is the year before t" (`b_inputs.gms:1027`,
`1053-1055`), so `tprev(tt,t)` selects the year *after* `t`. For the last
modeled year no such `tt` exists, the sum collapses to 0, and the left-hand side
becomes `-yeart(t) * growth_limit_absolute(tg)` — a large negative number
required to be `=g=` a non-negative sum of `INV`. That is infeasible, not
merely restrictive, and there is no slack variable.

`yearweight` uses the identical expression (`b_inputs.gms:5573`) and then
explicitly patches the last year (`b_inputs.gms:5574`);
`eq_growthlimit_absolute` has no such patch. The bug is latent upstream only
because `GSw_GrowthConLastYear` defaults to 2026 while runs end in 2050, so the
equation is never generated in the final year.

CEPM cases end at 2032 with solve years 2010/2026/2029/2032 (`cases_cepm.csv:5-7`,
`copy_files.py:1301-1311`). Setting `GSw_GrowthConLastYear=2032` — exactly what
[`tech-limit-options.md`](tech-limit-options.md) currently recommends for CEPM —
puts the equation in the final year.

**Confirmed (T0, part 1 — standalone GAMS reproduction, 2026-09-01).** A 40-line
GAMS file replicating `b_inputs.gms:1049-1055` verbatim over a CEPM solve-year
set, then generating the equation, reproduces it exactly. The year-gap
coefficient (`c_model.gms:1094`) comes out:

| solve year | 2010 | 2026 | 2029 | 2032 |
|---|---:|---:|---:|---:|
| `eq_growthlimit_absolute` gap | 16 | 3 | 3 | **−2032** |
| `yearweight` gap (same expression, last year patched) | 16 | 3 | 3 | 2051 |

and the generated row for the final year, using the shipped `pv` limit of
28,582 MW/yr, is:

```
eq_growthlimit_absolute(2032)..  - INV(2032) =G= 58078624 ; (LHS = 0, INFES = 58078624 ****)
```

i.e. `INV(2032) ≤ −58,078,624 MW` against `INV ≥ 0`. CPLEX reports
`Bound infeasibility column 'INV(2032)'`, GAMS model status 4 (Infeasible).
Not restrictive — infeasible, exactly as the sign analysis predicted, and the
side-by-side with `yearweight` shows this is a missing `tlast` patch rather than
an intentional convention.

**Confirmed (T0, part 2 — live ReEDS run, 2026-09-01).**
`runs/v20260901t0_WECC-SW_t0growthcon` — `WECC-SW_baseline`'s exact
configuration plus `GSw_GrowthAbsCon=1` and `GSw_GrowthConLastYear=2032`:

| solve year | model status |
|---|---|
| 2026 | 1 Optimal |
| 2029 | 1 Optimal |
| 2032 | **4 Infeasible** |

CPLEX's conflict refiner isolated it to a single row — no ambiguity about the
cause:

```
Row 'eq_growthlimit_absolute(PV,2032)' infeasible, all entries at implied bounds.
Number of equations in conflict: 1
  lower: eq_growthlimit_absolute(PV,2032) > 5.80786e+07
Number of variables in conflict: 8
  lower: INV(upv_4,new15,p29,2032) > 0
  ...
```

`5.80786e+07` matches part 1's predicted 58,078,624 exactly.
`3_solve_oneyear.gms` then aborts with *"Model did not solve to optimality"*
(return code 3), the run stops after 2029, and no `outputs.h5` is produced.

The non-final years solving cleanly is the important half of this result: the
constraint is well-behaved everywhere except the last modeled year, which is
precisely the signature of the missing `tlast` patch rather than of a badly-sized
limit.

**D1 is therefore closed in favor of §4.** `tech-limit-options.md`'s CEPM
recommendation section — which recommends exactly the configuration tested here
— needs correcting, and this warrants an entry in `CEPM/known-reeds-issues.md`.

### F2 — `growth_limit_absolute(tg)` has no year index, and CEPM baselines are extremely lumpy

The parameter is `growth_limit_absolute(tg)` — one MW/year number per tech
group, no `t` (`b_inputs.gms:4804-4810`). The constraint is therefore a
**constant annual pace**, and the only way to hit a cumulative target is to
divide the target by the horizon.

Actual gross new capacity from `runs/v20260824-2_WECC-SW_baseline`
(`outputs/cap_new_out.csv`, MW_ac):

| tech group | 2010 | 2026 | 2029 | 2032 |
|---|---:|---:|---:|---:|
| pv (upv) | 35 | 11,423 | 7,258 | 1,500 |
| wind-ons | 168 | 6,708 | 200 | 9,531 |
| battery | 0 | 7,853 | 200 | 530 |

Wind builds 200 MW in 2029 and 9,531 MW in 2032. A flat annual cap sized to the
2029+2032 total (9,731 MW over six years ≈ 1,622 MW/yr → 4,866 MW allowed per
solve year) would **cap the `_limitre` case below the baseline's own path**. The
ceiling would bind in a scenario that is supposed to be able to reproduce the
baseline exactly — the constraint would be measuring our discretization, not the
policy question. This is not a tuning problem; a time-invariant rate cannot
express a lumpy cumulative target.

### F3 — Reported capacity is MW_ac; `INV` is MW_dc

Every reported capacity quantity is divided by the inverter loading ratio:
`cap_new_out = INV / ilr(i)` (`report.gms:820-825`), and `ilr(i) = ilr_utility
= 1.34` for UPV (`b_inputs.gms:3756-3762`, `inputs/scalars.csv:50`). PVB gets
its own ILR (`b_inputs.gms:3763`). Wind and battery are 1.0.

So any ceiling written against `INV` must be in MW_dc, and a harvest script that
reads `cap_new_out` and writes the number straight through would under-cap solar
by 34%. Two ways out; the second is strictly better and is why writing our own
equation pays for itself:

1. multiply harvested PV by `ilr_utility` in the harvest script (fragile — the
   CSV then means something different from every plot and output table); or
2. **write the equation in MW_ac**, dividing `INV` by `ilr(i)` inside the sum.
   Then the cap CSV, `cap_new_out`, and every comparison plot are all in the
   same units, and the harvest script does no conversion at all.

### F4 — The interconnection-queue cap is already active *and already violated* — don't reuse it

Option 2 in `tech-limit-options.md` (`cap_limit.csv` /
`eq_interconnection_queues`) is genuinely cumulative and has no last-year
problem, so it looks like the natural home for this. It is not, for two reasons.

First, it is already binding in CEPM baselines.
`runs/v20260824-2_WECC-SW_baseline/outputs/cap_above_limit.csv` has 20 non-zero
rows — PV in `z28` exceeds its queue limit by ~5.0 GW in 2026, wind in `p31` by
~5.2 GW, gas in `p59` by ~2.0 GW. These are mostly prescribed 2026 builds that
the queue data (aggregated to CEPM's zones) cannot accommodate, absorbed by the
penalized slack `CAP_ABOVE_LIM` (`c_model.gms:1385-1403`,
`d_objective.gms:47`). Overwriting `cap_limit.csv` with a policy ceiling would
therefore change a constraint that is *already doing work* in the baseline,
breaking the clean factorial in §1.

Second, `cap_limit.csv` is computed directly in `copy_files.py:1403-1417` from
`inputs/capacity_exogenous/interconnection_queues.csv` with no scenario switch,
so making it case-specific means editing `copy_files.py` — the single
most-churned file in the 2026.08.03 release (568 lines changed, see §8). That is
the worst possible place to put a fork hook.

Corollary, worth noting independently of this project: because the shipped queue
data only extends to 2030, `sum{(tgg,rr), cap_limit(tgg,rr,'2032')}` is zero and
the queue constraint **switches itself off entirely in 2032** in every CEPM run
today.

**Followed up in depth (2026-09-03) — see
[`interconnection-queue-and-prescribed-builds.md`](interconnection-queue-and-prescribed-builds.md).**
F4's "already doing work" is a considerable understatement. The violations are
priced at a flat **$10,000,000/MW**, recharged in every modeled year because the
constraint is cumulative, and they amount to **77% of the 2026 objective** and
65% of 2029's — while being excluded from reported `systemcost.csv` entirely.
The collision is structural: CEPM's 2026 solve absorbs **16 years** of
accumulated prescriptions (2011-2026, because the prior solve year is 2010) and
must place 33.0 GW against 11.8 GW of queue headroom. About 94.5% of the penalty
falls on prescribed capacity and so has no effect on the optimization, which is
why F4's conclusion still holds and why the T9 comparison in §7 is unaffected
(the 2032 objective carries no penalty at all). The remaining 5.5% is a live
signal and looks wrong — see that doc's §4.4 on gas in `p59`.

---

## 4. The mechanism as built: purpose-built cumulative caps, two scopes

Two equations modeled line-for-line on `eq_interconnection_queues`, which
already has exactly the right shape (cumulative over `tt`, guarded by
`tmodel(tt) or tfix(tt)` so it works in ReEDS' sequential solve). Per **D2**
both scopes exist and either can be left empty:

- `eq_cepm_tg_cap_sys(tg)` — one system-wide total per tech group.
- `eq_cepm_tg_cap_reg(tg,r)` — a per-region ceiling.

Two equations rather than one indexed table because `'all'` is not a member of
the set `r`, so a single `(tg,r)` parameter cannot carry a system-wide row
without abusing the region set. If both files are populated, both bind (total
≤ X *and* each region ≤ Y), which is a sensible and documented semantic.

**c_model.gms** — two lines in the equation declaration block (near line 176)
and one block immediately after `eq_interconnection_queues` (line ~1403):

```gams
* --- declarations ---
 eq_cepm_tg_cap_sys(tg)     "--MW_ac-- CEPM: cumulative system-wide cap on new investment by tech group"
 eq_cepm_tg_cap_reg(tg,r)   "--MW_ac-- CEPM: cumulative regional cap on new investment by tech group"

* --- definitions ---
* CEPM: cumulative ceilings on new investment by technology group, in MW_ac to
* match reported cap_new_out. See CEPM/guidance/two-step-re-limited-runs.md.
eq_cepm_tg_cap_sys(tg)$[cepm_tg_cap_sys(tg)$Sw_CEPM_TgCap$(not Sw_PCM)]..

    cepm_tg_cap_sys(tg)

    =g=

    sum{(i,newv,r,tt)$[valinv(i,newv,r,tt)$tg_i(tg,i)
                       $(yeart(tt)>=Sw_CEPM_TgCapStartYear)
                       $(tmodel(tt) or tfix(tt))],
        [INV(i,newv,r,tt) + INV_REFURB(i,newv,r,tt)$[refurbtech(i)$Sw_Refurb]]
        / ilr(i) } ;

eq_cepm_tg_cap_reg(tg,r)$[cepm_tg_cap_reg(tg,r)$Sw_CEPM_TgCap$(not Sw_PCM)]..

    cepm_tg_cap_reg(tg,r)

    =g=

    sum{(i,newv,tt)$[valinv(i,newv,r,tt)$tg_i(tg,i)
                     $(yeart(tt)>=Sw_CEPM_TgCapStartYear)
                     $(tmodel(tt) or tfix(tt))],
        [INV(i,newv,r,tt) + INV_REFURB(i,newv,r,tt)$[refurbtech(i)$Sw_Refurb]]
        / ilr(i) } ;
```

**b_inputs.gms** — two additive blocks next to the existing growth limits
(line ~4810):

```gams
* CEPM: cumulative new-investment caps by tech group (empty file = no cap)
$onempty
parameter cepm_tg_cap_sys(tg) "--MW_ac-- CEPM cumulative system-wide cap on new investment by tech group"
/
$offlisting
$ondelim
$include inputs_case%ds%cepm_tg_cap_sys.csv
$offdelim
$onlisting
/ ;

parameter cepm_tg_cap_reg(tg,r) "--MW_ac-- CEPM cumulative regional cap on new investment by tech group"
/
$offlisting
$ondelim
$include inputs_case%ds%cepm_tg_cap_reg.csv
$offdelim
$onlisting
/ ;
$offempty
```

Note the regional symbol is a **`parameter` in list form, not a `table`** (this
draft originally proposed a `table`). Both CSVs are therefore long — `*tg,MW` and
`*tg,r,MW` — which keeps `make_tg_cap.py`'s two outputs structurally identical,
keeps a header-only file trivially valid under `$onempty`, and avoids a wide
`tg × r` matrix that would need every region as a column even where a group has
no cap. The leading `*` on the header line is what makes GAMS skip it inside the
`/ ... /` include; it also means the first column is literally named `*tg` to
anything reading the CSV with pandas, which matters in §5.1.

### The zero-value trap (created by D4's wider group list)

Both equations are guarded by the parameter value, so **a value of 0 means "no
cap", not "no builds"** — GAMS does not store zero-valued records, so an
explicit `0` in the CSV is indistinguishable from an absent row.

That is harmless for `pv`/`wind-ons`/`battery`, which always have baseline
builds. It is a live trap for `wind-ofs`, `csp`, and `pumped-hydro`, which
have **zero** baseline builds in WECC-SW and SERTP today: harvesting them
honestly yields `0`, which switches their ceiling off and leaves exactly the
leak D4 was chosen to close.

Mitigation: `make_tg_cap.py` writes a floor of `0.001` MW rather than `0` for
any requested group whose baseline buildout is zero, and says so in its stdout
summary. 0.001 MW is far below any meaningful build and far above the
zero-record threshold. Test T5(d) covers it. A genuine, permanent zero should
still use `bannew(i)` instead (see `tech-limit-options.md`).

### F5 — prescribed builds are a hard floor under any ceiling

Found the hard way: the first T4 attempt, at `--headroom 0.5`, died with a bare
"Model did not solve to optimality" ~25 minutes in. CPLEX's conflict refiner
named it exactly:

```
fixed: eq_forceprescription_power(battery_li,z28,2026) = 6406.2
lower: eq_cepm_tg_cap_sys(BATTERY) > -4291.51
```

z28 has 6,406 MW of already-committed battery forced by `eq_forceprescription`
as an **equality**. Our cap has no slack (D6), so a ceiling below that is
infeasible — not tight, infeasible.

**The floor is computable from the reference run alone.** Builds in the first
covered solve year are effectively all prescribed, and this checks out exactly
two independent ways: reconstructing from the prescribed input files gives
battery 7,852.6 MW and pv 11,423.3 MW; summing `cap_new_out` for t=2026 gives
7,852.6 and 11,423.3. So `make_tg_cap.py` computes it directly from
`cap_new_out` — no fragile input-file parsing, no `prescribed_rsc` MW_dc-vs-MW_ac
trap (that file is MW_dc for PV), and no double-counting of wind (which appears
in both `prescribed_rsc.csv` and `prescribed_builds_wind-ons.csv`).

**Headroom 1.0 — the actual `_limitre` case — is safe by construction**, since
the cap equals the reference run's own builds, which already include the
prescriptions. This only bites below 1.0.

**Region scope needs `--clamp-to-floor` to go below 1.0 at all.** Six of the 15
regional cells in WECC-SW are *100% prescribed* (battery p27/p31, pv p29/p31,
wind-ons p27/z28), so a uniform regional headroom under 1.0 is infeasible no
matter how mild. `--clamp-to-floor` raises any cell back to its floor; it is
opt-in, because it means the effective ceiling is no longer a uniform fraction
of the reference run and silently changing that would be worse than failing.

Two mitigations now exist, and the warning fires at harvest time in seconds
rather than 25 minutes into a solve:

```
[make_tg_cap] *** WARNING: ceiling is below the 2026 prescribed-build floor for:
      battery              cap    4,291.505 < prescribed    7,852.600
      pv                   cap   10,090.590 < prescribed   11,423.324
[make_tg_cap] *** ... the run will very likely be INFEASIBLE in its first solve year.
```

### Guardrails in `b_inputs.gms`

Two `abort`s, both gated on `Sw_CEPM_TgCap` so they can never affect a run that
isn't using the caps:

1. **`ilr(i) = 0` on an investable technology.** The equations divide `INV` by
   `ilr(i)`; every investable tech is assigned `ilr = 1` at `b_inputs.gms:3758`,
   so this should be unreachable — but a division by zero would corrupt the
   ceiling silently rather than fail, so it's checked explicitly.
2. **Switch on, both cap files empty.** Since `0` means "no cap", a run with
   `GSw_CEPM_TgCap=1` and no data loaded would solve happily and completely
   uncapped — which is exactly what a failed or skipped harvest step looks like.
   This is the guardrail that protects phase B from a silently-broken phase A.

**Both need `$onImplicitAssign`.** In a healthy run `cepm_ilr_zero` has no
records, and whichever cap file is unused is legitimately empty; referencing an
all-empty symbol is GAMS error 141. Without the directive, these guardrails abort
*every* run — verified the hard way, and worth knowing before anyone adds a third
one.

### 4a. Fallback if T0 refutes F1

If the final-year infeasibility does not reproduce, the Option 3 route
(`GSw_GrowthAbsCon`) becomes available again but still needs: a first-year floor
switch so prescribed 2026 builds don't force infeasibility, ILR handling in the
harvest script (F3), and some answer to F2's lumpiness — which has no fix inside
a parameter with no `t` index. In that case the realistic choice is Option 3 for
a *pace* limit plus this equation for the *cumulative* ceiling, not Option 3
alone. Revisit D1 with T0's result in hand.

**Why this and not a patched `GSw_GrowthAbsCon`:**

| | patch Option 3 | new equation |
|---|---|---|
| Upstream lines *edited* | 2 (both inside an upstream equation) | 0 — everything additive |
| Fixes F1 | needs a `tlast` fallback | n/a — cumulative, no gap arithmetic |
| Fixes F2 | **cannot** — no `t` index on the parameter | n/a — cumulative by construction |
| Fixes F3 | no — bounds `INV` in MW_dc | yes — `/ ilr(i)` puts it in MW_ac |
| Can exclude prescribed 2026 builds | needs a *third* patch (no first-year floor exists) | `Sw_CEPM_TgCapStartYear` |
| Model statement | n/a | none needed — `Model ReEDSmodel /all/` (`e_solveprep.gms:7`) |
| Rebase risk | edits lines upstream may touch | additive block; conflicts only on adjacent edits |

`Sw_CEPM_TgCap` and `Sw_CEPM_TgCapStartYear` need **no GAMS plumbing at all**:
`reeds.io.write_gswitches` (`reeds/io.py:1950-1980`) auto-emits `scalar Sw_X`
for every numeric `GSw_X` in the cases file.

**No slack variable is proposed.** ReEDS already has unserved-energy slack, so a
binding RE ceiling should push the model to gas or to load-shedding rather than
to infeasibility. If a run does go infeasible we want to know, not to quietly
pay a penalty. If that proves wrong in practice, the fallback is a penalized
`CEPM_CAP_ABOVE(tg)` slack, which costs one extra line in `d_objective.gms` —
see D6.

**Semantics to document loudly:** `cepm_tg_cap(tg) = 0` means "no cap" (the
`$cepm_tg_cap(tg)` guard drops the equation), not "zero builds". A true zero
should use `bannew(i)` instead.

---

## 5. Component design

### 5.1 ReEDS-side files (all additive)

| File | Change |
|---|---|
| `reeds/core/setup/c_model.gms` | +2 declaration lines, +1 equation block (§4) |
| `reeds/core/setup/b_inputs.gms` | +2 parameter blocks (§4) |
| `reeds/input_processing/runfiles.csv` | +2 rows (below) |
| `cases.csv` | +3 rows (below) |
| `inputs/growth_constraints/cepm_tg_cap_{sys,reg}_none.csv` | new, header-only (the defaults) |
| `cases_cepm.csv` | +2 rows (`GSw_CEPM_TgCap`, `cepmtgcapscen`) and +2 case columns (`<stem>_limitre`, `<stem>_optimized`) |
| `CEPM/reeds-to-cepm-log.md` | inventory rows + a section |

Orchestration-side files, added later and covered in §5.3-5.4 rather than here:
`CEPM/scripts/make_tg_cap.py`, `CEPM/scripts/multistep_cases.py`, and
`run_cepm.ps1`'s `-m`/`--harvest-args`.

`runfiles.csv` rows — **both are non-region rows**, i.e. `region_col` is left
blank and `aggfunc`/`disaggfunc` are both `ignore`, even though the regional file
carries an `r` column:

```
cepm_tg_cap_reg.csv,inputs/growth_constraints/cepm_tg_cap_reg_{cepmtgcapscen}.csv,1,ignore,ignore,,,,,0,,,,,,
cepm_tg_cap_sys.csv,inputs/growth_constraints/cepm_tg_cap_sys_{cepmtgcapscen}.csv,1,ignore,ignore,,,,,0,,,,,,
```

#### Why not the region-filter treatment (correcting this draft's original row)

This draft first proposed `...,1,sum,ignore,r,tg,,1,0,...` for the regional row,
on the reasoning that an `r`-indexed file should use the machinery the other
`r`-indexed rows use, and that `aggfunc=sum` would be "a no-op in practice."
Both halves of that are wrong, and the failure mode is silent rather than loud.

`copy_files.py` splits `runfiles.csv` into non-region files (plain copy) and
region files, on `region_col` being blank/`ignore` vs. not
(`copy_files.py:128-146`). Setting `region_col=r` moves our file onto the region
path, where `write_region_indexed_file` calls
`reeds.spatial.upscale_from_county_to_zone` **unconditionally** whenever
`aggfunc != 'ignore'` (`copy_files.py:1095-1101`) — not only when the run is at
mixed or county resolution. That function does:

```python
df[region_col] = df[region_col].map(county_r_map)   # spatial.py:548
```

where `county_r_map` is indexed by five-digit-FIPS county labels (`p04013`,
`spatial.py:535-536`). That whole framework assumes the *source* file in
`inputs/` is county-resolution data waiting to be rolled up to the run's zones.
Our cap file is the opposite kind of artifact: it is harvested from a **completed
run at that run's own resolution**, so its regions are already model regions
(`p27`, `p29`, `p31`, `p59`, `z28` in WECC-SW). None of those are counties, the
`.map()` returns `NaN` for every row, and the subsequent `groupby` drops every
NaN key — delivering an **empty** `cepm_tg_cap_reg.csv` to `inputs_case/`.

Two independent things then go wrong:

- If the run also has a system-scope cap, the empty-file guardrail in
  `b_inputs.gms` does *not* fire (it sums both files), so the regional ceiling
  vanishes silently and the run reports success while capping less than asked.
- `fix_cols=tg` never matches anyway, because the CSV's first column is literally
  `*tg` — the `*` that makes GAMS treat the header as a comment is not a pandas
  comment character. `upscale_from_county_to_zone` keeps only `fix_cols` that are
  actually present (`spatial.py:530`), so even on county-shaped data it would
  have grouped by `r` alone and summed every tech group into one number per
  region.

`wide=1` was wrong for the same reason the `table` was (§4): the file is long,
not a `tg × r` matrix.

The tradeoff of the plain-copy path is that regions are no longer filtered
against `val_r_all`. That is the right trade: reusing a cap harvested at one
region set in a run with another is a mistake we want to hear about, and it fails
loudly — an unrecognized label in a `parameter x(tg,r) / ... /` list is a GAMS
domain error at compile time, not a silently dropped row. Verified end-to-end:
`runs/v20260901t4b_WECC-SW_t4rc/inputs_case/cepm_tg_cap_reg.csv` is byte-identical
to the harvested `inputs/growth_constraints/cepm_tg_cap_reg_t4rc.csv`.

**General lesson for this fork:** `runfiles.csv`'s region columns are for
*upstream county-resolution inputs*. Any CEPM file harvested from a finished run
is already at model resolution and belongs on the non-region path.

`cases.csv` rows:

```
cepmtgcapscen,CEPM: suffix selecting inputs/growth_constraints/cepm_tg_cap_{sys,reg}_{}.csv,N/A,none,
GSw_CEPM_TgCap,CEPM: turn on/off the cumulative tech-group investment caps,0; 1,0,
GSw_CEPM_TgCapStartYear,CEPM: first solve year whose investment counts against the caps,int,2026,
```

One `cepmtgcapscen` value selects both the system and regional files, so a
scenario is always a matched pair — you cannot accidentally pair this batch's
system cap with last batch's regional cap.

`cases_cepm.csv` per case: `_baseline` and `_optimized` get
`GSw_CEPM_TgCap=0`; `_limitre` gets `GSw_CEPM_TgCap=1` and a `cepmtgcapscen`
value naming the generated file.

The `{switch}` pattern in `runfiles.csv` is deliberately chosen over a
`copy_files.py` hook: `runfiles.csv` changed only by *added rows* in 2026.08.03,
while `copy_files.py` was substantially rewritten (§8).

### 5.2 Getting the generated file to the `_limitre` case only

The generated cap file is per-batch, but `cepmtgcapscen` lives in a git-tracked
cases file. Two options:

- **(a) Fixed token.** `cases_cepm.csv` carries `cepmtgcapscen,cepm_auto` for
  the `_limitre` column forever; the orchestrator writes
  `inputs/growth_constraints/cepm_tg_cap_cepm_auto.csv` before phase B and
  deletes it after. Dead simple and readable, but two batches running phase B
  concurrently from the same clone would clobber each other's ceiling.
- **(b) Generated cases file (recommended).** The orchestrator reads
  `cases_cepm.csv` with `reeds.inputs.parse_cases` (`reeds/inputs.py:143`,
  signature unchanged in 2026.08.03), substitutes
  `cepmtgcapscen = <BatchName>` into the `_limitre` column, writes
  `cases_cepm__<BatchName>.csv`, and passes `-c cepm__<BatchName>` to phase B.
  The cap file is `cepm_tg_cap_<BatchName>.csv`. Both generated files are
  deleted in a `finally`. Collision-free, and `git status` stays clean.

Cross-case contamination *within* a batch is a non-issue either way: `_baseline`
and `_optimized` set `GSw_CEPM_TgCap=0`, so they ignore whatever the data file
says.

### 5.3 `CEPM/scripts/make_tg_cap.py`

```
usage: make_tg_cap.py --baseline-case runs/<Batch>_<stem>_baseline
                      --out-dir inputs/growth_constraints --token <BatchName>
                      [--scope system|region|both]        (default: system)
                      [--tgs pv,wind-ons,wind-ofs,csp,battery,pumped-hydro]
                      [--headroom 1.00] [--zero-floor 0.001] [--clamp-to-floor]
                      [--from-year 2026] [--to-year 2032] [--print-only]
```

Writes `cepm_tg_cap_sys_<token>.csv` and `cepm_tg_cap_reg_<token>.csv`; the one
not selected by `--scope` is written header-only so the matched pair always
exists and the unused equation is inert.

Behavior:

1. Fail loudly if `<case>/outputs/outputs.h5` is absent.
2. `df = reeds.io.read_output(case, 'cap_new_out')` → columns `i, r, t, Value`
   (MW_ac). `read_output` is unchanged in 2026.08.03.
3. Build the `i → tg` map by mirroring `b_inputs.gms:794-807` on the **run's own**
   `inputs_case/tech-subset-table.csv`, expanded through
   `reeds.techs.import_tech_groups` (`reeds/techs.py:45-64`, which handles the
   `upv_1*upv_10` GAMS range syntax — a plain `pd.read_csv` does not):
   - `pv` ← (`UPV` ∪ `PVB`) − `distpv`
   - `wind-ons` ← `ONSWIND`
   - `wind-ofs` ← `OFSWIND`
   - `csp` ← `CSP` (plus the non-numeraire CSP classes when `GSw_WaterMain` is
     on — `b_inputs.gms:810-811`; CEPM cases run with it off today, so flag
     rather than silently ignore)
   - `battery` ← `BATTERY`
   - `pumped-hydro` ← `PSH`
4. Filter to `from-year ≤ t ≤ to-year`, then sum `Value` — over `r` for the
   system file, by `r` for the regional file — multiply by `--headroom`, round.
5. **Apply `--zero-floor` to any requested group (or group/region cell) whose
   sum is zero**, so the ceiling stays on. See "the zero-value trap" in §4.
6. **No ILR conversion** — the equations are in MW_ac by construction (F3).
7. Emit a summary table to stdout (it lands in `bootstraplog.txt`), listing each
   group's harvested value and flagging every floored cell explicitly. Warn on
   any `i` present in the outputs but absent from the map.

For the WECC-SW baseline above, `--scope system --from-year 2026 --to-year 2032`
yields `pv,20181` / `wind-ons,16439` / `battery,8583`, and `wind-ofs`, `csp`,
`pumped-hydro` all floored to `0.001` (MW_ac).

### 5.4 `run_cepm.ps1`

New bootstrap-only switch `-m/--multistep <stem>`. `-m` is free of both
`runreeds.py`'s reserved letters (`-b -c -s -r -l -f -d -n -p -t -h`) and the
existing bootstrap set (`-y -q -u -x -o`); the reserved-options block in the
script header needs updating to record it.

Sequence, all inside the existing transcript `try`/`finally`:

1. Resolve `-b`/`-c` as today. Verify all three case columns exist in the cases
   file, and that `_limitre` has `GSw_CEPM_TgCap=1` while the other two have
   `0`; abort with a clear message otherwise.
2. Phase A: `runreeds.py -b $BatchName -c $CasesSuffix -s "${stem}_baseline" -r 1`.
   Non-zero exit or missing `outputs.h5` → throw (and ntfy).
3. Harvest: `uv run python CEPM/scripts/make_tg_cap.py ...`.
4. Write the generated cases file (§5.2b).
5. Phase B: `runreeds.py -b $BatchName -c <generated> -s "${stem}_limitre,${stem}_optimized" -r 2`.
6. Existing `-x` comparison path, unchanged — `compare_cases.py "runs/$BatchName_"`
   picks up all three and defaults its base to the alphabetically-first completed
   case, which is `_baseline`.
7. `finally`: delete the generated cap CSV and cases file; warn, never throw.

**Hazard found the hard way while running T0 — load-bearing for this design:**

- **`runreeds.py` exits 0 on a failed case.** The T0 run's 2032 solve went
  infeasible, `3_solve_oneyear.gms` aborted, no `outputs.h5` was written — and
  `runreeds.py` still printed *"…has finished"* and returned exit code 0, so
  `run_cepm.ps1` reported success. Phase A therefore **cannot** trust the exit
  code; it must verify `runs/<Batch>_<stem>_baseline/outputs/outputs.h5` exists
  before harvesting, and `make_tg_cap.py` must fail loudly if it doesn't (§5.3
  step 1). Without both checks, a silently-failed baseline yields an empty or
  partial ceiling and phase B runs on garbage. Worth considering a
  `neue_<endyear>i0.csv` check too, since that file's absence is what first
  flagged the failure here.

Two further existing behaviors need a look in this mode:

- `CEPM/scripts/get_batch_info.py` returns the first **non-ignored** case in the
  cases file for the `bootstraplog.txt` destination and `--startyear`. Under
  `-m`, `-s` overrides `ignore`, so that case may not be one of the three that
  ran. Simplest fix: in `-m` mode, target `runs/<Batch>_<stem>_baseline`
  directly and read `yearset` from the `_baseline` column.
- ntfy messages should name the phase, so a long two-phase batch is legible from
  a phone.

### As built (2026-09-02)

Implemented as designed above, with three additions worth recording.

**`CEPM/scripts/multistep_cases.py`** does the §5.4 step-1 validation and the
§5.2(b) cases-file generation. Validation resolves defaults through
`reeds.inputs.parse_cases` rather than reading raw cells, because a blank
`GSw_CEPM_TgCap` cell is the *correct* way to express 0 (it inherits from
`cases.csv`) and a raw read would report `''` and prove nothing. Generation, by
contrast, works on the raw file so the written copy keeps every row and blank
exactly as committed — the generated file differs from the source by **one cell**.
It also warns if `_limitre` and `_optimized` differ in any switch besides the
ceiling, which is the §1 factorial stated as an executable check. Validation
additionally returns the baseline's `yearset` start year, which is what `-m`
uses for `--startyear` and for the `bootstraplog.txt` destination.

**`--harvest-args "<args>"`** passes extra flags through to `make_tg_cap.py`
(e.g. `--harvest-args "--scope both --headroom 0.95"`). The script's own defaults
already encode D2/D3/D4, so the common case needs nothing.

**Hazard found while building it — phase B hangs without an explicit worker
count.** `runreeds.py` short-circuits to `WORKERS=1` only when `len(caseList)==1`
(`runreeds.py:979-989`); with two or more cases and no `--simult_runs` it calls
`input('Number of simultaneous runs [positive integer]: ')`. Phase A is immune
(one case), but **phase B runs two**, so a background or CI invocation would
block forever on a prompt nobody can see. `-m` therefore passes
`--simult_runs 2` itself unless the caller supplied one.

This is *not* contradicted by the §9 note that `--simult_runs` fails through the
wrapper: that bug is in PowerShell's binding of **caller-supplied** arguments
(`-r` being a unique prefix of the script's own `$RunbatchArgs` parameter). Args
the script builds into an array itself never reach that binder, so they work
fine. Forward `--simult_runs 1` to run the two phase-B cases sequentially
instead.

### 5.5 Reporting

`cap_new_out` already gives per-case buildout, so the ceiling is verifiable from
existing outputs — no new report parameter is strictly required. Optional
nice-to-have: dump `cepm_tg_cap` into the run's outputs so a case carries its
own ceiling for later plotting.

---

## 6. Design decisions

- **D1 — mechanism. DECIDED (T0, 2026-09-01): purpose-built cumulative equations
  (§4).** T0 confirmed F1 in both a standalone reproduction and a live
  `WECC-SW_baseline`-configured run, where CPLEX's conflict refiner isolated the
  infeasibility to `eq_growthlimit_absolute(PV,2032)` alone. `GSw_GrowthAbsCon`
  is unusable here without patching an upstream equation, and even patched it
  cannot follow a lumpy baseline (F2). §4a is retained only as a record of the
  path not taken.
- **D2 — scope. DECIDED: both, switchable.** Two parameters and two equations
  (§4), selected per run by which file the harvest script populates
  (`--scope system|region|both`). Both populated means both bind. Note this
  option only exists because we are writing our own equation —
  `growth_limit_absolute` has no `r` index at all.
- **D3 — what counts against the ceiling. DECIDED: cumulative gross builds from
  2026**, i.e. `Sw_CEPM_TgCapStartYear=2026` and `--from-year 2026`. This
  includes the 2026 prescriptions, which are exogenous and identical across all
  three cases, so it leaves no front-loading leak and keeps the baseline path
  exactly feasible under its own ceiling (T3).
- **D4 — groups and headroom. DECIDED:** `pv`, `wind-ons`, `wind-ofs`, `csp`,
  `battery`, `pumped-hydro` at `--headroom 1.00`. The wider list closes the leak
  where displaced RE reappears as an uncapped renewable, at the cost of the
  zero-value trap handled in §4 and tested by T5(d).
- **D5 — cases-file plumbing. DECIDED (implementation, 2026-09-02): generated
  cases file** (§5.2b). `run_cepm.ps1 -m` writes
  `cases_<suffix>__<BatchName>.csv` with `cepmtgcapscen` for the `_limitre`
  column set to the batch name, and deletes it in a `finally`. Collision-free
  between concurrent batches, and verified by T6/T8 to leave `git status` clean
  even when phase B fails. The generated file differs from the committed one by
  exactly one cell.
- **D6 — hard vs. penalized. DECIDED: hard, no slack.** Revisit if T4/T5 show
  infeasibility is a practical risk; adding a penalized `CEPM_CAP_ABOVE(tg)`
  later costs one `d_objective.gms` line.
- **D7 — what counts as "arriving capacity". DECIDED (review, 2026-09-01):
  `INV + INV_REFURB + UPGRADES − UPGRADES_RETIRE`**, matching `report.gms`'s
  `cap_new_out` exactly so the constraint measures the same quantity the ceiling
  is harvested from. `eq_interconnection_queues`, which this equation is modeled
  on, counts only `INV + INV_REFURB`; copying that would have left a real hole,
  because upgrade techs inherit `tg` membership from the tech they upgrade *to*
  (`b_inputs.gms:412-413`) and `upgrade_link.csv` contains
  `hydED → pumped-hydro`. With `GSw_Upgrades` defaulting to 1, a storage ceiling
  could otherwise have been evaded by upgrading hydro instead of building
  batteries. `INV_REFURB` matters independently: all 30 UPV/onshore/offshore wind
  classes are `refurbtech`, so repowering counts on both sides.
- **D8 — how the cap files reach `inputs_case/`. DECIDED (implementation,
  2026-09-01; re-verified 2026-09-02): the non-region path**, i.e. `region_col`
  blank and `aggfunc`/`disaggfunc` both `ignore` on **both** `runfiles.csv` rows,
  including the `(tg,r)` one. This **reverses** this draft's original §5.1 row,
  which used `region_col=r, aggfunc=sum, fix_cols=tg, wide=1` on the regional
  file. Full reasoning in §5.1; the short version is that `runfiles.csv`'s region
  machinery exists to roll *county-resolution upstream inputs* up to a run's
  zones, and it would have silently emptied our file — which is harvested from a
  finished run and is therefore already at model resolution. The related
  consequence is that the regional GAMS symbol is a long-format `parameter`, not
  a `table` (§4). Re-checked against `2026.08.03` and `upstream/main` in §8a:
  the split predicate this relies on is byte-identical at both, and the region
  path we avoided is exactly the code upstream is currently rewriting.

---

## 7. Test plan

Ordered so that the cheapest disqualifying test runs first.

**T0 — confirm F1 before building anything. This is D1's decision gate.**
Two parts:

- *Part 1, standalone (0.3 s).* A GAMS file replicating `b_inputs.gms:1049-1055`
  and the `eq_growthlimit_absolute` LHS over the CEPM solve-year set, solved as a
  toy LP. Isolates the set arithmetic from everything else in ReEDS.
  **Result: infeasible, as predicted — see F1.** Worth keeping as a regression
  artifact (suggested home: `CEPM/scripts/t0_growthgap.gms`) since it re-runs in
  under a second after any rebase.
- *Part 2, live run.* `WECC-SW_baseline`'s exact configuration plus
  `GSw_GrowthAbsCon=1` and `GSw_GrowthConLastYear=2032` (and `cleanup_level=0`,
  to keep `lstfiles/` for diagnosis and to avoid an interactive prompt that
  blocks non-interactive shells). Confirms the equation is really generated in a
  live sequential solve rather than filtered out by `tmodel`/`valinv`. Expect
  2010/2026/2029 to solve and 2032 to fail.

**Both parts ran on 2026-09-01 and confirmed F1 — see F1 for results. D1 is
closed.** Reproduce with:

```powershell
# cases_t0.csv = WECC-SW_baseline cloned, plus GSw_GrowthAbsCon=1,
#                GSw_GrowthConLastYear=2032, cleanup_level=0
.\run_cepm.ps1 -y -q -b v20260901t0 -c t0 -s WECC-SW_t0growthcon
```

**T1 — harvest unit test. PASSED 2026-09-01 (18/18 assertions).** Run
`make_tg_cap.py` against a completed baseline and assert: totals match a hand
computation from `cap_new_out.csv`; `distpv` is excluded from `pv`;
`upv_1*upv_10` range syntax expands (i.e. no UPV class is silently dropped);
upgrade inheritance is replicated (`hydED_pumped-hydro`→`pumped-hydro`,
`Gas-CC_*-CCS`→`gas`, `*_coal-CCS_*`→`coal`); `--headroom` scales;
`--scope region` sums by `r` to the same system total; `wind-ofs`/`csp` come out
at the zero-floor, not `0`; `--from-year` excludes 2010. Cheap, no ReEDS run.

Two script bugs this caught, both of which would have quietly corrupted a
ceiling:

- `reeds.io.read_output` returns **float32**, so sums carried ~6e-4 MW of error
  on a 20 GW total — the same order as the 0.001 zero-floor, in a file feeding a
  hard constraint. Now cast to float64 on read.
- Writing values with `:g` truncates to 6 significant figures, silently
  rewriting `pv,20181.180` as `pv,20181.2`. Harmless upward, but rounding *down*
  would make a self-harvested ceiling bind and fail T3 for an entirely spurious
  reason. Now `:.3f`, matching `harvest()`'s `round(3)`.

Note when writing assertions: outputs are float32, so `DataFrame.equals()` is
the wrong comparison — use an absolute/relative tolerance.

**T2 — inert when off. PASSED 2026-09-01** (`runs/v20260901t2b_WECC-SW_baseline`,
and `runs/v20260901t2_WECC-SW_baseline`, which is identical to it). A
`WECC-SW_baseline` built on `mvp/two-step-runs` (`b310704c`) with the new
equations, parameters and both guardrails compiled in, `GSw_CEPM_TgCap=0` and
`cepmtgcapscen=none`, against the pre-change `runs/v20260824-2_WECC-SW_baseline`
(branch `mvp-scenario`, `a637b36f`). `z_rep.csv`, `cap_new_out.csv` and
`objfn_raw.csv` are **byte-identical** — not merely within tolerance; the 2032
objective is 40,443,825,903.56735 in both. Proves the additive GAMS changed
nothing, and in particular that the two `$onImplicitAssign` guardrails are inert
when the switch is off.

**T3 — self-consistency (the strongest single test). PASSED 2026-09-01**
(`runs/v20260901t3_WECC-SW_t3selfcap`). Take the baseline's own switches, add
`GSw_CEPM_TgCap=1` with the ceiling harvested from that same run, and re-solve.
It must solve and reproduce the unconstrained baseline. This simultaneously
proves the units are right (F3), the tech-group mapping and upgrade inheritance
are right, `Sw_CEPM_TgCapStartYear` doesn't exclude counted builds, and the
prescribed 2026 builds fit under the cap. Any of those being wrong shows up here
as a binding constraint or an infeasibility.

Result: all four solve years Optimal, no guardrails fired, and 4 system cap rows
generated (`csp` and `wind-ofs` drop out — no investable capacity in WECC-SW, so
their equations have no variables). Against the unconstrained baseline:

| quantity | difference |
|---|---|
| `cap` | max 0.00024 MW (2.2e-07 relative) |
| `cap_new_out` | max 0.00033 MW |
| 2032 objective | 40,443,825,903.57 → 40,443,825,910.05 (**1.6e-10** relative) |

i.e. identical to solver tolerance.

**T4 — binds when it should. PASSED 2026-09-01** at `--headroom 0.95`
(`runs/v20260901t4b_WECC-SW_t4`). Every capped group lands *exactly* on its
ceiling — pv 19,172.1, wind-ons 15,616.9, battery 8,153.9, pumped-hydro 916.9
MW_ac, all with +0.00 slack. Uncapped groups absorbed the displacement (gas
+381 MW, h2 +407 MW) and the 2032 objective rose 1.60%. This is the test that
proves the mechanism restrains anything at all; T3 alone cannot, because there
the ceiling sits exactly at the unconstrained optimum and never has to push.

**T4r — regional scope. PASSED 2026-09-01** across three runs:

- `t4ra` (region, headroom 1.0) reproduces the baseline to **1.4e-10** on the
  objective and 0.00024 MW on capacity — the T3 result at region scope.
- `t4rb` (region, 0.95, `--clamp-to-floor`) — 0 cells over cap, 8 cells binding
  exactly at 0.95 × baseline, 6 cells clamped to their prescribed floor, 1 cell
  with genuine slack (`pumped-hydro/z28`, which the model chose not to fill once
  its neighbours were constrained).
- `t4rc` (both scopes, 0.95, clamped) — 0 violations in either scope, 4/4 system
  caps binding, 10/15 regional cells binding.

**The cost ordering is the useful result**, and it makes the D2 trade-off
concrete rather than theoretical:

| case | 2032 objective | vs baseline |
|---|---:|---:|
| baseline (uncapped) | 40,443,825,904 | — |
| system, 0.95 | 41,089,822,395 | **+1.60%** |
| region, 0.95 | 41,217,975,071 | **+1.91%** |
| both, 0.95 | 41,490,409,125 | **+2.59%** |

Per-region ceilings are strictly tighter than a system-wide ceiling of the same
total, because they remove the model's freedom to relocate capacity; both
together are tighter still. Choose scope accordingly — "cap the same MW" means
materially different things at each.

**T5 — edge cases.** Revised after the guardrails landed; (b) in particular now
asserts the opposite of what this draft first specified.

- **(a) `battery` cap set very small. PASSED 2026-09-03**
  (`runs/v20260903t5a_WECC-SW_t5a`). "Very small" is bounded from below by F5:
  battery's 2026 prescribed floor is 7,852.6 MW, so the tightest *feasible*
  system cap is essentially that. Set to **7,853.0 MW** — 8.5% under the
  baseline's 8,583.0 — with every other group left uncapped, so the test
  isolates one binding ceiling:

  | tech group | baseline | T5(a) | vs baseline |
  |---|---:|---:|---:|
  | battery | 8,583.010 | **7,853.000** (= cap, exactly) | −730.0 |
  | pumped-hydro | 965.153 | 1,817.854 | **+852.7** |
  | wind-ons | 16,438.874 | 15,892.175 | −546.7 |
  | pv | 20,181.180 | 20,151.450 | −29.7 |

  2032 objective 40,443,825,904 → 40,787,547,648 (**+0.85%**). The cap binds to
  the exact digit with ~730 MW of headroom removed, which is the assertion.

  **The displacement is the more interesting result.** The model replaced the
  lost battery almost 1:1 with **pumped hydro** (+852.7 MW against −730.0 MW of
  battery) rather than shedding storage or buying gas. That is a direct,
  quantified demonstration of the leak **D4** exists to close: cap one storage
  technology and the model simply routes around it into an uncapped one. Here
  that was intentional — only `battery` was capped — but it is exactly why the
  production configuration caps `pv`, `wind-ons`, `wind-ofs`, `csp`, `battery`
  *and* `pumped-hydro` together.
- **(b) switch on, both cap files empty → the run must ABORT. PASSED 2026-09-02**
  (`runs/v20260902t5b_WECC-SW_limitre`). The original wording ("equation never
  generated, identical to T2") describes a state the `b_inputs.gms` guardrail now
  makes impossible on purpose — that state is exactly what a failed or skipped
  harvest looks like, and it would otherwise solve happily and completely
  uncapped. Run `WECC-SW_limitre` in its committed default state
  (`GSw_CEPM_TgCap=1`, `cepmtgcapscen=none`), i.e. the case as it sits in
  `cases_cepm.csv` with no harvest having run. Result — no `outputs.h5`, and:

  ```
  *** Error at line 110668: Execution halted: abort$1 'CEPM: GSw_CEPM_TgCap=1 but
  both cepm_tg_cap_sys.csv and cepm_tg_cap_reg.csv are empty, so nothing would be
  capped. Check cepmtgcapscen and that make_tg_cap.py actually ran.'
  ```

  Two things worth keeping from this. First, the committed `_limitre` column *is*
  this test: anyone who runs that case without `-m` gets the abort rather than a
  silently uncapped run, which is the desired safety property and needs no
  separate fixture. Second, `run_cepm.ps1` still exited **0** — the F1-era hazard
  in §5.4, re-confirmed. It is exactly why `-m` phase A checks for `outputs.h5`
  rather than trusting the exit code. The "inert when the files are empty" half of
  the original intent is covered by T2 (switch off, `none` files).
- **(c) a `tg` label not in `tg.csv`. PASSED 2026-09-03**
  (`runs/v20260903t5c_WECC-SW_t5c`) — **and the answer is better than this test
  originally expected.** The draft asked us to "confirm it is ignored rather than
  silently mis-binding"; in fact a bad label is not ignored at all. It is caught
  twice, both times loudly:

  1. **At the script.** `make_tg_cap.py` validates `--tgs` against the run's own
     tech-group set and refuses to write anything:
     `error: unknown tech group(s) ['H2']; known: ['battery', 'biomass', 'coal', 'csp', 'dr_shed', 'gas', ...]`
     (observed while querying T7 — note the set is lowercase, so `h2`, not `H2`).
     That closes the realistic path by which a bad label reaches a cap file.
  2. **At GAMS**, if someone hand-edits one in anyway. A cap CSV containing
     `unobtanium,5000.000` above a legitimate `pv,20181.180` row gives:

     ```
     --- .. cepm_tg_cap_sys.csv(2) 87 Mb 1 Error
     *** Error 170 in .../inputs_case/cepm_tg_cap_sys.csv
         Domain violation for element
     ...
     *** Status: Compilation error(s)
     ```

     The run stops at compile with no `outputs.h5`, and GAMS names the file
     **and the offending line** (`(2)` — the `unobtanium` row; line 3's `pv` row
     loads fine). This falls out of declaring the parameter over the `tg` domain
     in §4 and needs no guard of our own.

  So "silently mis-binding" is not a reachable state, which is a stronger result
  than the test asked for. Update expectations accordingly if this is ever
  re-run.
- **(d) zero-value trap. PASSED 2026-09-03** on the mechanism
  (`runs/v20260903t5da_SERTP_t5da` vs `runs/v20260903t5db_SERTP_t5db`);
  inconclusive on the solution, for a reason worth recording.

  **Why not WECC-SW.** T3 established that `csp` and `wind-ofs` produce no
  equation rows there — no investable capacity in the region at all — so a
  floored ceiling has no variables to bind on and the working and broken
  behaviors look identical. SERTP has both `wind-ofs` (340 supply-curve rows) and
  `pumped-hydro` (128), each investable and each with **zero** baseline builds,
  so both get the floor. `csp` has 0 rows there too and remains untestable.

  **Why `pumped-hydro` rather than `wind-ofs`.** T9 showed a starved model
  reaches for **gas**, which is uncapped and far cheaper than offshore wind, so
  neither variant would ever build `wind-ofs` and the solution could not
  discriminate. `pumped-hydro` looked more promising because T5(a) showed the
  model actively substituting PSH for squeezed battery. Setup: ceiling harvested
  from `runs/v20260825_SERTP_baseline` with **battery squeezed to 4,692 MW** —
  just above its 4,691.1 MW prescribed floor, a 29% cut — and two cap files
  differing in exactly one cell:

  | | `pumped-hydro` row |
  |---|---|
  | variant A (`t5da`) | `0.001` — the script's floor |
  | variant B (`t5db`) | `0.000` — the literal zero |

  **Result at the solution level: no difference.** Both built **0 MW** of PSH,
  both bound battery at exactly 4,692.000, and `cap_new_out` came out
  **byte-identical**; objectives agree to solver noise. SERTP simply never wants
  PSH — the squeezed battery went to gas instead (30,759.8 → 40,730.5 MW,
  +9,970.7). The T5(a) substitution did not reproduce here.

  **Result at the equation level: decisive.** `SINGLE EQUATIONS` from the GAMS
  listings:

  | solve year | A (`0.001`) | B (`0`) | difference |
  |---|---:|---:|---:|
  | 2026 | 26,982 | 26,982 | 0 |
  | 2029 | 45,233 | 45,232 | **+1** |
  | 2032 | 60,423 | 60,422 | **+1** |

  Exactly one extra row in A, in exactly the years `pumped-hydro` is investable —
  `eq_cepm_tg_cap_sys('pumped-hydro')`. 2026 ties because PSH is not yet
  investable that year, so the row has no variables and is presolved away in both.

  **This is the assertion, proven:** a literal `0` drops the constraint entirely
  (GAMS stores no record, the `$` guard fails), while `0.001` generates it. In
  variant B nothing was stopping unlimited PSH — it simply happened not to be
  economic. That is precisely why the floor exists: **you cannot rely on
  economics to keep an uncapped group at zero**, and a harvest that writes an
  honest `0` silently removes the ceiling D4 was chosen to provide.

  Caveat for anyone re-running this: the solution-level half of the test needs a
  region where the floored group is genuinely competitive. Neither WECC-SW nor
  SERTP is, for any of the three zero-build groups. The equation-count check is
  the portable evidence.

**T6 — orchestration, dry run. PASSED 2026-09-02** (batches `v20260902t6`,
`t6b`, `t6c`). `-m WECC-SW -t`: validation passes, both phases get the right case
names (`WECC-SW_baseline`, then `WECC-SW_limitre,WECC-SW_optimized`), the
generated cases file is written with `cepmtgcapscen` flipped `none` → the batch
name, and removed again in the `finally`. `git status` clean afterwards. The
`bootstraplog.txt` warning is expected here — `--dryrun` quits before any run
folder exists.

Two flag-conflict guards were added and verified to refuse immediately, before
the GAMS/Julia/uv preflight: `-m` with `-o/--compare-only`, and `-m` with a
caller-supplied `-s/--single`. **The `-o` one was a real bug when first written:**
the guard was inside Step 8's `else` branch, which `-o` skips entirely, so
`-m -o` silently ignored the `-m`. Both guards now sit immediately after argument
parsing.

**T7 — orchestration, real. PASSED 2026-09-02** (`runs/v20260902t7_WECC-SW_*`),
in ~52 minutes wall clock for all three cases. One invocation:

```powershell
.\run_cepm.ps1 -y -x -b v20260902t7 -c cepm -m WECC-SW
```

Every assertion holds: three run folders, three `outputs.h5`, phase A gated on
its own outputs before harvesting, the ceiling harvested and both cap CSVs
written, the generated cases file produced and passed to phase B, both phase B
cases run concurrently under `--simult_runs 2`, `compare_cases.py` run with
`--startyear 2026` (taken from the `_baseline` column, not from
`get_batch_info.py`) producing
`outputs/comparisons/results-WECC-SW_baseline,WECC-SW_limitre,WECC-SW_optimized.pptx`
with `_baseline` as base, `bootstraplog.txt` in the baseline folder, and all
three generated files removed in the `finally` leaving `git status` clean.

The baseline's 2032 objective came out at **40,443,825,903.56735** — identical to
T2's and to the pre-change `v20260824-2` baseline, so the whole `-m` path
demonstrably did not perturb the counterfactual.

**T8 — cleanup is unconditional. PASSED 2026-09-02** (batch `v20260902t8`).
Forced a **phase-B-only** failure by copying `cases_cepm.csv` to `cases_t8.csv`
with an invalid `GSw_CCS=7` on the `_optimized` column alone. That is the useful
shape of this test: `runreeds.py` validates only the cases named in `-s`, so
phase A passes, the cap token and cases file are generated, and phase B is the
thing that dies. Result: `run_cepm.ps1` threw
*"Phase B (WECC-SW_limitre, WECC-SW_optimized) failed: runreeds.py returned 1"*,
the generated cases file was removed by the `finally` **before** the throw
propagated, and `git status` came back clean.

**T9 — comparison sanity. PASSED 2026-09-02** on T7's batch. Cumulative gross new
capacity 2026-2032, MW_ac, from each case's own `cap_new_out`:

| tech group | `_baseline` | `_limitre` | `_optimized` | ceiling |
|---|---:|---:|---:|---:|
| pv | 20,181.2 | **20,181.2** | 41,305.4 | 20,181.2 |
| wind-ons | 16,438.9 | **16,438.9** | 18,529.3 | 16,438.9 |
| battery | 8,583.0 | **8,583.0** | 9,354.6 | 8,583.0 |
| pumped-hydro | 965.2 | 926.2 | 1,534.0 | 965.2 |
| gas | 5,198.5 | 35,929.2 | 22,644.0 | *uncapped* |
| h2 | 1,106.1 | 3,445.2 | 1,273.6 | *uncapped* |
| hydro | 456.0 | 471.0 | 456.0 | *uncapped* |
| biomass | 0 | 112.5 | 112.5 | *uncapped* |

| case | 2032 objective | vs `_baseline` | vs `_optimized` |
|---|---:|---:|---:|
| `_baseline` | 40,443,825,904 | — | |
| `_optimized` | 109,068,553,006 | +169.7% | — |
| `_limitre` | 145,479,820,221 | +259.7% | **+33.4%** |

Three things to read off this:

1. **The ceiling binds exactly.** `_limitre` lands on its cap to the printed
   precision for `pv`, `wind-ons` and `battery` — the same behavior T4 showed, now
   through the full orchestrated path with a ceiling nobody wrote by hand.
   `pumped-hydro` has genuine slack (926.2 against 965.2), i.e. the model chose
   not to fill it once its neighbours were constrained — the same pattern as
   T4r's `pumped-hydro/z28`.
2. **Data-center load leans heavily on new RE when allowed to.** `_optimized`
   vs `_baseline` — the load effect alone — more than doubles PV, 20.2 → 41.3 GW,
   and adds 2.1 GW wind, 0.8 GW battery and 17.4 GW gas.
3. **Denied that RE, the model buys gas.** `_limitre` vs `_optimized` — the
   ceiling effect alone — gives up 21.1 GW of PV and 2.1 GW of wind and replaces
   them with **+13.3 GW gas and +2.2 GW h2**, at a 33.4% higher 2032 objective.
   The substitution is smaller in MW than what it replaces, which is what you
   would expect from the capacity-factor difference.

**Report the substitution as thermal capacity, not a gas/h2 split.** `tg 'h2'` is
`h2_combustion(i)` — plants that **burn** hydrogen (H2-CC/H2-CT), not hydrogen
production. `GSw_H2` (electrolyzers, SMR, storage, transport) is **0** in every
CEPM case and correctly builds nothing; the H2-CC capacity came from
`GSw_H2Combustion=1` / `GSw_H2CombinedCycle=1`, fuelled at an **exogenous** price
via `h2combustionfuelscen` — `cases.csv` documents that switch as *"only used if
endogenous H2 production is turned off"*.

Re-running this batch with `GSw_H2Combustion=0` (`runs/v20260903h2off_*`) settles
what that was worth: **H2-CC converts to gas-CC essentially one-for-one**
(residual 0.00-0.52 MW per case), wind/solar/storage move by <0.02%, and the
headline gap shifts from 33.38% to **33.39%** — one hundredth of a point. So the
`+13.3 GW gas / +2.2 GW h2` split above is arbitrary; the substance is
**+15.46 GW of thermal capacity**, however it is labelled.

CEPM now sets `GSw_H2Combustion=0` and `GSw_H2CombinedCycle=0` by default. That
is an **interpretability** choice — it stops us reporting capacity fuelled by
hydrogen the model never produces — not a modelling correction. Full 2×2 in
[`interconnection-queue-and-prescribed-builds.md`](interconnection-queue-and-prescribed-builds.md)
§4.6, which also shows the h2 and queue-penalty effects are completely
independent.

That third row is the answer §1 set out to get, and the factorial is clean enough
to attribute each half of it separately.

**Caveat added 2026-09-03 — the +33.4% is distorted by the interconnection-queue
penalty.** Re-running this identical batch with the queue constraint disabled
(`GSw_CapPenaltyMult=0.000001`, run `v20260903qoff`) gives **+43.4%** instead.
The penalty falls harder on `_optimized`, which builds 41 GW of PV and so pushes
further past queue limits, than on `_limitre`, which substitutes gas — so it
*compresses* the apparent cost of holding RE at the baseline by ~10 percentage
points. It also reshapes the mix: −14.9% PV, +12.6% onshore wind, +157.6% h2.

Neither number is "the" answer. The penalty represents something physically real,
but it is applied to a 2026 solve carrying 16 years of prescriptions against one
year of queue ramp, at an undocumented $10M/MW. Treat +33.4% and +43.4% as
bounds, and see
[`interconnection-queue-and-prescribed-builds.md`](interconnection-queue-and-prescribed-builds.md)
§4.5 for the measurement and §5 for what to do about it.

**T10 — post-rebase.** Re-run T2 and T3 after the 2026.08.03 rebase.

---

## 8. Rebase to upstream `2026.08.03` — what we checked

This fork sits on upstream `2026.06.18` plus commits through `62f6381e`
(`CEPM/reeds-to-cepm-log.md`). Everything below is `git diff 2026.06.18
2026.08.03` on the specific paths this design touches.

**Unchanged — safe to build on:**

- `eq_growthlimit_absolute`, `growth_limit_absolute`, `tg_i`, `inputs/sets/tg.csv`,
  `inputs/growth_constraints/*`, and the `growth_limit_absolute.csv` row in
  `runfiles.csv`. (So F1 is *not* fixed upstream in this release either.)
- `eq_interconnection_queues`, `cap_limit`, `cap_penalty` — the equation we are
  copying is stable.
- `Model ReEDSmodel /all/` (`e_solveprep.gms:7`) — new equations still enter the
  model automatically.
- All capacity reporting: `cap_out`, `cap_new_out`, `cap_new_ann`, `ilr`.
  `report_params.csv` gains 5 rows, none of them capacity.
- `inputs/scalars.csv`: `ilr_utility` still 1.34.
- `reeds.io.read_output`, `reeds.io.write_gswitches`, `reeds.inputs.parse_cases`,
  and `reeds/techs.py` — all signature-stable.
- `runreeds.py`'s `--single` comma-list, run-folder naming, `file_replacements`,
  and the blocking `start /wait` launch.

**Changed — matters to us:**

- `reeds/input_processing/copy_files.py` — 568 lines, the largest single change
  in the release. The `cap_limit.csv` block survives but its region handling is
  rewritten from the `agglevel_variables` machinery to a `county2zone` map. This
  is the concrete reason §5.1 puts our hook in `runfiles.csv` (additive rows
  only) rather than in `copy_files.py`.
- `runfiles.csv` — additive rows (`employment_factor_plant`,
  `gasreg_price_adj_regression_params`, `jtype`, `hydadjann/sea`) plus removals
  of `financials_sys`, `financials_tech`, `incentives`, `regional_cap_cost_diff`,
  and `modeled_regions`. Our new row will not collide.
- `inputs/tech-subset-table.csv` — reformatted wholesale (148 lines) and gains a
  `GENTECH` column. Expect the rebase diff to show the whole file; the columns our
  mapper uses (`ONSWIND`, `OFSWIND`, `UPV`, `PVB`, `distpv`, `BATTERY`, `PSH`) are
  all still present, verified against `2026.08.03`.
- `cases.csv` — `GSw_PRM_StressThreshold` is replaced by
  `GSw_PRM_StressThresholdMetrics` plus six per-metric switches; `GSw_ZoneSet`
  default moves `z132` → `z90` and the allowed set gains `z90`;
  `GSw_RegionResolution` is gone. **`cases_cepm.csv` will need updating for the
  PRM stress switches** — independent of this project, but it will surface during
  the same rebase.
- New switches/params that are additive but worth knowing: `GSw_EmploymentFactor`,
  `GSw_GasPriceAdjMethod`, `GSw_gopt_mga`, `gentech(i)`,
  `storage_duration_m(i,v,r)`, `hours_t(allh,allt)`, a `gasreg` column in
  `hierarchy`, and `cplex.op3`/`.op4`.
- `postprocessing/compare_cases.py` — 61 lines; this fork already carries two
  patches there (`reeds-to-cepm-log.md`), so expect conflicts, unrelated to this
  project.

**Net:** every mechanism this design depends on sits in the stable part of the
codebase, and the design deliberately avoids the one file (`copy_files.py`) that
churned. Re-run T2/T3 after the rebase (T10); the CEPM cases file's PRM rows will
need attention regardless.

### 8a. Re-checked against the spatial revamp (2026-09-02)

Upstream has been rewriting the spatial machinery, so the §5.1 decision to put
both cap files on the **non-region path** was re-verified against two refs:
`2026.08.03` (the rebase target) and `upstream/main` at `1f73bd23` (2026-09-01,
248 commits past the tag). Between our base `2026.06.18` and `upstream/main`,
`copy_files.py` + `spatial.py` are −606 net lines.

**The revamp is a simplification *inside* the region path; it does not touch the
split predicate or the plain copy.** Verified stable at all three refs:

| Mechanism we depend on | Status |
|---|---|
| non-region/region split on `region_col` blank/`ignore` (`copy_files.py:91-109`) | byte-identical at both upstream refs |
| `{cepmtgcapscen}` substitution — `row['filepath'].format(**sw)` | present at all three refs |
| our rows falling through to `shutil.copy` (blank `GAMStype`) | holds at both |
| `runfiles.csv` 16-column schema | unchanged; only col 15 renamed `comment`→`GAMScomment` at `main`, and our rows leave it empty |
| `eq_interconnection_queues` (our template *and* our insertion anchor) | byte-identical at `upstream/main` |
| `cap_new_out` (what D7 aligns against) | byte-identical at `upstream/main` |
| `ilr(i)$[valcap_i(i)] = 1` — the premise of the ilr guardrail | still present (`b_inputs.gms:3359` at `main`) |
| `$include inputs_case%ds%*.csv` list-parameter idiom | intact; `growth_limit_absolute` still uses it at `main` |
| every GAMS symbol the equations use — `valinv`, `valcap`, `tg_i`, `refurbtech`, `Sw_Refurb`, `Sw_Upgrades`, `Sw_PCM`, `upgrade_derate`, `UPGRADES`, `UPGRADES_RETIRE`, `INV_REFURB`, `tmodel`/`tfix` | all survive |
| `tg.csv`; the `tech-subset-table.csv` columns `make_tg_cap.py` reads | unchanged / all present |
| `reeds.techs.import_tech_groups`, `reeds.io.write_gswitches` | unchanged |
| `reeds.io.read_output` | cosmetic only (`Path(case).suffix` vs `case.endswith`) |
| `reeds.spatial.upscale_from_county_to_zone` | functionally identical at `main` — so §5.1's rationale does not go stale either |

**The structural reason this is robust,** beyond the line-by-line check: the cap
file is harvested from a finished run *at that run's own resolution* and consumed
against the same `r` set the model solves on. Whatever upstream does to
county→zone mapping, the ceiling and the quantity it constrains move together. We
are only exposed to a change in how a file gets from `inputs/` to `inputs_case/`,
which is the plain-copy path — the least likely part to change, and unchanged so
far.

**Three things to watch at rebase time (none of them correctness risks):**

1. **`b_inputs.gms` churn — merge conflicts, not breakage.** 1,210 lines touched
   between our base and `upstream/main` (net −985), so both of our insertion
   points will likely need re-placing by hand. `c_model.gms` is far calmer (164
   lines) and our anchor is identical, so that half should apply cleanly.
2. **Upstream is migrating `$include` CSV parameters into `inputs.h5`.**
   `GAMStype=parameter` rows in `runfiles.csv` went 1 → 1 → **11** across
   `2026.06.18` → `2026.08.03` → `main`, with `write_non_region_file` now routing
   `GAMStype in ['set','parameter']` to `write_csv_to_inputs_h5`. That is where
   the deleted `b_inputs.gms` lines went. The growth-constraint parameters have
   not been migrated, so our block is still idiomatic. If the migration completes,
   converting is mechanical — fill `GAMStype`/`GAMSname` on our two rows and drop
   the `$include` block — and it would hit every comparable upstream file at the
   same time.
3. **Pre-existing fork divergence in the same file.** Our `copy_files.py` is
   *unmodified* from `2026.06.18`, but that version's `read_runfiles` carries
   `{lvl}` multi-resolution machinery that upstream **removed** by `2026.08.03`.
   Not our change and not our problem to fix, but it lands in the same function
   we reasoned about above, so expect it in the rebase diff. The placeholder
   mechanism our rows rely on (`format(**sw)`) survives the removal.

Minor tidy, optional: our two rows sit at lines 3-4 of `runfiles.csv` rather than
with the other `growth_constraints` rows near line 99. That breaks the file's
grouping convention, though it is arguably *safer* for rebasing since upstream's
churn is all in the body.

---

## 9. Suggested build order

1. ~~**T0.** Confirm F1 and close D1.~~ **Done 2026-09-01 — F1 confirmed, D1
   closed in favor of §4.** Evidence in
   `runs/v20260901t0_WECC-SW_t0growthcon/` (gitignored; `gamslog.txt` around the
   `Row 'eq_growthlimit_absolute(PV,2032)' infeasible` line, and
   `lstfiles/*_2032i0.lst`).
2. ~~GAMS + plumbing (§4, §5.1) with `GSw_CEPM_TgCap=0` everywhere; run
   **T2**.~~ **Done 2026-09-01 — T2 passes byte-identically.** Evidence in
   `runs/v20260901t2b_WECC-SW_baseline` vs `runs/v20260824-2_WECC-SW_baseline`.
   Two deviations from what §4/§5.1 originally specified, both now folded back
   into those sections: the regional symbol is a long-format `parameter`, not a
   `table`, and both `runfiles.csv` rows are non-region rows.
3. ~~`make_tg_cap.py` (§5.3); run **T1** against the archived baseline — no ReEDS
   run needed.~~ **Done 2026-09-01 — T1 passes, 18/18.** Note the test itself was
   never committed; it needs rewriting as a file before it can serve as the
   post-rebase regression check T10 assumes. Same for the T0 standalone GAMS
   reproduction (suggested home `CEPM/scripts/t0_growthgap.gms`).
4. ~~Wire `_limitre` by hand (write the cap CSVs manually, set the switches); run
   **T3**, then **T4**/**T4r**.~~ **Done 2026-09-01 — T3, T4, T4r all pass.**
   Evidence in `runs/v20260901t3_*` and `runs/v20260901t4b_*`. **T5(a)-(c) done
   2026-09-02/03; T5(d) remains blocked on region choice** — see §7.
5. ~~`run_cepm.ps1 -m` (§5.4); run **T6**, **T7**, **T8**.~~ **Done 2026-09-02 —
   T6, T7, T8 and T9 all pass.** Also added: `CEPM/scripts/multistep_cases.py`,
   the three `cases_cepm.csv` case columns, and `--harvest-args`.

   The two `run_cepm.ps1` arg-plumbing bugs found while running T4 turned out to
   affect only *caller-supplied* arguments, not what `-m` builds for itself: `-r`
   is a unique prefix of the script's own `$RunbatchArgs` parameter, so PowerShell
   binds it there and the *next* flag fails with a confusing "parameter not
   found"; and `--simult_runs 1` fails separately with argparse reporting
   `unrecognized arguments: 1`. Arguments the script assembles into an array
   itself bypass that binder entirely, which is what lets `-m` pass
   `--simult_runs 2` to phase B — see §5.4 "As built" for why phase B *needs* it.
   For a plain (non-`-m`) invocation, the pattern that works is still one case per
   invocation via `-s <single>`, which sets `WORKERS=1` with no prompt.
6. ~~Docs: correct the CEPM recommendation in `tech-limit-options.md` (F1/F2),
   add an F1 entry to `CEPM/known-reeds-issues.md`, and write the
   `CEPM/reeds-to-cepm-log.md` inventory rows + section.~~ **Done** — the first
   two 2026-09-01, the divergence-log entry 2026-09-02 (5 inventory rows and a
   "Cumulative tech-group investment caps" section carrying D8's non-region
   `runfiles.csv` decision and its post-rebase checks).
7. Rebase onto 2026.08.03, then **T10**.

### Housekeeping — resolved 2026-09-03

All three open items were decided and applied before the first commit.

- **Test scaffolding deleted (17 files).** `cases_t{3,4,5}.csv` and
  `cepm_tg_cap_{sys,reg}_{t3,t4,t4ra,t4rb,t4rc,t5a,t5c}.csv` are gone. Only the
  `_none` pair is committed; under §5.2b every real ceiling is generated per
  batch and deleted in a `finally`, so a committed hand-made ceiling is an
  invitation to pick up a stale one. (`cepm_tg_cap_sys_t5c.csv` in particular
  contained a deliberately **invalid** tech group and would fail any run
  selecting it.) T10's post-rebase T3 re-run has to re-harvest its ceiling from
  the post-rebase baseline anyway, so only the case definition was reusable and
  that is an `awk` one-liner to rebuild.
- **`cleanup_level` stays at 0** — this is now a deliberate decision, not test
  residue. `runreeds.py:959-967` blocks on
  `input('Proceed? y/[n]: ')` (default `n`, so it quits) whenever **any** case
  has `cleanup_level >= 1` and `--skip_checks` was not passed. Two details make
  that specifically dangerous for `-m`: the check runs at launch, before anything
  starts; and because `-m` always uses `-s`, ignored cases are **not** dropped
  from `df_cases` first (`runreeds.py:899-905`), so the check scans *every*
  column in the file — including the ten this batch is not running. One stray
  `cleanup_level=2` anywhere in `cases_cepm.csv` therefore hangs a background
  `-m` run on a prompt nobody can see. Recorded as a comment in `run_cepm.ps1`.
- **`WECC-SW_dcload` removed**, resolving the duplication in favour of the
  documented convention. `WECC-SW_optimized` was an exact copy of it — the same
  scenario under two names, because §1's naming needs an `_optimized` and
  `_dcload` predates it. `WECC-SW_dcloco2` is unaffected (it is an independent
  column, not derived from `_dcload`), and completed runs under the old name are
  untouched.

- **SERTP two-step columns added 2026-09-03**, mirroring WECC-SW:
  `SERTP_{limitre,optimized}` appended from `SERTP_dcload`'s config, and
  `SERTP_dcload` then removed for the same duplication reason. Both stems now
  validate for `-m`. The remaining stems (`NM_*`, `USA_*`) do not have two-step
  columns, and `-m` refuses with a message naming the missing ones.

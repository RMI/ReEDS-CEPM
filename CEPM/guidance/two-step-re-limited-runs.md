# Two-step baseline-constrained runs (`*_baseline` → `*_limitre` + `*_optimized`)

**Status:** built and merged (PR #49), carried through the 2026.08.03 sync.
Outstanding: **T10** (re-run T2/T3 post-sync on a current stem). Results below
come from the former `WECC-SW`/`SERTP` cases (removed in #55) and pre-date the
fix for Texas load landing in `p59`, which inflates the T9 figures (see
[`batch-log.md`](../batch-log.md) and
[`loadsite-mechanism.md`](loadsite-mechanism.md)). One command produces the
three-case factorial and its comparison deck:

```powershell
.\run_cepm.ps1 -y -x -b <batch> -c cepm -m st-AZNM
```

**Scope:** a `run_cepm.ps1` mode that runs a CEPM case in two phases — first a
`*_baseline` ReEDS run, then a pair of data-center-load runs where one
(`*_limitre`) is capped at the baseline's own wind/solar/storage buildout and
the other (`*_optimized`) is free — including the ReEDS-side plumbing needed to
inject a per-batch capacity ceiling and the tests that prove it works.

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

**Decisions (all closed):** D1 purpose-built equations, closed by T0 (§6);
D2 both scopes, switchable (§4); D3 cumulative gross builds from 2026 (§6);
D4 wide group list — `pv`, `wind-ons`, `wind-ofs`, `csp`, `battery`,
`pumped-hydro` — at 100% (§5.3); D5 generated cases file (§5.2b); D6 hard cap,
no slack; D7 `INV + INV_REFURB + UPGRADES − UPGRADES_RETIRE`; D8 non-region
`runfiles.csv` rows (§5.1).

---

## 1. What we're building

Given a CEPM case stem (`st-AZNM`, `st-MSALGA` or `VA` today), three case
columns in `cases_cepm.csv`:

| Case | Data-center load | RE ceiling | Purpose |
|---|---|---|---|
| `<stem>_baseline` | off | none | counterfactual; source of the ceiling |
| `<stem>_limitre` | on | wind/solar/storage capped at baseline buildout | "what if new load can't lean on new RE" |
| `<stem>_optimized` | on | none | "what the optimizer would actually do" |

`<stem>_limitre` and `<stem>_optimized` differ **only** in the ceiling, and
`<stem>_optimized` differs from `<stem>_baseline` **only** in the load. That
clean factorial is the whole point, and it constrains several decisions below —
in particular it rules out reusing any mechanism that is already active in the
baseline (see F4).

---

## 2. Orchestration shape

`runreeds.py` gives us everything we need:

- `--single/-s` takes a **comma-delimited list** of case names and overrides the
  `ignore` row for exactly those cases (`runreeds.py`: `create_case_lists`,
  `setupEnvironment`, and the `--single` argument in `main`).
- On Windows a case is launched with `os.system('start /wait cmd /c ...')`
  (`runreeds.py`, `launch_single_case_run`), and the worker pool joins, so
  `runreeds.py` **blocks until the whole batch finishes**. `run_cepm.ps1` already relies on this
  (`Invoke-Native { uv run python runreeds.py @ForwardArgs }`), so sequencing
  two invocations needs no new waiting logic.
- Run folders are `runs/{BatchName}_{case}`, so both phases can share one batch
  name and `compare_cases.py "runs/{BatchName}_"` picks up all three cases.

So the flow is:

```
Phase A   runreeds.py -b BATCH -c cepm -s <stem>_baseline
          └── blocks until runs/BATCH_<stem>_baseline/outputs/outputs.h5 exists
Harvest   CEPM/scripts/make_tg_cap.py  (reads phase A outputs → writes cap CSV)
Phase B   runreeds.py -b BATCH -c <generated> -s <stem>_limitre,<stem>_optimized --simult_runs 2
          └── blocks until both finish
Compare   postprocessing/compare_cases.py "runs/BATCH_"      (existing -x path)
Cleanup   delete the generated cap CSV + generated cases file (always, in finally)
```

Phase A must hard-fail the whole invocation if `outputs.h5` is missing — a
ceiling harvested from a partial run is worse than no run at all.

---

## 3. Four findings that shape the design

Each of these was checked against the code in this fork and, where possible,
against `runs/v20260824-2_WECC-SW_baseline`.

### F1 — `eq_growthlimit_absolute` goes **infeasible** in the final solve year

The equation's allowance is the gap to the *next* modeled year (via `tprev`).
In the last modeled year there is none, so the left-hand side collapses to
`-yeart(t) * growth_limit_absolute(tg)` and the row is infeasible, not merely
restrictive; `yearweight` uses the same expression but patches the last year.
CEPM cases end at 2032, so `GSw_GrowthConLastYear=2032` puts the equation in the
final year. T0 confirmed this on 2026-09-01, in a standalone GAMS reproduction
and in a live run (2026/2029 Optimal, 2032 Infeasible, with CPLEX's conflict
refiner isolating `eq_growthlimit_absolute(PV,2032)`). **D1 is therefore closed
in favor of §4.** Full write-up:
[`known-reeds-issues.md`](../known-reeds-issues.md#gsw_growthabscon1-makes-the-final-solve-year-infeasible-eq_growthlimit_absolute).

### F2 — `growth_limit_absolute(tg)` has no year index, and CEPM baselines are extremely lumpy

The parameter is `growth_limit_absolute(tg)` — one MW/year number per tech
group, no `t` (`b_inputs.gms`). The constraint is therefore a
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
`cap_new_out = INV / ilr(i)` (`cap_new_out` in `report.gms`), and `ilr(i) =
ilr_utility = 1.34` for UPV (the `ilr` assignments in `b_inputs.gms`;
`ilr_utility` in `inputs/scalars.csv`). PVB gets its own ILR (`ilr_pvb_config`).
Wind and battery are 1.0.

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
penalized slack `CAP_ABOVE_LIM` (`eq_interconnection_queues` in
`c_model.gms`; the `cap_penalty * CAP_ABOVE_LIM` term in `d_objective.gms`).
Overwriting `cap_limit.csv` with a policy ceiling would therefore change a constraint that is *already doing work* in the baseline,
breaking the clean factorial in §1.

Second, `cap_limit.csv` is computed directly in `copy_files.py` (`write_miscellaneous_files`) from
`inputs/capacity_exogenous/interconnection_queues.csv` with no scenario switch,
so making it case-specific means editing `copy_files.py` — the single
most-churned file in the 2026.08.03 release (568 lines changed). That is
the worst possible place to put a fork hook.

Corollary, worth noting independently of this project: because the shipped queue
data only extends to 2030, `sum{(tgg,rr), cap_limit(tgg,rr,'2032')}` is zero and
the queue constraint **switches itself off entirely in 2032** in every CEPM run
today.

Followed up in depth, including the size of the penalty and why F4's conclusion
still holds, in
[`interconnection-queue-and-prescribed-builds.md`](interconnection-queue-and-prescribed-builds.md).

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

**c_model.gms** — two lines in the equation declaration block (next to
`eq_interconnection_queues`'s declaration) and one block immediately after the
`eq_interconnection_queues` definition:

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
(`growth_limit_absolute`):

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
   `ilr(i)`; every investable tech is assigned `ilr = 1`
   (`ilr(i)$[valcap_i(i)] = 1` in `b_inputs.gms`), so this should be unreachable — but a division by zero would corrupt the
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

### Why this and not a patched `GSw_GrowthAbsCon`

| | patch Option 3 | new equation |
|---|---|---|
| Upstream lines *edited* | 2 (both inside an upstream equation) | 0 — everything additive |
| Fixes F1 | needs a `tlast` fallback | n/a — cumulative, no gap arithmetic |
| Fixes F2 | **cannot** — no `t` index on the parameter | n/a — cumulative by construction |
| Fixes F3 | no — bounds `INV` in MW_dc | yes — `/ ilr(i)` puts it in MW_ac |
| Can exclude prescribed 2026 builds | needs a *third* patch (no first-year floor exists) | `Sw_CEPM_TgCapStartYear` |
| Model statement | n/a | none needed — `Model ReEDSmodel /all/` (`e_solveprep.gms`) |
| Rebase risk | edits lines upstream may touch | additive block; conflicts only on adjacent edits |

`Sw_CEPM_TgCap` and `Sw_CEPM_TgCapStartYear` need **no GAMS plumbing at all**:
`reeds.io.write_gswitches` auto-emits `scalar Sw_X`
for every numeric `GSw_X` in the cases file.

**No slack variable is proposed.** ReEDS already has unserved-energy slack, so a
binding RE ceiling should push the model to gas or to load-shedding rather than
to infeasibility. If a run does go infeasible we want to know, not to quietly
pay a penalty. If that proves wrong in practice, the fallback is a penalized
`CEPM_CAP_ABOVE(tg)` slack, which costs one extra line in `d_objective.gms` —
see D6.

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

An earlier draft used `region_col=r, aggfunc=sum, fix_cols=tg, wide=1`. That puts
the file through `reeds.spatial.upscale_from_county_to_zone`, which maps regions
through a county index and would silently empty a cap harvested at model
resolution; the plain-copy path instead fails loudly (a GAMS domain error) if the
region set doesn't match. Full reasoning:
[`reeds-to-cepm-log.md`, "Departure from convention"](../reeds-to-cepm-log.md#departure-from-convention-worth-knowing-both-rows-are-non-region-rows).

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
while `copy_files.py` was substantially rewritten.

### 5.2 Getting the generated file to the `_limitre` case only

The generated cap file is per-batch, but `cepmtgcapscen` lives in a git-tracked
cases file. Two options:

- **(a) Fixed token** (a permanent `cepmtgcapscen,cepm_auto`) — rejected,
  because two batches running phase B concurrently would clobber each other's ceiling.
- **(b) Generated cases file (recommended).** The orchestrator reads
  `cases_cepm.csv` with `reeds.inputs.parse_cases` (signature unchanged in
  2026.08.03), substitutes
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
3. Build the `i → tg` map by mirroring the `tg_i` assignments in `b_inputs.gms` on the **run's own**
   `inputs_case/tech-subset-table.csv`, expanded through
   `reeds.techs.import_tech_groups` (which handles the
   `upv_1*upv_10` GAMS range syntax — a plain `pd.read_csv` does not):
   - `pv` ← (`UPV` ∪ `PVB`) − `distpv`
   - `wind-ons` ← `ONSWIND`
   - `wind-ofs` ← `OFSWIND`
   - `csp` ← `CSP` (plus the non-numeraire CSP classes when `GSw_WaterMain` is
     on — the `Sw_WaterMain` line of `tg_i`; CEPM cases run with it off today, so flag
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

For the former WECC-SW baseline above, `--scope system --from-year 2026 --to-year 2032`
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
2. Phase A: `runreeds.py -b $BatchName -c $CasesSuffix -s "${stem}_baseline"`.
   Non-zero exit or missing `outputs.h5` → throw (and ntfy).
3. Harvest: `uv run python CEPM/scripts/make_tg_cap.py ...`.
4. Write the generated cases file (§5.2b).
5. Phase B: `runreeds.py -b $BatchName -c <generated> -s "${stem}_limitre,${stem}_optimized" --simult_runs 2`.
6. Existing `-x` comparison path, unchanged — `compare_cases.py "runs/$BatchName_"`
   picks up all three and defaults its base to the alphabetically-first completed
   case, which is `_baseline`.
7. `finally`: delete the generated cap CSV and cases file; warn, never throw.

**Hazard — `runreeds.py` exits 0 on a failed case** (found running T0). Phase A
therefore verifies `runs/<Batch>_<stem>_baseline/outputs/outputs.h5` exists
before harvesting, and `make_tg_cap.py` fails loudly if it doesn't (§5.3 step 1).
See [`known-reeds-issues.md`, "`runreeds.py` reports success on a failed case…"](../known-reeds-issues.md#runreedspy-reports-success-on-a-failed-case-and-hangs-on-a-multi-case--s).

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

**Hazard — phase B hangs without an explicit worker count** (same
[known-issues entry](../known-reeds-issues.md#runreedspy-reports-success-on-a-failed-case-and-hangs-on-a-multi-case--s), symptom 2). `-m` therefore passes
`--simult_runs 2` itself unless the caller supplied one; arguments the script
builds itself are not affected by the PowerShell `-r` binding trap described
there. Forward `--simult_runs 1` to run the two phase-B cases sequentially
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
  cannot follow a lumpy baseline (F2).
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
  (the `upgrade_to` assignment of `i_subsets` in `b_inputs.gms`) and
  `upgrade_link.csv` contains `hydED → pumped-hydro`. With `GSw_Upgrades` defaulting to 1, a storage ceiling
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
  a `table` (§4). What to re-check in new releases is in
  [`reeds-to-cepm-log.md`](../reeds-to-cepm-log.md#cumulative-tech-group-investment-caps-gsw_cepm_tgcap) ("What to test in new releases").

---

## 7. Test plan

Ordered so that the cheapest disqualifying test runs first.

**T0 — confirm F1 before building anything. This is D1's decision gate.**
Two parts:

- *Part 1, standalone (0.3 s).* A GAMS file replicating the `tprev` definitions
  in `b_inputs.gms` and the `eq_growthlimit_absolute` LHS over the CEPM solve-year set, solved as a
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
closed.**

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

**Includes the Texas→`p59` load error; re-run before quoting.**

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

**T10 — post-sync. NOT YET RUN.** Re-run T2/T3 on a current stem (e.g. `st-AZNM`).

---

## 8. Sync checks

See [`sync-log.md`](../sync-log.md) and
[`reeds-to-cepm-log.md`](../reeds-to-cepm-log.md#cumulative-tech-group-investment-caps-gsw_cepm_tgcap) ("What to test in new releases").

---

## 9. Remaining work

Remaining: T10. The T1 test and T0 GAMS file were never committed; write them as
files before T10.

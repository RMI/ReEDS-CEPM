# Options for restricting a technology's capacity in ReEDS

**Scope:** the range of mechanisms available for constraining a single
technology (e.g. biopower, solar, wind) in a ReEDS run — from a full ban, to a
new-build-only ban, to a soft cost penalty, to a hard cumulative ceiling — and
what each implies for existing capacity, solvability, and reporting.

**Short version:** ReEDS already contains four distinct mechanisms that cover
most of this design space (`ban`/`bannew`, growth-rate constraints, the
interconnection-queue cumulative cap, and cost-multiplier penalties), and this
fork adds a fifth (a purpose-built cumulative cap by tech group — see the CEPM
recommendation section). Which one is right depends on a question that is easy
to skip past: do you want to guarantee a hard limit, or discourage the
technology and let the model decide? Only some of the options below can actually
promise the former.

> **Correction, 2026-09-01.** An earlier version of this doc recommended
> `GSw_GrowthAbsCon` with `GSw_GrowthConLastYear` set to the case's `endyear` as
> the CEPM answer for non-RSC techs. That configuration makes the final solve
> year **infeasible** — confirmed both in a standalone GAMS replication and in a
> live `WECC-SW_baseline` run. See the ⚠️ block in Option 3 and the withdrawn
> recommendation below. If you acted on the old advice, that's the cause.

## The core distinction: `ban(i)` vs `bannew(i)`

`reeds/core/setup/b_inputs.gms` declares both sets side by side, with the
distinction spelled out in a comment right above them (`b_inputs.gms:102-106`):

```gams
sets
*The following two sets:
*ban - will remove the technology from being considered, anywhere
*bannew - will remove the ability to invest in that technology
  ban(i) "ban from existing, prescribed, and new generation -- usually indicative of missing data or operational constraints"
```

- **`ban(i)`** removes the technology from `valcap` entirely, including
  existing/prescribed capacity (`b_inputs.gms:2118-2119`, comment: *"existing
  plants are enabled if not in ban(i)"*). This is what `GSw_Biopower` and
  `GSw_OfsWind` use (`b_inputs.gms:422-424`, `545-547`). A tech under `ban` does
  not exist in the model at all in that run — no capacity, no generation, in
  any solve year.
- **`bannew(i)`** only blocks new vintages (`b_inputs.gms:2134`,
  `2141`, `2164`); existing/prescribed capacity stays in `valcap` and keeps
  operating. `GSw_OnsWind6to10` uses this to freeze out new builds of specific
  onshore wind resource classes while leaving existing turbines alone
  (`b_inputs.gms:549-554`).

**Implication:** if the intent is "no new investment, but don't touch what's
already built," `bannew` is correct and `ban` is a mistake — using `ban` will
retire existing capacity out of the model, which is a much bigger behavioral
change than most "turn off new X" requests actually want.

## Option 1 — Resource supply curve ceiling (RSC techs only)

Solar (UPV, DistPV), wind (onshore, offshore), geothermal, and PSH are all
`rsc_i(i)` technologies, gated by `m_rscfeas`, which in turn requires nonzero
resource in `rsc_dat(i,r,"cap",rscbin)` (`b_inputs.gms:1647`, `2141`). The
supply curve *is* a ceiling already — it represents the physical resource
available to build against.

**How to use it as a policy ceiling:** edit the resource supply curve input
CSVs so the bins sum to your target instead of the full physical potential.
This is a **data-only change** — no GAMS edits required.

**Implications:**
- Only works for `rsc_i` technologies. Gas, batteries, nuclear, etc. have no
  supply curve to shrink.
- The ceiling is enforced per region/bin, so hitting a specific national total
  means allocating it across regions yourself — there's no single knob for
  "50 GW nationally, distributed however the model likes."
- Because it's the same mechanism as physical resource scarcity, anything
  reading the supply curve for other purposes (reporting resource potential,
  reV integration) will see the same edited numbers. Don't reuse this file if
  something else depends on it representing true physical potential.

## Option 2 — Interconnection queue cumulative cap (closest fit for a hard ceiling)

`eq_interconnection_queues(tg,r,t)` (`c_model.gms:1385-1403`) already
constrains cumulative new investment by tech group and region against a
data-driven limit:

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

`cap_limit(tg,r,allt)` is loaded from `inputs_case/cap_limit.csv`
(`b_inputs.gms:2014-2020`). Repurposing this table to encode a policy ceiling
(rather than actual queue data) is a **data-only change**, and it already
handles cumulative investment, by tech group, by region — no new equation
needed.

**The catch: it is a soft constraint by design.** `CAP_ABOVE_LIM(tg,r,t)` is a
penalized slack variable, not a hard bound — the objective charges
`cap_penalty(tg) * CAP_ABOVE_LIM(tg,r,t)` (`d_objective.gms:47`) rather than
making violation infeasible. That's intentional: a hard `=g=` with no slack
would make the model infeasible any time the queue data and reality diverge.
Two consequences:

- With `cap_penalty(tg)` at whatever value ships with the queue data, the
  "ceiling" can be exceeded if the alternative is expensive enough. To make it
  effectively hard, fix `CAP_ABOVE_LIM.up(tg,r,t) = 0` for your target group
  (or set `cap_penalty(tg)` very high, which is a softer version of the same
  idea and easier to reason about numerically).
- `tg` groups techs coarsely (all UPV + PVB is one `'pv'` group, for example —
  see `tg_i(tg,i)` at `b_inputs.gms:793-810`). If your ceiling needs to apply
  to a narrower slice than the existing groups, see the `tg` customization
  section below.

**Not actually case-customizable in this fork today.** The "data-only change"
framing above is true for editing the file once, repo-wide — it is not true
per-case. `copy_files.py:1404-1433` computes `cap_limit.csv` directly from
`inputs/capacity_exogenous/interconnection_queues.csv` (real interconnection
queue data), reading the source via `reeds_path` rather than the case
directory, with no scenario switch and no corresponding row in
`reeds/input_processing/runfiles.csv`. That means:

- It can't be parameterized by a `cases_cepm.csv` switch the way `distpvscen`
  or `GSw_SitingUPV` parameterize their files.
- It can't be swapped per case via `file_replacements` either — that
  mechanism only substitutes files already staged under `casedir/reeds/...`
  by the time it runs (`runreeds.py:1249-1274`), and `cap_limit.csv`'s source
  never passes through there.

Repurposing this option for a policy ceiling today means editing the shared
queue-data CSV for every case that reads it, or adding new plumbing (a
scenario switch plus a `runfiles.csv` row) — meaningfully more work than "edit
a CSV," and out of scope for a single-case ask. See the CEPM-specific
recommendation below for what to reach for instead when the ceiling needs to
vary by case.

## Option 3 — Growth-rate constraints (not a ceiling — a pace limiter)

`GSw_GrowthAbsCon` / `GSw_GrowthPenalties` (`cases.csv:153-156`) drive
`eq_growthlimit_absolute(tg,t)` and `eq_growthlimit_relative(i,st,t)`
(`c_model.gms:1088-1102`, `1048-1075`). These bound **MW added per year**, not
cumulative capacity:

```gams
eq_growthlimit_absolute(tg,t)$[growth_limit_absolute(tg)$tmodel(t)
                               $Sw_GrowthAbsCon$(yeart(t)<=Sw_GrowthConLastYear)
                               $(yeart(t)>=model_builds_start_yr)
                               $(not Sw_PCM)]..
     (sum{tt$[tprev(tt,t)], yeart(tt) } - yeart(t)) * growth_limit_absolute(tg)
     =g=
     sum{(i,v,r)$[valinv(i,v,r,t)$tg_i(tg,i)], INV(i,v,r,t) } ;
```

**Implication:** a technology under this constraint can still grow without
bound given enough years — it slows the ramp, it does not cap the total. Also
note both switches default to `0` (off) and, where they're used elsewhere in
this repo, carry near-term end years (`GSw_GrowthConLastYear` default 2026,
`GSw_GrowthPenLastYear` default 2034) — they're built for near-term
transition-pace realism, not permanent limits. Don't reach for this if the ask
is "never exceed X GW"; reach for it if the ask is "don't let X grow faster
than Y per year."

**⚠️ CEPM-specific trap: setting `GSw_GrowthConLastYear` to the run's `endyear`
makes the final solve year infeasible.** This section previously recommended
exactly that; it is wrong, and the correction is important enough to state
before anything else about Option 3.

The equation's allowance is the gap to the **next** modeled year. `tprev(t,tt)`
means "tt is the year before t" (`b_inputs.gms:1027`, `1053-1055`), so
`tprev(tt,t)` in the equation selects the year *after* `t`. For the last
modeled year no such `tt` exists, the sum collapses to 0, and the coefficient
becomes `-yeart(t)` — a large negative number required to be `=g=` a
non-negative sum of `INV`. There is no slack variable, so the solve is
infeasible, not merely tight.

`yearweight` uses the identical expression and then explicitly patches the last
year (`b_inputs.gms:5573-5574`); `eq_growthlimit_absolute` never got that patch.
The bug is latent upstream (confirmed still present at tag `2026.08.03`) only
because `GSw_GrowthConLastYear` defaults to 2026 while runs end in 2050, so the
equation is never generated in the final year.

**Confirmed empirically, 2026-09-01**, on `WECC-SW_baseline`'s exact
configuration plus `GSw_GrowthAbsCon=1`/`GSw_GrowthConLastYear=2032`
(`runs/v20260901t0_WECC-SW_t0growthcon`): 2026 and 2029 solve to
`MODEL STATUS 1 Optimal`, 2032 returns `MODEL STATUS 4 Infeasible`, and CPLEX's
conflict refiner isolates it to a single row —

```
Row 'eq_growthlimit_absolute(PV,2032)' infeasible, all entries at implied bounds.
Number of equations in conflict: 1
  lower: eq_growthlimit_absolute(PV,2032) > 5.80786e+07
```

5.80786e+07 = 2032 × 28,582, i.e. the year number times the shipped `pv`
MW/year limit. Full writeup in
[`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) (finding F1) and
[`../known-reeds-issues.md`](../known-reeds-issues.md).

**The workaround: a sacrificial final solve year.** Because the coefficient only
needs *some* later modeled year to exist, extending the run one solve period past
the last year you care about restores a positive gap:

| solve years | 2010 | 2026 | 2029 | 2032 |
|---|---:|---:|---:|---:|
| `2010,2026,2029,2032` (`endyear=2032`) | 16 | 3 | 3 | **−2032** |
| `2010,2026,2029,2032,2035` (`endyear=2035`) | 16 | 3 | 3 | **3** |

Concretely: set `yearset=2026..2035..3` and `endyear=2035`, leave
`GSw_GrowthConLastYear=2032`, and truncate reporting at 2032. Costs one extra
solve year (plus its Augur/PRAS pass — roughly a third more solve time on a
3-build-year CEPM case).

**⚠️ The sacrificial year is not a free no-op on the years you do report.**
Adding a later solve year changes the *last reported* year's investment
decisions, because that year is no longer the model's terminal year and loses
its end-of-horizon effects. Measured directly — two runs at the same commit,
identical except for the horizon (`runs/v20260901t2_WECC-SW_baseline` at
`endyear=2032` vs `runs/v20260901t0b_WECC-SW_t0bsacrificial` at `endyear=2035`),
with the growth constraint slack in both so it isn't the cause:

| gross new builds (MW_ac) | 2026 | 2029 | 2032 |
|---|---:|---:|---:|
| pv | 0.0% | +0.1% | +0.2% |
| wind-ons | 0.0% | 0.0% | **−4.6%** (9,531 → 9,089) |
| battery | 0.0% | 0.0% | **−5.4%** (530 → 502) |

Earlier years are untouched; the final reported year moves by several percent.
So "add a throwaway year" is really "accept a perturbed final year" — fine for a
sensitivity, not fine if 2032 capacity is the headline number, and definitely
not fine if you are comparing a sacrificial-year run against a non-sacrificial-year
one. If you use this workaround, use it for *every* case in the comparison.

**Confirmed live, 2026-09-01** (`runs/v20260901t0b_WECC-SW_t0bsacrificial`): the
same `WECC-SW_baseline` configuration that failed above, changed only by
`yearset=2026..2035..3`/`endyear=2035`, solves **2032 to `MODEL STATUS 1
Optimal`**. The constraint is genuinely live rather than silently dropped — both
runs generate exactly 3 `eq_growthlimit_absolute` rows in their 2032 solve (one
each for `pv`, `wind-ons`, `battery`, the three groups with nonzero limits in
`growth_limit_absolute.csv`):

```
t0  (endyear 2032):  Equation eq_growthlimit_absolute  ...  3   -> 2032 Infeasible
t0b (endyear 2035):  Equation eq_growthlimit_absolute  ...  3   -> 2032 Optimal
```

Same equation, same row count, only the year-gap coefficient differs. At the
shipped MW/year limits the constraint is non-binding for WECC-SW (2032 onshore
wind builds 9,531 MW against a 3 × 8,854 = 26,562 MW allowance), so the
sacrificial-year run reproduces the ordinary baseline through 2032.

**But the workaround only fixes the infeasibility, not the fitness for purpose.**
Three limitations remain, and together they are why CEPM's baseline-constrained
work did *not* end up using Option 3:

1. **No year index.** `growth_limit_absolute(tg)` is a single MW/year number per
   tech group (`b_inputs.gms:4804`) — the constraint is necessarily a *constant
   annual pace*. Real CEPM baselines are extremely lumpy: the WECC-SW baseline
   builds 200 MW of onshore wind in 2029 and 9,531 MW in 2032. A flat rate sized
   to that total allows 4,866 MW per solve year, which would cap a scenario
   *below the very baseline it was derived from*. No amount of tuning fixes this;
   the parameter cannot express a lumpy target.
2. **Unit mismatch.** The constraint bounds `INV`, which for UPV is MW_dc, while
   every reported capacity output is MW_ac (`cap_new_out = INV / ilr(i)`,
   `report.gms:820-825`; `ilr_utility = 1.34`). A limit derived from reported
   capacity and applied without conversion under-caps solar by 34%.
3. **No first-year floor.** The constraint's lower year bound is
   `model_builds_start_yr`, with no switch to raise it, so it also applies to the
   first build year — where CEPM cases carry large *prescribed* builds the model
   has no choice about. With no slack variable, a limit tight enough to be
   interesting risks making that year infeasible too.

Also note the equation is national-only in its indexing (no `r` term, just
`tg,t`). For a subnational case that's harmless — the sum only runs over
whatever regions are in the model, so it naturally becomes the run's total — but
it means Option 3 cannot express a per-region ceiling at all.

**When Option 3 is still the right tool:** when you genuinely want a pace limit
("don't let X grow faster than Y MW/year"), on a run whose horizon extends past
`GSw_GrowthConLastYear` so the final-year trap never fires. That is what it was
built for. It is not a cumulative ceiling, and the short-horizon equivalence
argument this section used to make does not survive contact with the final-year
bug or with lumpy build profiles.

## Option 4 — CAPEX/cost multiplier (discourage, don't cap)

`GSw_NukeStateBan` (`cases.csv:240`) already implements this as a selectable
mode alongside a hard ban:

```
GSw_NukeStateBan,Switch to limit nuclear with state bans. [0] off / [1] full ban / [2] cost multiplier,0; 1; 2,1,
```

Mode 1 is a hard `valcap` exclusion (`b_inputs.gms:2280-2282`); mode 2 instead
inflates `cost_cap_fin_mult(i,r,t)` (`2_financials.gms:93-97`):

```gams
if(Sw_NukeStateBan = 2,
  cost_cap_fin_mult(i,r,t)$[nuclear(i)$nuclear_ba_ban(r)] =
    cost_cap_fin_mult(i,r,t) * nukebancostmult ;
```

Applying the same pattern to solar or wind — a new multiplier keyed off
`pv(i)`/`wind(i)` — is mechanically simple by analogy.

**Implication — the important one:** this is a soft lever, not a ceiling. No
finite multiplier can *guarantee* a capacity stays under some GW target; it can
only make the technology less attractive relative to alternatives. The model
will still build past whatever informal target you had in mind if everything
else is pricier in some region/year (transmission-constrained pockets,
reliability-driven builds, resource scarcity elsewhere). Hitting a specific
number with this approach means iterating the multiplier and re-solving, not
setting a value once. Use this when the goal is "discourage" or "represent a
soft policy headwind," not when the goal is "guarantee ≤ X GW."

## Customizing `tg` (tech groups)

Both the growth constraints and the interconnection-queue cap operate on `tg`,
which groups technologies more coarsely than individual `i` — e.g. all UPV and
PVB (minus DistPV) collapse into one `'pv'` group (`b_inputs.gms:796`). If an
existing group is too coarse for what you want to cap, `tg` is easier to
extend than it looks.

`tg` is declared as an **open, dynamically-populated set** with no fixed
element list:

```gams
set tg ;
alias(tg,tgg) ;
```

(`autocode/b_declare_sets.gms`, generated per run). Its members today come
entirely from the literal `tg_i(tg,i)$[...] = yes ;` assignments at
`b_inputs.gms:793-810`, plus whatever labels appear in the associated input
CSVs (`cap_limit.csv`, `cap_penalty.csv`, `growth_limit_absolute.csv`). Adding
a new group needs only:

1. One new assignment line, e.g.
   `tg_i('my_new_group',i)$[<condition on i>] = yes ;`
2. A row for `'my_new_group'` in whichever CSV feeds the constraint you're
   using (`cap_limit.csv`/`cap_penalty.csv` for the interconnection-queue cap,
   `growth_limit_absolute.csv` for the absolute growth constraint).

No set-schema change is needed — GAMS picks up the new label from the data.

**Before doing this:** check that any postprocessing that assumes the current
fixed roster of `tg` labels (`wind-ons`, `wind-ofs`, `pv`, `csp`, `gas`, `coal`,
`nuclear`, `battery`, `hydro`, `h2`, `geothermal`, `biomass`, `pumped-hydro`,
`dr_shed`) iterates over `tg` dynamically rather than hardcoding that list.
Several `postprocessing/` scripts reference these category names; a new label
that isn't consumed the same way downstream could silently be missing from
plots and summaries rather than erroring.

## Combining mechanisms: cost tiers for a single technology

A natural follow-on question: can a technology have a cheap tier with a hard
capacity limit, and a pricier tier that picks up whatever exceeds it — the
same shape as an RSC supply curve's bins, but for a technology that isn't
`rsc_i`?

**Yes, conceptually.** RSC technologies already get this for free: each
`rscbin` is a cost/quantity pair, so the model exhausts cheap bins before
touching expensive ones (Option 1). For a non-RSC technology, the same effect
can be approximated by **duplicating the technology under two `i` labels**
with identical technical characteristics but different constraint treatment:

- **Tier 1** (`mytech_tier1`) — its own `tg` group, with Option 2's
  interconnection-queue mechanism repurposed and `CAP_ABOVE_LIM.up(tg,r,t) = 0`
  fixed for that group, giving it a genuine hard ceiling.
- **Tier 2** (`mytech_tier2`) — a `cost_cap_fin_mult` multiplier (Option 4,
  by analogy to `GSw_NukeStateBan` mode 2) making it strictly pricier than
  tier 1, left uncapped (or capped higher, for a third tier).

Because tier 2 costs more, the model fills tier 1 first and only spills into
tier 2 once tier 1's hard cap binds — a tiered merit order out of two
independent mechanisms, rather than one purpose-built equation.

**Warning: this is a lot more plumbing than it sounds like, and easy to get
partially wrong.** `i` is not a cosmetic label — it's the join key for a large
number of sets and input tables across the model, and a duplicated tech only
behaves identically to the original in the places someone has explicitly gone
and duplicated it too. In practice that likely means auditing and updating:

- Every tag/subset the original tech belongs to (e.g. `pv(i)`, `nuclear(i)`,
  `gas(i)`, `tg_i(tg,i)`) — miss one and tier 2 silently drops out of whatever
  logic that tag drives (curtailment, capacity credit, reserve margins, RPS
  eligibility, etc.).
- All per-technology input CSVs the model reads for `i` (cost, heat rate,
  capacity factor, minimum loading, emissions, `dollaryear.csv`, and whatever
  else `runfiles.csv` maps to `i`), duplicated for the new label with the
  correct values.
- Where existing/prescribed capacity gets assigned — it needs to land in one
  tier (presumably tier 1, since it already exists and shouldn't compete
  against the new-build cap).
- Any postprocessing/reporting script that hardcodes tech names or a fixed
  tech list rather than iterating a set dynamically — a new `i` label that
  isn't consumed the same way downstream can silently vanish from plots and
  summaries instead of erroring (the same caution called out above for
  extending `tg`).

None of this is exotic — it's the same category of work as adding any new
technology to ReEDS — but "duplicate the tech and apply two different
constraints" is the easy 10% of this pattern. The other 90% is making sure
the duplicate is indistinguishable from the original everywhere except cost
and cap. Treat it as a multi-file change with real risk of partial
implementation, not a config tweak.

## Option not recommended: bounding `INV`/`CAP` directly

It's tempting to reach for a plain GAMS variable bound (`INV.up(i,v,r,t) = ...`
or `CAP.up(i,v,r,t) = ...`) instead of adding an equation. This works for a
per-instance limit (one tech, one vintage, one region, one year), but **GAMS
bounds don't aggregate** — there's no way to express "the sum of `CAP` across
all `(v,r)` for this `i` stays under X" as a `.up` bound, because a bound
applies to one variable instance, not a sum of instances. A genuine cumulative
ceiling requires either the interconnection-queue mechanism above (already
built for exactly this) or a new equation modeled on it. Don't spend time
trying to fake a cumulative cap with instance-level bounds — Option 2 already
solves this problem.

## CEPM recommendation: a deployment cap by tech group, using default `tg` groups

For the common CEPM ask — "cap how much of tech group X gets built," using the
default `tg` roster, without new GAMS code — split by whether the tech is
`rsc_i` or not, since no single mechanism cleanly covers both:

**RSC techs (`wind-ons`, `wind-ofs`, `pv`, `geothermal`, `pumped-hydro`):** cap
the resource supply curve (Option 1), but don't edit the shared default file —
these already key off scenario switches. `supplycurve_upv-{GSw_SitingUPV}.csv`,
`supplycurve_wind-ons-{GSw_SitingWindOns}.csv`, and
`supplycurve_wind-ofs-{GSw_SitingWindOfs}.csv`
(`reeds/input_processing/runfiles.csv:231-233`) are all parameterized by a
siting-scenario switch already. Add a new siting-scenario value pointing at a
capped copy of the supply curve, rather than shrinking the default file that
every other case also reads. Genuinely data-only, no code touched, and it's a
real physical ceiling — `m_rscfeas` simply won't allow more capacity than what
the bins contain.

**Everything else (`gas`, `coal`, `nuclear`, `battery`, `h2`, `biomass`,
`hydro`):** ~~use `GSw_GrowthAbsCon` + `GSw_GrowthConLastYear`~~ — **this
recommendation has been withdrawn.** It said to set
`GSw_GrowthConLastYear` to the case's `endyear`, which is precisely the
configuration that makes the final solve year infeasible (see the ⚠️ block in
Option 3 above, and the live confirmation on `WECC-SW_baseline`). Even with the
sacrificial-final-year workaround, the flat MW/year parameter can't follow a
lumpy build profile, bounds MW_dc while outputs report MW_ac, and has no way to
exempt the first year's prescribed builds.

**Use instead:** the purpose-built cumulative caps
(`eq_cepm_tg_cap_sys` / `eq_cepm_tg_cap_reg`) added for CEPM's
baseline-constrained runs, driven by `GSw_CEPM_TgCap` and
`inputs/growth_constraints/cepm_tg_cap_{sys,reg}_{cepmtgcapscen}.csv`. They are
genuinely cumulative (so the final year is fine), available at both system-wide
and per-region scope, and expressed in MW_ac so the numbers match
`cap_new_out` and every plot. Design rationale, units, and the zero-value trap
are documented in
[`two-step-re-limited-runs.md`](two-step-re-limited-runs.md) §4.

**Why not Option 2 for this** — worth recording, since the queue mechanism looks
like the obvious fit. `cap_limit`/`eq_interconnection_queues` is already active
*and already violated* in CEPM baselines: `cap_above_limit.csv` from
`runs/v20260824-2_WECC-SW_baseline` has 20 non-zero rows (PV in `z28` ~5.0 GW
over its limit in 2026, wind in `p31` ~5.2 GW over, gas in `p59` ~2.0 GW over),
absorbed by the penalized `CAP_ABOVE_LIM` slack. Repurposing it for a policy
ceiling would perturb a constraint that is already doing work in the baseline,
which breaks any controlled baseline-vs-scenario comparison. Separately worth
knowing: the shipped queue data stops at 2030, so
`sum{(tgg,rr), cap_limit(tgg,rr,'2032')}` is zero and the queue constraint
**switches itself off entirely in 2032** in every CEPM run today.

## Recommendation

| Want to... | Use |
|---|---|
| Remove a tech entirely, including existing capacity | `ban(i)`, following the `GSw_Biopower`/`GSw_OfsWind` pattern |
| Stop new builds, keep existing capacity operating | `bannew(i)`, following the `GSw_OnsWind6to10` pattern |
| Cap physical buildable potential for an RSC tech (solar/wind/geo/PSH) | Edit the resource supply curve `cap` bins |
| Impose a real cumulative MW ceiling on new investment, by tech group (CEPM) | `GSw_CEPM_TgCap` + `cepm_tg_cap_{sys,reg}_*.csv` (`eq_cepm_tg_cap_sys`/`_reg`) — cumulative, MW_ac, system-wide or per-region |
| Same, but you're upstream / can't add an equation | Repurpose `cap_limit.csv`/`cap_penalty.csv` (`eq_interconnection_queues`); fix `CAP_ABOVE_LIM.up = 0` if it must be hard rather than soft — but see the CEPM caveat above about perturbing an already-binding constraint |
| Slow the pace of new builds without capping the eventual total | `GSw_GrowthAbsCon`/`GSw_GrowthPenalties` — **and keep `GSw_GrowthConLastYear` strictly below the last modeled year** |
| Discourage a tech economically without guaranteeing a limit | A cost multiplier on `cost_cap_fin_mult(i,r,t)`, by analogy to `GSw_NukeStateBan` mode 2 |

The three mistakes to avoid: reaching for `ban(i)` when you meant `bannew(i)`
(you'll retire capacity you meant to keep); reaching for a cost multiplier or
growth-rate constraint when you actually need a guaranteed ceiling (neither can
promise one); and setting `GSw_GrowthConLastYear` to the run's `endyear`, which
makes the final solve year infeasible outright (Option 3's ⚠️ block above).

# Options for restricting a technology's capacity in ReEDS

**Scope:** the range of mechanisms available for constraining a single
technology (e.g. biopower, solar, wind) in a ReEDS run — from a full ban, to a
new-build-only ban, to a soft cost penalty, to a hard cumulative ceiling — and
what each implies for existing capacity, solvability, and reporting.

**Short version:** ReEDS already contains four distinct mechanisms that cover
most of this design space (`ban`/`bannew`, growth-rate constraints, the
interconnection-queue cumulative cap, and cost-multiplier penalties). Which one
is right depends on a question that is easy to skip past: do you want to
guarantee a hard limit, or discourage the technology and let the model decide?
Only some of the options below can actually promise the former.

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

**CEPM-specific exception: short horizons turn this into a de facto ceiling.**
`eq_growthlimit_absolute` is national-only in its indexing (no `r` term, just
`tg,t`) — but for a subnational case that's harmless, since the sum only ever
runs over whatever regions are actually in the model, so it naturally becomes
your run's total. More importantly: because CEPM cases typically run a short
horizon (e.g. `endyear=2032`, build years `2026/2029/2032`), setting
`GSw_GrowthConLastYear` to cover the *entire* run means there are no
later years left for the model to "catch up" in — the pace limiter and the
cumulative cap become numerically equivalent for the run's duration. This
turns Option 3 into the practical answer for a deployment cap on non-RSC techs
(gas, coal, nuclear, battery, h2, biomass, hydro) in CEPM specifically, even
though it's explicitly the wrong tool for a full 2050-horizon ReEDS run. See
the recommendation section below for the concrete switch/data values.

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
`hydro`):** use `GSw_GrowthAbsCon` + `GSw_GrowthConLastYear`, leaning on the
short-horizon exception called out above. Concretely, to cap `tg='gas'` at
5 GW cumulative for a case whose build years are 2026/2029/2032:

1. Add a `gas,<MW/year>` row to `inputs/growth_constraints/growth_limit_absolute.csv`,
   sized so `MW/year * (number of build-year intervals)` ≈ your GW target
   (e.g. `5000 / 2` if there are two 3-year intervals between 2026→2029→2032).
2. In `cases_cepm.csv`, add rows (mirroring the existing `GSw_GrowthPenalties`
   row at line 23) for that case's column:
   - `GSw_GrowthAbsCon,1`
   - `GSw_GrowthConLastYear,2032` (the case's `endyear`)

This is cheap because both switches already exist in `cases.csv:153-154`, and
the data file already uses the default `tg` groups (`wind-ons`, `pv`,
`battery` are populated today; add a row for whatever `tg` you're targeting).

**Caveat to carry forward:** this is not a true infinite-horizon hard cap —
it's "hard for the length of this run." If a case's `endyear` is later
extended past what `GSw_GrowthConLastYear` was set to, the constraint stops
binding with no warning, and the model can build past the intended ceiling
silently. Re-check `GSw_GrowthConLastYear` any time a capped case's horizon
changes.

**If the ask ever outgrows this** — a true cumulative ceiling that holds
regardless of horizon length, or one that needs to vary by region rather than
apply to the whole modeled area — that requires the interconnection-queue
mechanism (Option 2), which in turn requires adding the scenario-switch/
`runfiles.csv` plumbing described in that section's caveat above. Not
currently implemented; flag as follow-up work if it comes up.

## Recommendation

| Want to... | Use |
|---|---|
| Remove a tech entirely, including existing capacity | `ban(i)`, following the `GSw_Biopower`/`GSw_OfsWind` pattern |
| Stop new builds, keep existing capacity operating | `bannew(i)`, following the `GSw_OnsWind6to10` pattern |
| Cap physical buildable potential for an RSC tech (solar/wind/geo/PSH) | Edit the resource supply curve `cap` bins |
| Impose a real cumulative GW ceiling on new investment, by tech group and region | Repurpose `cap_limit.csv`/`cap_penalty.csv` (`eq_interconnection_queues`); fix `CAP_ABOVE_LIM.up = 0` if it must be hard rather than soft |
| Slow the pace of new builds without capping the eventual total | `GSw_GrowthAbsCon`/`GSw_GrowthPenalties` |
| Discourage a tech economically without guaranteeing a limit | A cost multiplier on `cost_cap_fin_mult(i,r,t)`, by analogy to `GSw_NukeStateBan` mode 2 |

The two mistakes to avoid: reaching for `ban(i)` when you meant `bannew(i)`
(you'll retire capacity you meant to keep), and reaching for a cost multiplier
or growth-rate constraint when you actually need a guaranteed ceiling (neither
can promise one — only the interconnection-queue mechanism, made hard via
`CAP_ABOVE_LIM.up = 0`, or a purpose-built cumulative-cap equation, can).

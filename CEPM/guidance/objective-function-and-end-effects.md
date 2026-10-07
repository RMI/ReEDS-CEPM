# What the ReEDS objective minimizes, and how it treats years after `endyear`

**Scope:** which costs the ReEDS optimization minimizes, how they are discounted,
and whether costs beyond the last year in `yearset` are counted. This covers
all three `timetype` modes (`seq`, `int`, `win`). It is based on a reading of
the source on `dev` as of October 2026. No model runs were made for it.

**Short version:** yes, the objective counts costs after `endyear`, but only
**operating** costs, and only by assumption. No years after `endyear` are
modeled. Instead, the operating cost of the last modeled year is multiplied by
a present-value factor that treats that year as repeating unchanged for
`sys_eval_years` years (default **30**,
[`cases.csv:66`](../../cases.csv#L66)). In the default sequential mode, *every*
solve year's operating cost is treated this way. **Capital** costs are charged
once, as a lump sum in the build year. They are scaled to a 30-year economic
life, but the model applies no salvage or terminal-value credit for assets
still in service after the horizon.

## 1. What the objective contains

The objective is the sum, over modeled years, of an investment term and an
operations term
([`d_objective.gms:22`](../../reeds/core/setup/d_objective.gms#L22)):

```text
Z = cost_scale * Σ_{t ∈ tmodel} [ Z_inv(t) + Z_op(t) ]
Z_inv(t) = pvf_capital(t) * ( ...capital terms... )
Z_op(t)  = pvf_onm(t)     * ( ...annual operating terms... )
```

### Investment component, `Z_inv(t)`

[`d_objective.gms:28-143`](../../reeds/core/setup/d_objective.gms#L28-L143):

| Term | Lines |
| --- | --- |
| Overnight capex for generation and storage, including battery energy capacity, multiplied by `cost_cap_fin_mult` | 38-44 |
| Upgrades, refurbishments, and capacity/energy upsizing | 55, 90, 121-126 |
| Supply-curve spur lines and explicitly modeled spur lines | 63-69 |
| Intra-zone network reinforcement (POI) | 73 |
| Interzonal AC and HVDC transmission, LCC and VSC converters | 95-113 |
| Water access, when `Sw_WaterMain` is on | 77-87 |
| H₂ pipelines and storage, CO₂ pipelines and spur lines | 129-139 |
| **Penalties that are not real costs:** interconnection-queue overage, growth penalties, storage duration-bin penalty | 47, 50, 117 |

### Operations component, `Z_op(t)`

[`d_objective.gms:149-372`](../../reeds/core/setup/d_objective.gms#L149-L372).
These are costs for **one year**:

| Term | Lines |
| --- | --- |
| Variable and fixed O&M for generators, storage, transmission lines, converters, spur lines, POI | 159-207 |
| Fuel: coal, nuclear and other fixed-price fuels, gas (several supply-curve options), biomass | 227-280 |
| Startup/ramping costs, operating reserves, transmission hurdle rates | 233, 219, 283 |
| Emissions taxes, CO₂ transport and storage, RPS alternative compliance payments, dropped/excess load | 287-311 |
| H₂ and DAC production costs, retail adder | 314-333 |
| **Credits (subtracted):** PTC, 45Q, H₂ PTC, curtailment market, retirement "friction" | 210, 307, 350-368 |

The user-facing docs list the same categories at a higher level
([`model_documentation.md:288-304`](../../docs/source/model_documentation.md#L288-L304)).
Their only mention of the post-horizon treatment is a footnote: operating
expenses are counted "over the evaluation period", and "the default evaluation
period is 30 years". The docs don't explain how this works. The rest of this
note does.

## 2. How operating costs reach past `endyear`

How it works depends on `timetype`. All three modes rely on `pvf_onm(t)`.

### Sequential (`seq`, the default; [`cases.csv:2`](../../cases.csv#L2))

Each solve year is a separate, myopic optimization. `tmodel` contains only that
year. [`e_solveprep.gms:124-127`](../../reeds/core/setup/e_solveprep.gms#L124-L127)
overwrites the factors:

```gams
pvf_capital(t) = 1 ;
pvf_onm(t)$tmodel_new(t) = round(1 / crf(t),6) ;
```

`crf` is computed over `sys_eval_years`
([`financials.py:171`](../../reeds/financials.py#L171)). So `1/crf` is the
present value of a 30-year annuity, about 14-20 for real discount rates of
3-6%. **In every solve year, not just the last, one year of operating cost is
valued as if it continued for 30 years**, and that total is compared against a
one-time capital cost. The model is myopic in that solve year: it holds that
year's loads, fuel prices and policies flat for 30 years. Gap years between
solve years carry no weight of their own in sequential mode.

### Intertemporal (`int`)

All modeled years are solved together, and `pvf_onm` is built in Python:

1. [`financials.py:43-44`](../../reeds/financials.py#L43-L44) builds the year
   range as `min(modeled_years)` through `max(modeled_years) + sys_eval_years`.
   The code comment says it does this to "extend beyond the last modeled year
   by the evaluation horizon".
2. [`financials.py:48-52`](../../reeds/financials.py#L48-L52) maps each
   calendar year to the latest modeled year at or before it. Every year after
   the final modeled year therefore maps to the final modeled year.
3. [`financials.py:159-166`](../../reeds/financials.py#L159-L166) computes
   cumulative per-year discount factors (end-of-year convention).
4. [`calc_financial_inputs.py:485-489`](../../reeds/input_processing/calc_financial_inputs.py#L485-L489)
   **sums** those factors by modeled year to produce `pvf_onm_int.csv`.

As a result, each modeled year stands in for the gap years until the next
modeled year. **The final modeled year stands in for 30 years: `endyear`
through `endyear + 29`.** The final year's operating cost therefore carries
roughly 15-20× the weight of a single year. This is the classic end-effect
problem. ReEDS handles it with a steady-state tail approximation, not a salvage
value.

### Window (`win`)

[`3_solve_window.gms:31-35`](../../reeds/core/solve/3_solve_window.gms#L31-L35)
uses the intertemporal factors inside each window. It then resets the window's
last year to a 30-year annuity, discounted to that year:

```gams
pvf_onm(t)$tlast(t) = round(pvf_capital0(t) / crf(t), 6) ;
```

## 3. How capital costs fit the 30-year window

Capital costs aren't cut off at `endyear`. A plant built in the final year pays
the same capital cost as one built earlier. Instead, all capital is scaled to
the 30-year evaluation period:

- **`cost_cap_fin_mult`**
  ([`2_financials.gms:24-28`](../../reeds/core/solve/2_financials.gms#L24-L28))
  covers construction financing, the tax gross-up, MACRS depreciation, the
  ITC, the financing-risk premium, regional cost differences, and
  `eval_period_adj_mult`.
- **`eval_period_adj_mult`** = PV-sum over `sys_eval_years` ÷ PV-sum over the
  technology's own `eval_period`
  ([`calc_financial_inputs.py:152-157`](../../reeds/input_processing/calc_financial_inputs.py#L152-L157)).
  A technology with a life shorter than 30 years has its capital scaled up;
  one with a longer life has it scaled down.
- **Transmission** is scaled by `CRF(trans_crp) / CRF(sys_eval_years)`
  ([`financials.py:705-712`](../../reeds/financials.py#L705-L712)), with
  `trans_crp = 40` ([`scalars.csv:86`](../../inputs/scalars.csv#L86)). Only
  the part of transmission capital that falls inside the 30-year window is
  charged.
- **Production tax credits** are rescaled from their actual durations to the
  30-year window in the same way: the PTC via `ptc_value_scaled`
  ([`financials.py:716-743`](../../reeds/financials.py#L716-L743)), and 45Q
  and the H₂ PTC via `crf(t) / crf_<incentive>(t)` in the objective
  ([`d_objective.gms:351`](../../reeds/core/setup/d_objective.gms#L351),
  [`:367`](../../reeds/core/setup/d_objective.gms#L367)).
- `pvf_capital` only discounts each year back to the first modeled year
  ([`financials.py:152-157`](../../reeds/financials.py#L152-L157)). It is
  exported only for modeled years
  ([`financials.py:758-761`](../../reeds/financials.py#L758-L761)), so capital
  gets no extra weight past the horizon.

Taken together, the model's implicit accounting horizon is **each build plus 30
years of operation**, with a uniform 30-year economic life. Nothing in the
objective represents retirements, replacements, or changes in load, fuel
prices, carbon prices or policy after `endyear`.

## 4. Things that are easy to misread

- **The objective is not the reported system cost.** The docs section "Present
  Value of Direct Electric Sector Cost"
  ([`model_documentation.md:3775-3800`](../../docs/source/model_documentation.md#L3775-L3800))
  describes a *reporting* metric. It uses a social discount rate over the
  analysis period only. The objective discounts with `d_real`, a real rate
  derived from the WACC
  ([`financials.py:135-145`](../../reeds/financials.py#L135-L145)), and
  includes the 30-year tail.
- **Penalty terms inflate the objective value.** The queue-overage, growth and
  bin penalties are in `Z_inv`, but they aren't real costs. See
  [`interconnection-queue-and-prescribed-builds.md`](interconnection-queue-and-prescribed-builds.md)
  for how large the queue penalty can be in CEPM runs.
- **Credits are netted in.** The PTC, 45Q and H₂ PTC are subtracted from
  `Z_op`, so the objective is a net cost.

## 5. What this means for CEPM runs

- `cases_cepm.csv` doesn't set `timetype`, so CEPM runs use the default
  `seq`. With `endyear = 2032` and `yearset = 2026..2032..3`, each solve year
  values its own operating costs over a 30-year annuity. For example, the 2032
  solve implicitly values 2032 operations through about 2061.
- Because each solve is myopic, a 2026 build decision sees 2026 fuel prices,
  loads and policy held flat for 30 years. It doesn't see conditions in 2029
  or 2032.
- `sys_eval_years` is the lever for testing sensitivity to the tail length. It
  changes `crf`, `pvf_onm`, `eval_period_adj_mult`, the transmission CRF
  scaling and `ptc_value_scaled` together.

## 6. How to check the actual factors for a run

All of these are in `runs/<case>/inputs_case/`:

| File | Contents |
| --- | --- |
| `crf.csv` | CRF per modeled year (over `sys_eval_years`); `1/crf` is the `seq` operating-cost multiplier |
| `pvf_onm_int.csv` | Intertemporal operating-cost PV factor per modeled year; the last row includes the 30-year tail |
| `pvf_cap.csv` | Capital PV factor per modeled year (overwritten to `1` in `seq`) |
| `eval_period_adj_mult.csv` | Per-technology capital scaling for non-30-year lives |

`pvf_capital` and `pvf_onm`, as actually used, are also written as report
parameters ([`report_params.csv:269-270`](../../reeds/core/terminus/report_params.csv#L269-L270)),
so they appear in a completed run's `outputs/`.

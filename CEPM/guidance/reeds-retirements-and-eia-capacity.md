# ReEDS retirements, prescribed builds, and 2026 generator data
**Written Date:** October 15, 2026

This note summarizes how ReEDS treats generator retirements and prescribed builds, and records the comparison between the August and September 2026 generator databases used in CEPM analysis. The generator-database comparison below is for the **WECC-SW region (p27-p31 and p59)** unless otherwise noted.

## Retirement switches

The following are the main retirement-related switches in the ReEDS `2026.08.03` base.

| Switch | Default | Options / meaning |
|---|---:|---|
| `GSw_Retire` | `5` | Controls **endogenous retirement**. `0`: none; `1`: any existing plant; `2`: existing coal/gas only; `3`: new and existing nuclear/coal/gas after minimum age; `4`: new and existing plants of any technology; `5`: same as `3`, but nuclear cannot retire before 2030. |
| `GSw_RetireYear` | `2027` | First year in which endogenous retirement is allowed. |
| `GSw_RetirePenalty` | `1` | `0`/`1`. Applies a penalty for retiring a plant early to represent retirement friction. |
| `GSw_RetireYears_Coal` | `0` | Integer adjustment to retirement years for currently operating coal plants. `0` uses retirement years from the EIA unit database; negative values shorten lifetime and positive values extend it. Ignored when `GSw_RetireYears_Thermal` is nonzero. |
| `GSw_RetireYears_Thermal` | `0` | Integer adjustment to retirement years for currently operating thermal plants. `0` uses retirement years from the EIA unit database; negative values shorten lifetime and positive values extend it. |
| `retscen` | `Nuke80RetireYear` | Nuclear exogenous-retirement scenario: `Nuke60RetireYear`, `Nuke80RetireYear`, `NukeEarlyRetireYear`, or `NukeRefRetireYear`. |
| `GSw_NukeNoRetire` | `1` | `0`/`1`. Prevents nuclear units from retiring before the year set by `GSw_NukeNoRetireYear`. |
| `GSw_NukeNoRetireYear` | `2032` | With `GSw_NukeNoRetire=1`, nuclear cannot retire through the end of this year. |

`GSw_Clean_Air_Act` is not a general retirement switch, but can affect coal-retirement decisions. Its default is `1`, which enables the modeled Clean Air Act Section 111 provisions.

## Exogenous and endogenous retirements

ReEDS distinguishes between **exogenous retirement dates** supplied with the generator data and **endogenous retirements** chosen by the model.

For existing generators, `writecapdat.py` primarily uses the unit's online year and retirement year to determine whether capacity is available. A unit is treated as retired at the **beginning of its `RetireYear`**. Plant-status fields are useful when comparing the database with EIA, but they are not the primary rule ReEDS uses to determine availability.

The exogenous retirement date therefore sets the outside limit on how long existing capacity remains available. `GSw_RetireYears_Coal` and `GSw_RetireYears_Thermal` can shift those dates before the model solves, while `retscen` selects the nuclear retirement-date assumption.

When endogenous retirement is enabled through `GSw_Retire`, eligible capacity may retire **earlier** if the model finds that economical. Endogenous retirement does not extend an existing unit beyond its exogenous retirement date. `GSw_RetireYear`, retirement penalties, minimum-age requirements, and the nuclear no-retirement settings further restrict when early retirement can occur.

In short:

- **Exogenous retirement** determines when capacity must leave the system.
- **Endogenous retirement** allows eligible capacity to leave earlier.
- The unit database's `RetireYear` is more important to ReEDS availability than the descriptive EIA status field.

## Prescribed builds

ReEDS also separates **existing capacity** from **prescribed future builds**. In `writecapdat.py`, capacity with an online year before the model start is treated as existing, while capacity with an online year at or after the model start is collected as prescribed capacity.

Prescribed builds are exogenous assumptions about the **technology, region, timing, and amount** of capacity expected to come online. With `GSw_ForcePrescription=1` (the default), ReEDS enforces these requirements rather than treating the projects as optional candidate builds.

Prescriptions are enforced cumulatively. If a prescribed online year falls between modeled solve years, the requirement is carried into the next solve year. Once built, prescribed capacity enters the model's investment and capacity accounting in the same general way as other new capacity. ReEDS may also build **additional capacity beyond the prescription** when it is economical to do so.

This means prescribed capacity should be interpreted as a required minimum based on the input pipeline, not as a complete forecast of what ReEDS will build.

## August vs. September 2026 generator database

The September generator database was a substantial update from the August version. The August file reflected an older EIA data vintage, while the September file incorporated the updated 2026 generator data. As a result, much of the difference represents projects that had entered service, moved forward in the development pipeline, or were newly captured in the EIA update rather than a change in ReEDS model logic.

### Capacity available in 2026

Total WECC-SW capacity represented as active in 2026 increased from approximately **56.84 GW in August to 62.02 GW in September**, an increase of about **5.18 GW**.

The largest grouped changes were:

| Technology | August | September | Change |
|---|---:|---:|---:|
| Battery | 7.85 GW | 10.18 GW | +2.33 GW |
| Solar | 11.37 GW | 13.14 GW | +1.77 GW |
| Gas / oil | 17.93 GW | 18.68 GW | +0.75 GW |
| Wind | 7.18 GW | 7.68 GW | +0.50 GW |
| Coal | 4.48 GW | 4.30 GW | -0.18 GW |

The September database aligned much more closely with the updated EIA inventory: about **99.4% of EIA operable capacity** was represented, compared with roughly **88.3% in the older August database**.

The 62.02 GW ReEDS total should not be read as an EIA "commercially operating" total. ReEDS classifies units primarily from online and retirement years, so some projects with a 2026 online year can be included even when EIA still reports them as under construction, testing, or otherwise not yet commercially operating.

### Prescribed future capacity

The update was even larger for prescribed builds with an online year of 2026 or later:

| | August | September |
|---|---:|---:|
| Prescribed rows | 32 | 84 |
| Prescribed capacity | 7.12 GW | 16.20 GW |

This is an increase of approximately **9.07 GW**. The largest additions were about **4.44 GW of battery**, **3.35 GW of utility PV**, **0.94 GW of gas CT**, and **0.50 GW of onshore wind**. The August database contained no WECC-SW prescriptions after 2026; the September update added about **3.31 GW in 2027** and **0.73 GW in 2028**.

A project-level check against the September/EIA update also showed that the August 2026 prescriptions were generally real projects progressing through the pipeline. Of the **7.12 GW** prescribed for 2026 in the August file:

- about **4.75 GW** was operating by the September update;
- about **0.52 GW** was construction-complete but not yet commercial;
- about **1.29 GW** remained under construction with a 2026 expected online year;
- about **0.45 GW** had moved to 2027; and
- about **0.11 GW** was corrected to an online year before 2026.

None of the August prescribed capacity simply disappeared from the updated data.

## Practical interpretation

For CEPM analysis, the September generator database should be treated as the better representation of the 2026 starting fleet and near-term project pipeline. The comparison also reinforces two important points when interpreting ReEDS results:

1. **Retirements are governed by ReEDS retirement-year inputs and switches, not simply by an EIA status label.**
2. **Prescribed builds represent exogenous minimum additions from the known project pipeline; they do not prevent ReEDS from building additional capacity.**

## Key ReEDS references

- `cases.csv` — switch definitions and defaults.
- `reeds/input_processing/writecapdat.py` — construction of existing capacity, prescribed capacity, and retirement inputs.
- `inputs/capacity_exogenous/ReEDS_generator_database_final_EIA-NEMS.csv` — underlying EIA-NEMS generator database.

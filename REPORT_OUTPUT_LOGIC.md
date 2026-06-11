# ReEDS Report Output Logic

This table explains the sections in the standard expanded ReEDS bokehpivot
report. It is meant for triaging `outputs/reeds-report/report.html` and
`outputs/reeds-report/report.log` after a run.

The report template is `postprocessing/bokehpivot/reports/templates/reeds2/standard_report_expanded.py`.
Its result definitions live in `postprocessing/bokehpivot/reeds2.py`.

## How to Read This

- Bare source names like `cap_nat` or `systemcost` are resolved by
  `reeds.io.read_output`; in current runs they commonly come from
  `outputs/outputs.h5`, though some may also exist as standalone output files.
- Paths ending in `.csv` are read literally relative to `outputs/`, unless they
  start with `../inputs_case/`, in which case they are read from the run's
  `inputs_case/` directory.
- A section reports out when its source data exists, has the expected columns,
  survives preprocessing, and is still non-empty after the section's filters.
- Map sections also need valid region/state mapping data and at least one
  non-empty final-year value after filtering.
- `report.log` red-section failures are isolated by design: bokehpivot catches a
  section exception, writes a red `ERROR!` header in `report.html`, logs the
  traceback, and keeps building later sections.

## Core Model Outputs

| No. | Report section | Reads | Reports when |
| --- | --- | --- | --- |
| 1 | Error Check: shows modeled error-check values by error type. | `error_check` | The error-check table exists with `type` and `Value`. Nonzero values may be a meaningful model warning, not a plotting failure. |
| 2 | Intertemporal Capacity by Iteration (GW): capacity by tech, year, and solver iteration. | `cap_iter` | Intertemporal/iteration output was written. This is tied to intertemporal solve mode; sequential cases such as `timetype=seq` may not write `cap_iter`, so the section can fail even if the model solved. |
| 3 | Generation (TWh): national annual generation by technology. | `gen_ann_nat` | National annual generation exists with tech-year rows. |
| 4 | Capacity (GW): national installed capacity by technology. | `cap_nat` | National capacity exists with tech-year rows. |
| 5 | Energy Capacity (GWh): storage/product energy capacity by tech, vintage, region, and year. | `cap_energy_ivrt` | Energy-capacity output exists. Empty storage/product portfolios can leave little to plot. |
| 6 | New Annual Capacity (GW): national annual capacity additions by technology. | `cap_new_ann_nat` | New-build output exists with tech-year rows. |
| 7 | Annual Retirements (GW): national annual retirements by technology. | `ret_ann_nat` | Retirement output exists with tech-year rows. |
| 8 | Final Gen by timeslice (GW): final-year generation profile by modeled timeslice. | `gen_h_nat` | Timeslice generation exists, timeslices can be sorted, and final-year filtered rows are non-empty. |
| 9 | Final Gen by stress timeslice (GW): final-year generation during stress timeslices. | `gen_h_stress_nat` | Stress-period generation output exists and final-year stress timeslices are non-empty. |
| 10 | Regional Gen Final (TWh): final-year BA-level generation map by technology. | `gen_ann` via `Generation BA (TWh) [no-index]` | BA-level annual generation exists, final-year rows are non-empty, and BA geography joins succeed. |
| 11 | Operating Reserves (TW-h): annual operating reserve supply by reserve type and tech. | `opRes_supply` | Operating reserve supply exists with reserve-type, tech, region, and year. |
| 12 | Final OpRes by timeslice (GW): final-year operating reserve supply by timeslice. | `opRes_supply_h` | Timeslice reserve supply exists and the final-year filtered data has plottable reserve types/techs. `GSw_OpRes=2` enables the simplified `combo` reserve type and should not by itself suppress this output. However, the model equations are also gated by `opres_h`; if the active `inputs_case/<temporal_inputs>/opres_periods.csv` is empty, `opRes_supply_h.csv` can be header-only and the report can fail with a plotting index error. |
| 13 | Firm Capacity (GW): seasonal firm capacity and derived capacity credit. | `cap_firm`, `cap` | Firm-capacity and installed-capacity outputs both exist and can be joined by tech, region, season, and year. |
| 14 | Curtailment Rate: VRE curtailment rate over time. | `curt_rate` | Curtailment-rate output exists with year and `Curt Rate`. |
| 15 | Losses (fraction of load): losses normalized by load. | `losses_ann` | Loss and `load` rows exist. The `load` row is the denominator for the fraction. |
| 16 | Transmission (GW-mi): transmission capacity by type over time. | `tran_mi_out`, `tran_prm_mi_out`, `cap_new_bin_out`, `../inputs_case/spur_parameters.csv`, `../inputs_case/scalars.csv` | Transmission outputs and supporting spur-line inputs exist; preprocessing can calculate total transmission capacity. |
| 17 | Transmission (PRM) (GW-mi): PRM-attributed transmission capacity. | Same as section 16 | Same as section 16, plus the PRM transmission column is populated enough to plot. |

## Prices, Costs, Revenues, and Emissions

| No. | Report section | Reads | Reports when |
| --- | --- | --- | --- |
| 18 | Bulk System Electricity Price ($/MWh): stacked bulk cost components divided by load. | `reqt_price_sys`, `reqt_quant_sys` | System-level requirement prices and quantities exist, including `q_load` denominator rows and relevant price component rows. |
| 19 | National Energy Price ($/MWh): national energy price over time. | `reqt_price_sys`, `reqt_quant_sys` | Energy-price and load-quantity rows exist after price preprocessing. |
| 20 | Final National Energy Price by timeslice ($/MWh): final-year national energy price by timeslice. | `reqt_price_sys`, `reqt_quant_sys` | Final-year energy-price rows by timeslice exist and timeslices sort cleanly. |
| 21 | National Average Electricity Cost ($/MWh): annualized system cost divided by national load. | `systemcost`, `reqt_quant`, `../inputs_case/crf.csv`, `../inputs_case/val_r.csv`, `../inputs_case/df_capex_init.csv`, `../inputs_case/switches.csv`, `../inputs_case/scalars.csv` | System cost, load quantities, and financial helper files exist. Missing `df_capex_init.csv` or malformed financial inputs can break this and related cost sections. |
| 22 | National OpRes Price ($/MW-h): national operating reserve price over time. | `reqt_price_sys`, `reqt_quant_sys` | Operating reserve price and quantity rows exist after preprocessing. |
| 23 | Final National OpRes Price by timeslice ($/MW-h): final-year reserve price by timeslice. | `reqt_price_sys`, `reqt_quant_sys` | Final-year operating reserve price rows by timeslice exist and are non-empty. |
| 24 | Final Regional Energy Price ($/MWh): final-year BA energy price map. | `reqt_price`, `reqt_quant` | BA-level price and quantity rows exist, final-year load denominators exist, and BA map joins succeed. |
| 25 | National Annual Capacity Price ($/kW-yr): reserve-margin/capacity price over time. | `reqt_price_sys`, `reqt_quant_sys` | Annual capacity or reserve-margin price rows and matching quantity rows exist. |
| 26 | Annual Revenue National (Bil$/yr): revenue by technology and service. | `revenue_nat`, `cap_nat`, `gen_uncurtailed_nat` | Revenue output exists and can be joined to capacity and uncurtailed generation for derived metrics. |
| 27 | Annual Revenue per Capacity National ($/kW-yr): revenue normalized by capacity. | Same as section 26 | Same as section 26, plus capacity denominators are present and nonzero for plotted techs. |
| 28 | Annual Revenue per Generation National ($/MWh): revenue normalized by generation. | Same as section 26 | Same as section 26, plus generation denominators are present and nonzero for plotted techs. |
| 29 | Present Value of System Cost through 2050 (Bil $): discounted system cost summary. | `systemcost`, `../inputs_case/crf.csv`, `../inputs_case/val_r.csv`, `../inputs_case/df_capex_init.csv`, `../inputs_case/switches.csv`, `../inputs_case/scalars.csv` | System cost and financial helper files exist, and years overlap the report's present-value window. |
| 30 | Emissions National (metric tons): national emissions by emissions type. | `emit_nat` | National emissions output exists with emissions type, pollutant, year, and emissions value. |
| 31 | Net CO2e Emissions National (MMton): net CO2e by technology. | `emit_nat_tech` | Technology-level emissions exist and include rows usable by the net-CO2e preprocessing. |
| 32 | CO2 Abatement Cost ($/metric ton): CO2 price over time. | `co2_price` | CO2 price output exists and can be inflation-adjusted. |
| 33 | Undiscounted Annualized System Cost (Bil $): annual system cost by cost category. | Same as section 29 | Same as section 29, with annual cost rows available after preprocessing. |

## Hydrogen and Technology Detail

| No. | Report section | Reads | Reports when |
| --- | --- | --- | --- |
| 34 | Hydrogen Production (Million metric tons): production from hydrogen technologies. | `prod_produce_ann` | Production output exists and includes hydrogen tech rows selected by the preset. |
| 35 | Hydrogen Price ($ per kg): hydrogen product price over time. | `prod_h2_price` | Hydrogen price output exists with product-year price rows. |
| 36 | Final Wind Capacity (GW): final-year BA map for onshore and offshore wind. | `cap` filtered to `Onshore Wind`, `Offshore Wind` | Final-year BA capacity exists for wind technologies and geography joins succeed. |
| 37 | Final PV Capacity (GW): final-year BA map for UPV and DPV. | `cap` filtered to `UPV`, `DPV` | Final-year BA capacity exists for PV technologies and geography joins succeed. |
| 38 | Area used for UPV (sq. km.): UPV built area over time. | `land_use_total.csv` | Land-use postprocessing produced `outputs/land_use_total.csv` with built capacity and area columns. This is controlled by `land_use_analysis`; when `land_use_analysis=0`, the file is not expected. |
| 39 | Final CSP Capacity (GW): final-year BA map for CSP. | `cap` filtered to `CSP` | Final-year CSP capacity exists. If the filter is empty, map plotting may fail rather than render a blank chart. |
| 40 | Final Biopower Capacity (GW): final-year BA map for biopower and landfill gas. | `cap` filtered to `Biopower`, `Landfill-Gas` | Final-year capacity exists for at least one filtered biopower tech. Empty filters can trigger map plotting errors. |
| 41 | Final Geothermal Capacity (GW): final-year BA map for geothermal. | `cap` filtered to `Geothermal` | Final-year geothermal capacity exists and maps cleanly. |
| 42 | Final Hydro and Canadian Import Capacity (GW): final-year BA map for hydro/import capacity. | `cap` filtered to `Hydropower`, `Canadian Imports` | Final-year capacity exists for hydro or Canadian import categories. |
| 43 | Final Pumped-hydro Capacity (GW): final-year BA map for pumped-hydro storage. | `cap` filtered to `Pumped-Hydro`, `Pumped-Hydro-Flex` | Final-year pumped-hydro capacity exists. Empty filters can trigger map plotting errors. |
| 44 | Final Battery Storage Capacity (GW): final-year BA map for battery capacity. | `cap` filtered to `Battery` | Final-year battery capacity exists. Empty filters can trigger map plotting errors. |
| 45 | Capacity Factor - Generation: generation-weighted capacity factor by tech. | `gen_ivrt`, `cap_ivrt` | Generation and capacity by tech-vintage-region-year exist and denominators are nonzero. |
| 46 | Battery Average Duration (h): energy-capacity-weighted storage duration. | `storage_duration_out`, `cap_energy_ivrt` | Storage duration and energy capacity outputs exist for storage technologies. |
| 48 | New Tech Value Factors: value factors for new technologies. | `valnew` | New-tech value output exists and preprocessing can derive value-factor fields. |

## Retail, Health, Reliability, and Runtime

| No. | Report section | Reads | Reports when |
| --- | --- | --- | --- |
| 47 | Retail rate (cents/kWh): national retail rate by source over time. | `retail/retail_rate_USA_centsperkWh.csv` | Retail postprocessing completed and wrote the USA retail-rate CSV. If `retail_rate_calculations.py` fails, this section fails with `FileNotFoundError`. |
| 49 | Monetized health damages over time (billion $/year): annual health damages by air-quality model and concentration-response function. | `health_damages_caused_r.csv` | Health-damages postprocessing produced the current 9-column CSV (`ba`, `year`, `pollutant`, `tons`, `model`, `cr`, `md`, `damage_$`, `mortality`) or an equivalent schema that bokehpivot can normalize to its internal health-damage fields. |
| 50 | Mortality over time (lives/year): annual mortality impacts by model and concentration-response function. | Same as section 49 | Same as section 49. If section 49 fails during source preprocessing, later health presets may cascade with plotting-state errors. |
| 51 | Total undiscounted health damages through 2050 (billion $): cumulative undiscounted damages. | Same as section 49 | Same as section 49, with years overlapping the report's present-value start year through 2050. |
| 52 | Total discounted health damages through 2050 (billion $): cumulative discounted damages. | Same as section 49 | Same as section 49, plus discounting inputs from report defaults are valid. |
| 53 | Total mortality through 2050 (lives): cumulative mortality. | Same as section 49 | Same as section 49, with mortality rows available for the filtered year range. |
| 54 | System cost + health damages: ACS ($/MWh): average electricity cost including ACS health damages. | `systemcost`, `reqt_quant`, `../inputs_case/crf.csv`, `../inputs_case/val_r.csv`, `../inputs_case/df_capex_init.csv`, `../inputs_case/switches.csv`, `../inputs_case/scalars.csv`, `health_damages_caused_r.csv` | System cost, load quantity, financial helper files, and health damages all exist; health damages include `cr = acs` rows. |
| 55 | System cost + health damages: H6C ($/MWh): average electricity cost including H6C health damages. | Same as section 54 | Same as section 54, with `cr = h6c` rows. |
| 56 | NEUE (ppm): normalized expected unserved energy. | `neue.csv` | Resource-adequacy postprocessing produced `outputs/neue.csv` with year, iteration, and NEUE values. If PRAS/RA postprocessing is skipped, this is commonly absent. |
| 57 | Runtime (hours): process runtime by scenario. | `../meta.csv` | The run-level `meta.csv` exists and can be parsed into process time rows. |
| 58 | Runtime by year (hours): runtime split by model year/process. | `../meta.csv` | Same as section 57, with year-level process metadata available after runtime preprocessing. |

## Notes From `v20260610_TF_ND_small`

The current small smoke run solved far enough to produce many core outputs, but
its expanded report is not clean. The failures line up with optional or
small-case-sensitive report sections:

- Section 2 fails because `cap_iter` is absent from `outputs/outputs.h5`.
- Section 12 reads `opRes_supply_h` but fails during plotting, likely because
  the final-year/preset-filtered data is structurally empty or missing an
  expected plotted series.
- Section 38 fails because `outputs/land_use_total.csv` is absent.
- Sections 39, 40, 41, 43, and 44 fail after technology filters leave no
  plottable map data for the small case.
- Section 47 fails because `outputs/retail/retail_rate_USA_centsperkWh.csv` was
  not written after retail postprocessing failed.
- Sections 49 through 55 fail if `health_damages_caused_r.csv` does not match
  a schema that the report can normalize, or if health-damage preprocessing
  fails after loading.
- Section 56 fails because `outputs/neue.csv` is absent.

For a deliberately small smoke run, some of these can be expected gaps. For a
full standard test case, they are worth investigating unless the case settings
intentionally disable the corresponding postprocessor or technology family.

## Notes From `v20260611_Pacific`

This Pacific run is useful because several report failures can be traced to
specific switches or generated inputs:

- Section 2 fails because `cap_iter` is absent. The run uses `timetype=seq`, so
  the intertemporal capacity-by-iteration output is not expected for this
  sequential solve.
- Section 12 fails because `opRes_supply_h.csv` exists but is header-only.
  `GSw_OpRes=2` is not the direct cause; the simplified reserve formulation
  activates the `combo` reserve type. In this run, the representative-period
  file `inputs_case/rep/opres_periods.csv` is header-only, so `opres_h` is empty
  for the main solve and the operating-reserve equations generate zero rows.
  Stress-period folders have populated `opres_periods.csv`, but the standard
  expanded report reads the main reported `opRes_supply_h` output.
- Section 38 fails because `land_use_analysis=0`, so
  `outputs/land_use_total.csv` is not expected.

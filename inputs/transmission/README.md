# Transmission input files

- `b2b_converters.csv`: Power capacity and location of back-to-back (B2B) AC/DC/AC converters in the USA.
  - Power capacities are from [Brinkman et al. 2020](https://docs.nrel.gov/docs/fy21osti/78161.pdf) for converters at the eastern/western interface and [ERCOT 2020](https://www.ercot.com/files/docs/2020/07/30/ERCOT_DC_Tie_Operations_Document.docx) for converters at the eastern/texas interface.
  - Locations are from the [Open Infrastructure Map](https://openinframap.org/#4.1/40.65/-97.11).
  The `osm_id` column gives the OpenStreetMap ID of the converter; for example, the "Miles City, MT" converter (with `osm_id = 137835349`) can be found at <https://www.openstreetmap.org/way/137835349>.
  This file is used to validate the interface-level B2B capacity for different spatial resolutions stored at `inputs/zones/{GSw_ZoneSet}/b2b.csv`.

- `cost_hurdle_country.csv`: Hurdle rate for transmission flows [\$/MWh] between USA/Canada and USA/Mexico.

- `cost_hurdle_intra.csv`: Hurdle rate for transmission flows [\$/MWh] between ReEDS spatial hierarchy levels.

- `hvdc_lines.csv`: Power capacity and start/end locations of [high-voltage direct current (HVDC) lines](https://en.wikipedia.org/wiki/List_of_HVDC_projects#North_America) in the USA.
These lines are mapped to ReEDS zone interfaces during input processing.

- `itl_config.yaml`: Configuration file for interface transfer limit (ITL) calculations using the [TSC](https://github.nrel.gov/ReEDS/TSC) model.
Metadata only; not used directly in ReEDS.

- `itl_NARIS.csv`: Database of initial forward/reverse AC ITLs [MW] between pairs of connected ReEDS model zones for all supported zone resolutions.
Calculated using the [TSC](https://github.nrel.gov/pbrown/TSC) model as described by [Brown et al.](https://arxiv.org/abs/2308.03612) using nodal network data from [NARIS](https://www.nrel.gov/docs/fy21osti/79224.pdf).
  - The zone identifier is the md5 hash of the ','-delimited sorted list of 5-digit FIPS codes for the counties that define the zone.
    - For example, Delaware is 3 counties, with FIPS codes 10001, 10003, and 10005.
    Its delimited string is `10001,10003,10005`, and the md5 hash of that string is `a182e260da3f30b54260bf499f0db584`.
    (If on mac you can check it on the terminal with `$ echo -n 10001,10003,10005 | md5sum`.)
    - That hash is the same whether we call the zone `DE`, `Delaware`, `p125`, or something else.
    - The hash can be determined on the fly, but to make it easier to inspect, we record it for each supported spatial resolution in the `inputs/zones/{GSw_ZoneSet}/zonehash.csv` files.
  - The `itl_NARIS.csv` is indexed by the hashes of the two zones that define the interface (`md5_from` and `md5_to`).
    - So even though the `DE` and `MD` zones are used in many of the supported region resolutions, we only store the ITL for the `DE`/`MD` interface once, with `md5_from = a182e260da3f30b54260bf499f0db584` and `md5_to = f8644441280e76e07363ed18c744f98e`.
    - The interfaces to expect values for are listed in the `inputs/zones/{GSw_ZoneSet}/interfaces_{level}.csv` files, where `level` can be `r` or `transgrp`.
  - The most straightforward way to read all the ITLs for a given region resolution is to run the following commands from the root of the ReEDS repo with the `reeds2` conda environment activated:

    ```python
    import reeds
    ## GSw_ZoneSet can be any of the supported zone resolutions listed in the `GSw_ZoneSet` row of `cases.csv`
    GSw_ZoneSet = 'z134'
    reeds.inputs.get_itls(GSw_ZoneSet=GSw_ZoneSet)
    ```

- `rev_transmission_basecost.csv`: Base transmission costs (before terrain multipliers) used in reV.
Sources for numeric values are:
  - TEPPC: <https://www.wecc.org/Administrative/TEPPC_TransCapCostCalculator_E3_2019_Update.xlsx>
  - SCE: <http://www.caiso.com/Documents/SCE2019DraftPerUnitCostGuide.xlsx>
  - MISO: <https://cdn.misoenergy.org/20190212%20PSC%20Item%2005a%20Transmission%20Cost%20Estimation%20Guide%20for%20MTEP%202019_for%20review317692.pdf>
    - A more recent guide with a working link (as of 20230227) is available at <https://cdn.misoenergy.org/Transmission%20Cost%20Estimation%20Guide%20for%20MTEP22337433.pdf>.
  - Southeast: Private communication with a representative Southeastern utility

- `transmission_capacity_future_(ba|county)_baseline.csv` (DEPRECATED): Historically installed (since 2010) and currently planned transmission capacity additions at 134-zone resolution.
To be replaced with ITL-based estimates of the impacts of planned tranches of transmission system additions.

- `transmission_capacity_future_(ba|county)_{GSw_TransScen}.csv`: Available future routes for transmission capacity as specified by `GSw_TransScen`.

- `transmission_cost_ac_500kv_(ba|county).csv` and `transmission_distance_(ba|county).csv`: Distance and cost for a representative transmission route between each pair of 134 US ReEDS zones, assuming a 500 kV single-circuit line.
Routes are determined by the reV model using a least-cost-path algorithm accounting for terrain and land type multipliers.
Costs represent the appropriate base cost from `rev_transmission_basecost.csv` multiplied by the appropriate terrain and land type multipliers for each 90m pixel crossed by the path.
Endpoints are in inputs/shapefiles/transmission_endpoints and represent a point within the largest urban area in each of the 134 ReEDS zones.

- `transmission_cost_dc_(ba|county).csv`: Same as `transmission_cost_ac_500kv_(ba|county).csv` except assuming a 500 kV bipole DC line.

"""Harvest a tech-group capacity ceiling from a completed ReEDS run.

Reads a reference run's gross new capacity (`cap_new_out`) and writes the two
CSVs consumed by `eq_cepm_tg_cap_sys` / `eq_cepm_tg_cap_reg` (see
`reeds/core/setup/c_model.gms` and CEPM/guidance/two-step-re-limited-runs.md):

    inputs/growth_constraints/cepm_tg_cap_sys_{token}.csv   *tg,MW
    inputs/growth_constraints/cepm_tg_cap_reg_{token}.csv   *tg,r,MW

Both are always written; the one not selected by --scope is header-only, so a
scenario token always names a matched pair and the unused equation stays inert.

It also writes the per-year pair consumed by `eq_cepm_tg_cap_sys_t` /
`eq_cepm_tg_cap_reg_t` (active only with `GSw_CEPM_TgCap=2`):

    inputs/growth_constraints/cepm_tg_cap_sys_yr_{token}.csv   *tg,t,MW
    inputs/growth_constraints/cepm_tg_cap_reg_yr_{token}.csv   *tg,r,t,MW

where each value is the reference run's cumulative new capacity from
--from-year through solve year t. The totals above cap only the horizon sum,
which a myopic sequential solve can spend early; the per-year path also holds
the reference run's pace. The last solve year's per-year value equals the
horizon total, so turning the per-year path on never loosens the cap.

Units
-----
Output is MW_ac, matching `cap_new_out` exactly -- the equations divide `INV`
by `ilr(i)` so no conversion happens here. `ilr` is 1.0 for every technology
except UPV (1.34) and PVB, so for non-PV groups MW_ac is just MW.

Two things this script has to mirror from GAMS, or the ceiling silently
misstates what the constraint measures:

1. `tg_i` membership (`b_inputs.gms:794-807`) -- notably `tg 'pv'` is
   UPV + PVB *minus* distpv.
2. Upgrade-tech subset inheritance (`b_inputs.gms:412-413`) -- an upgrade tech
   inherits the subsets of the technology it upgrades *to*, so e.g.
   `hydED_pumped-hydro` belongs to `tg 'pumped-hydro'`. That inheritance happens
   at GAMS runtime and is NOT present in tech-subset-table.csv, so we redo it
   here from upgrade_link.csv. Without this the harvest would miss upgrade
   capacity that the constraint does count.

The zero floor
--------------
A value of 0 means "no cap" to GAMS, not "no builds" -- GAMS stores no record
for a zero, so an explicit 0 is indistinguishable from an absent row and the
equation's `$` guard drops it. Any requested group whose reference buildout is
genuinely zero therefore gets `--zero-floor` (default 0.001 MW) instead, and is
flagged in the summary. For a permanent, intentional zero use `bannew(i)`.

Prefer --scope region with the per-year path. A system-wide path still lets a
solve year place its share of a group's builds in any region. If a region then
has a prescribed build in a later year that its earlier builds don't already
cover, meeting it pushes the group past the path. The cap has no slack, so that
solve is infeasible. A regional path at --headroom >= 1 avoids this when the
capped run has the reference run's prescriptions and solve years: the reference
run's own buildout met every regional prescription at every solve year, and any
region with a prescription has a path because the reference run built there.
--scope both does not get that guarantee. Regions with no reference builds have
no regional path, and builds there still count against the system path.

Usage
-----
    python CEPM/scripts/make_tg_cap.py \
        --baseline-case runs/<Batch>_<stem>_baseline \
        --token <BatchName> [--scope system|region|both] \
        [--tgs pv,wind-ons,battery] [--headroom 1.00] \
        [--from-year 2026] [--to-year 2032] [--print-only]
"""

import argparse
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import reeds  # noqa: E402


# Mirrors tg_i(tg,i) in reeds/core/setup/b_inputs.gms:794-807. Values are
# tech-subset-table.csv column names.
TG_SUBSETS = {
    'wind-ons': ['ONSWIND'],
    'wind-ofs': ['OFSWIND'],
    'pv': ['UPV', 'PVB'],
    'csp': ['CSP'],
    'gas': ['GAS'],
    'coal': ['COAL'],
    'nuclear': ['NUCLEAR'],
    'battery': ['BATTERY'],
    'hydro': ['HYDRO'],
    'h2': ['H2_COMBUSTION'],
    'geothermal': ['GEO'],
    'biomass': ['BIO'],
    'pumped-hydro': ['PSH'],
    'dr_shed': ['DR_SHED'],
}

# tg_i('pv',i) is gated on $(not distpv(i)); no other group has an exclusion.
TG_EXCLUDE = {'pv': ['distpv']}

DEFAULT_TGS = ['pv', 'wind-ons', 'wind-ofs', 'csp', 'battery', 'pumped-hydro']


def build_tg_map(inputs_case):
    """Return {tech (lowercase): {tg, ...}} for the run's own tech set.

    Replicates tg_i plus the upgrade-tech subset inheritance that GAMS applies
    at b_inputs.gms:412-413.
    """
    groups = reeds.techs.import_tech_groups(
        os.path.join(inputs_case, 'tech-subset-table.csv'))
    # Normalize to lowercase; ReEDS is case-insensitive about technology names
    # but the CSVs are not internally consistent about casing.
    members = {col: {i.lower() for i in techs} for col, techs in groups.items()}

    # Upgrade techs inherit the subsets of the tech they upgrade TO (the DELTA
    # column), which is how e.g. hydED_pumped-hydro lands in tg 'pumped-hydro'
    # and Gas-CC_Gas-CC-CCS_mod lands in tg 'gas'.
    upgrade_link = os.path.join(inputs_case, 'upgrade_link.csv')
    inherited = 0
    if os.path.isfile(upgrade_link):
        links = pd.read_csv(upgrade_link)
        links.columns = ['to', 'from', 'delta']
        for _, row in links.iterrows():
            up, delta = str(row['to']).lower(), str(row['delta']).lower()
            for col, techs in members.items():
                if delta in techs:
                    techs.add(up)
                    inherited += 1
    else:
        print(f'[make_tg_cap] WARNING: no upgrade_link.csv in {inputs_case}; '
              'upgrade capacity will not be attributed to any tech group',
              file=sys.stderr)

    tg_map = {}
    for tg, cols in TG_SUBSETS.items():
        techs = set()
        for col in cols:
            techs |= members.get(col, set())
        for col in TG_EXCLUDE.get(tg, []):
            techs -= members.get(col, set())
        for tech in techs:
            tg_map.setdefault(tech, set()).add(tg)
    return tg_map, inherited


def harvest(case, tgs, from_year, to_year, headroom, zero_floor,
            clamp_to_floor=False):
    """Return (system Series indexed by tg, regional DataFrame, diagnostics)."""
    h5 = os.path.join(case, 'outputs', 'outputs.h5')
    if not os.path.isfile(h5):
        raise FileNotFoundError(
            f'{h5} not found -- the reference run did not complete. '
            'Note runreeds.py exits 0 even when a solve year fails, so never '
            'trust its exit code here.')

    df = reeds.io.read_output(case, 'cap_new_out')  # columns i, r, t, Value (MW_ac)
    # outputs.h5 stores float32; accumulate in float64 so the written ceiling is
    # exact rather than carrying ~1e-3 MW of rounding into a hard constraint
    # (which is also the order of --zero-floor).
    df['Value'] = df['Value'].astype('float64')
    inputs_case = os.path.join(case, 'inputs_case')
    tg_map, inherited = build_tg_map(inputs_case)

    df['tech'] = df['i'].str.lower()
    unmapped = sorted(set(df.loc[~df.tech.isin(tg_map), 'tech']))

    # Explode into (tg, r, t, Value); a tech belongs to exactly one default tg,
    # but the map is set-valued so a custom tg overlap would be caught here.
    df['tgs'] = df.tech.map(lambda x: sorted(tg_map.get(x, [])))
    df = df.explode('tgs').dropna(subset=['tgs']).rename(columns={'tgs': 'tg'})

    df = df[(df.t >= from_year) & (df.t <= to_year)]
    df = df[df.tg.isin(tgs)]

    # Builds in the first covered solve year are effectively all prescribed
    # (exogenous, already-committed plants), forced by eq_forceprescription as an
    # equality. Since eq_cepm_tg_cap_* has no slack, a ceiling below that floor
    # is infeasible -- the run dies with a bare "Model did not solve to
    # optimality" ~25 minutes in. Verified against CPLEX's conflict refiner: for
    # WECC-SW, battery 2026 builds = 7,852.6 MW == the prescribed_nonRSC total,
    # and pv 2026 builds = 11,423.3 == prescribed_rsc / ilr_utility.
    # This only bites for --headroom < 1; at 1.0 the cap is the reference run's
    # own buildout, which includes the prescriptions by construction.
    first_year = df.t.min() if len(df) else from_year
    floor_sys = df[df.t == first_year].groupby('tg').Value.sum()
    floor_reg = df[df.t == first_year].groupby(['tg', 'r']).Value.sum()

    sys_caps = df.groupby('tg').Value.sum() * headroom
    reg_caps = df.groupby(['tg', 'r']).Value.sum().reset_index()
    reg_caps['Value'] *= headroom

    if clamp_to_floor:
        # Raise any cell back up to its prescribed floor. A prescribed build
        # cannot be restrained by definition, so this is the honest behaviour --
        # but it means the effective ceiling is no longer a uniform fraction of
        # the reference run, so it is opt-in rather than silent.
        for tg in sys_caps.index:
            sys_caps.loc[tg] = max(float(sys_caps[tg]), float(floor_sys.get(tg, 0.0)))
        reg_caps['Value'] = [
            max(float(v), float(floor_reg.get((tg, r), 0.0)))
            for tg, r, v in zip(reg_caps.tg, reg_caps.r, reg_caps.Value)
        ]

    infeasible_sys = [
        (tg, float(sys_caps[tg]), float(floor_sys.get(tg, 0.0)))
        for tg in sys_caps.index if float(sys_caps[tg]) < float(floor_sys.get(tg, 0.0))
    ]
    infeasible_reg = [
        (f'{row.tg}/{row.r}', float(row.Value), float(floor_reg.get((row.tg, row.r), 0.0)))
        for row in reg_caps.itertuples()
        if float(row.Value) < float(floor_reg.get((row.tg, row.r), 0.0))
    ]

    # Requested groups with no builds at all still need a row, or they would be
    # uncapped rather than capped at zero (see the module docstring).
    floored = []
    for tg in tgs:
        if float(sys_caps.get(tg, 0.0)) <= 0.0:
            sys_caps.loc[tg] = zero_floor
            floored.append(tg)
    sys_caps = sys_caps.sort_index().round(3)
    reg_caps['Value'] = reg_caps['Value'].round(3)

    # Per-year cumulative path. Indexed by the reference run's own solve years,
    # not by the years that happen to have builds, so a group that builds nothing
    # until 2032 is still held near zero in 2026 and 2029 rather than left
    # uncapped there. Solve years come from modeledyears.csv.
    solve_years = [int(y) for y in reeds.io.get_years(case)
                   if from_year <= int(y) <= to_year]
    sys_path = path_by_year(
        df.groupby(['tg', 't']).Value.sum(), list(sys_caps.index), solve_years,
        headroom, zero_floor, floor_sys if clamp_to_floor else None)
    reg_path = path_by_year(
        df.groupby(['tg', 'r', 't']).Value.sum(),
        list(zip(reg_caps.tg, reg_caps.r)), solve_years,
        headroom, zero_floor, floor_reg if clamp_to_floor else None)

    return sys_caps, reg_caps, {'unmapped': unmapped, 'floored': floored,
                                'inherited': inherited,
                                'infeasible_sys': infeasible_sys,
                                'infeasible_reg': infeasible_reg,
                                'first_year': int(first_year),
                                'solve_years': solve_years,
                                'sys_path': sys_path,
                                'reg_path': reg_path}


def path_by_year(builds, keys, solve_years, headroom, zero_floor, floor=None):
    """Return {key: [(t, MW), ...]}, the cumulative ceiling at each solve year.

    `builds` is new capacity indexed by (*key, t). Each key gets a value for
    every solve year: the running sum through t, times headroom. With `floor`
    (the first-year prescribed builds), the first year is raised to it, as
    --clamp-to-floor does for the totals. The running max then keeps the path
    non-decreasing, since a cumulative ceiling that fell between years would
    demand negative investment. Values at or below zero get `zero_floor`, because
    a 0 means "no cap" to GAMS, not "no builds".
    """
    out = {}
    for key in keys:
        key_t = key if isinstance(key, tuple) else (key,)
        running, prev, rows = 0.0, 0.0, []
        for n, t in enumerate(solve_years):
            running += float(builds.get(key_t + (t,), 0.0))
            v = running * headroom
            if n == 0 and floor is not None:
                v = max(v, float(floor.get(key, 0.0)))
            v = max(v, prev)
            prev = v
            rows.append((t, round(v, 3) if v > 0.0 else zero_floor))
        out[key] = rows
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--baseline-case', required=True,
                   help='path to the completed reference run folder')
    p.add_argument('--out-dir', default=os.path.join('inputs', 'growth_constraints'))
    p.add_argument('--token', required=True,
                   help='cepmtgcapscen value; names the output files')
    p.add_argument('--scope', choices=['system', 'region', 'both'], default='system')
    p.add_argument('--tgs', default=','.join(DEFAULT_TGS),
                   help='comma-delimited tech groups to cap')
    p.add_argument('--headroom', type=float, default=1.00,
                   help='multiply the harvested ceiling by this factor')
    p.add_argument('--clamp-to-floor', action='store_true',
                   help='raise any cap below its prescribed-build floor back up to '
                        'that floor, keeping the run feasible at headroom < 1 '
                        '(the effective ceiling is then not a uniform fraction)')
    p.add_argument('--zero-floor', type=float, default=0.001,
                   help='MW written for a requested group with zero reference builds')
    p.add_argument('--from-year', type=int, default=2026)
    p.add_argument('--to-year', type=int, default=2032)
    p.add_argument('--print-only', action='store_true',
                   help='report the ceiling without writing any files')
    args = p.parse_args()

    tgs = [t.strip() for t in args.tgs.split(',') if t.strip()]
    unknown = [t for t in tgs if t not in TG_SUBSETS]
    if unknown:
        p.error(f'unknown tech group(s) {unknown}; known: {sorted(TG_SUBSETS)}')

    sys_caps, reg_caps, diag = harvest(
        args.baseline_case, tgs, args.from_year, args.to_year,
        args.headroom, args.zero_floor, args.clamp_to_floor)

    print(f'[make_tg_cap] reference run : {args.baseline_case}')
    print(f'[make_tg_cap] years         : {args.from_year}-{args.to_year} inclusive')
    print(f'[make_tg_cap] headroom      : {args.headroom:g}')
    print(f'[make_tg_cap] upgrade techs inherited into a tech group: {diag["inherited"]}')
    print(f'[make_tg_cap] ceiling (MW_ac), scope={args.scope}:')
    for tg in tgs:
        flag = '   <- ZERO FLOOR (no reference builds; capped at ~zero)' \
            if tg in diag['floored'] else ''
        nreg = int((reg_caps.tg == tg).sum())
        print(f'    {tg:14s} {float(sys_caps.get(tg, 0.0)):14,.3f}'
              f'   across {nreg} region(s){flag}')
    scope_hits = ((diag['infeasible_sys'] if args.scope in ('system', 'both') else [])
                  + (diag['infeasible_reg'] if args.scope in ('region', 'both') else []))
    if scope_hits:
        print(f'[make_tg_cap] *** WARNING: ceiling is below the {diag["first_year"]} '
              'prescribed-build floor for:')
        for name, cap, floor in scope_hits:
            print(f'      {name:20s} cap {cap:12,.3f} < prescribed {floor:12,.3f}')
        print('[make_tg_cap] *** Prescribed builds are forced by eq_forceprescription '
              '(an equality) and eq_cepm_tg_cap_* has no slack, so the run will very '
              'likely be INFEASIBLE in its first solve year.')
        print(f'[make_tg_cap] *** Raise --headroom (or --from-year past '
              f'{diag["first_year"]}, accepting that pre-{diag["first_year"] + 1} '
              'builds then go uncapped).')
    if diag['unmapped']:
        print(f'[make_tg_cap] NOTE: {len(diag["unmapped"])} technology(ies) in '
              f'cap_new_out map to no tech group (expected for distpv, o-g-s, '
              f'lfill-gas, can-imports, smr, dac, evmc): {diag["unmapped"]}')

    print(f'[make_tg_cap] per-year path (MW_ac, cumulative from {args.from_year}; '
          f'used only with GSw_CEPM_TgCap=2), solve years '
          f'{diag["solve_years"]}:')
    for tg in tgs:
        path = ', '.join(f'{t}: {v:,.1f}' for t, v in diag['sys_path'].get(tg, []))
        print(f'    {tg:14s} {path}')

    sys_path = os.path.join(args.out_dir, f'cepm_tg_cap_sys_{args.token}.csv')
    reg_path = os.path.join(args.out_dir, f'cepm_tg_cap_reg_{args.token}.csv')
    sys_yr_path = os.path.join(args.out_dir, f'cepm_tg_cap_sys_yr_{args.token}.csv')
    reg_yr_path = os.path.join(args.out_dir, f'cepm_tg_cap_reg_yr_{args.token}.csv')
    if args.print_only:
        print('[make_tg_cap] --print-only: no files written')
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    with open(sys_path, 'w', newline='') as f:
        f.write('*tg,MW\n')
        if args.scope in ('system', 'both'):
            for tg, v in sys_caps.items():
                if tg in tgs:
                    f.write(f'{tg},{v:.3f}\n')
    with open(reg_path, 'w', newline='') as f:
        f.write('*tg,r,MW\n')
        if args.scope in ('region', 'both'):
            for _, row in reg_caps.sort_values(['tg', 'r']).iterrows():
                f.write(f'{row.tg},{row.r},{row.Value:.3f}\n')
    with open(sys_yr_path, 'w', newline='') as f:
        f.write('*tg,t,MW\n')
        if args.scope in ('system', 'both'):
            for tg in sorted(diag['sys_path']):
                for t, v in diag['sys_path'][tg]:
                    f.write(f'{tg},{t},{v:.3f}\n')
    with open(reg_yr_path, 'w', newline='') as f:
        f.write('*tg,r,t,MW\n')
        if args.scope in ('region', 'both'):
            for (tg, r) in sorted(diag['reg_path']):
                for t, v in diag['reg_path'][(tg, r)]:
                    f.write(f'{tg},{r},{t},{v:.3f}\n')

    for path in (sys_path, reg_path, sys_yr_path, reg_yr_path):
        print(f'[make_tg_cap] wrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

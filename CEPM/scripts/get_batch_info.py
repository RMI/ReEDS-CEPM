"""Print info about the first non-ignored case in a cases file, for run_cepm.ps1.

Two things run_cepm.ps1 needs that only the cases file (not runreeds.py's own
output) can answer up front, both from the same case -- the first case
column, left to right, that is not marked ignore=1:
  - its name, to build the one run folder (runs/<BatchName>_<case>) that's
    guaranteed to exist regardless of which cases in the batch later succeed
    or fail, so bootstraplog.txt has somewhere to go; and
  - its model start year (the `yearset` switch's first 4 digits), to pass as
    compare_cases.py's --startyear, since that varies per cases file and
    compare_cases.py has no way to infer it on its own (falls back to a
    hardcoded 2020 otherwise).

Usage: python CEPM/scripts/get_batch_info.py <cases_filename>
    <cases_filename>: 'cases.csv' or 'cases_<suffix>.csv'

Output (stdout): the case name on line 1, and -- only if that case's
`yearset` switch starts with 4 digits -- the start year on line 2.

Exit codes:
    0  a non-ignored case was found (line 2 may still be absent)
    1  every case in cases_filename is marked ignore=1
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import reeds


def main():
    if len(sys.argv) != 2:
        print('[get_batch_info] usage: get_batch_info.py <cases_filename>', file=sys.stderr)
        return 1
    cases_filename = sys.argv[1]

    df_cases = reeds.inputs.parse_cases(cases_filename=cases_filename, skip_checks=True)
    casenames = [c for c in df_cases.columns if c not in ('Description', 'Default Value', 'Choices')]

    for case in casenames:
        if int(df_cases.loc['ignore', case]) == 1:
            continue
        print(case)
        yearset = str(df_cases.loc['yearset', case]).strip()
        startyear = yearset[:4]
        if startyear.isdigit():
            print(startyear)
        else:
            print(
                f"[get_batch_info] yearset '{yearset}' for case '{case}' does not start "
                "with 4 digits; omitting start year", file=sys.stderr)
        return 0

    print(f'[get_batch_info] no non-ignored case found in {cases_filename}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())

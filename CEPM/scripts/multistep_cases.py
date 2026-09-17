"""Validate and generate the cases file for run_cepm.ps1's two-step (-m) mode.

The two-step workflow (CEPM/guidance/two-step-re-limited-runs.md) runs three
cases built from one stem:

    <stem>_baseline    no data-center load, no ceiling -- source of the ceiling
    <stem>_limitre     data-center load, capped at the baseline's own buildout
    <stem>_optimized   data-center load, no ceiling

`_limitre` and `_optimized` must differ ONLY in the ceiling, and `_optimized`
must differ from `_baseline` ONLY in the load. This script guards the half of
that contract the orchestrator can actually check -- that the three columns
exist and that the cap switch is on for exactly one of them -- and then writes
the per-batch cases file that points `_limitre` at the harvested ceiling.

Two modes:

  --mode validate
      Fail loudly, before phase A burns an hour, if the cases file can't support
      a two-step run. Prints the baseline's start year (from `yearset`) on
      stdout so run_cepm.ps1 can use it for compare_cases.py's --startyear and
      for locating the bootstraplog destination, replacing get_batch_info.py's
      first-non-ignored-case convention (which is wrong under -m, since -s
      overrides `ignore`).

  --mode generate --token <BatchName> --out <path>
      Copy the cases file with `cepmtgcapscen` for the `_limitre` column set to
      <BatchName>, so that case picks up
      inputs/growth_constraints/cepm_tg_cap_{sys,reg}_<BatchName>.csv. Nothing
      else is touched. The generated file is deleted by run_cepm.ps1 in a
      `finally`; see 5.2(b) of the guidance doc for why this is preferred over a
      fixed token (two concurrent batches in one clone would clobber each
      other's ceiling).

Why validation resolves defaults rather than reading cells directly: a blank
cell in cases_cepm.csv inherits from that file's 'Default Value' column and then
from cases.csv, so `GSw_CEPM_TgCap` being visibly empty for `_optimized` is the
*correct* way to express 0. Reading the raw cell would report '' and tell us
nothing. Generation, by contrast, deliberately works on the raw file so the
written copy keeps every row, column and blank exactly as committed.

Usage:
    python CEPM/scripts/multistep_cases.py --mode validate \
        --cases-filename cases_cepm.csv --stem WECC-SW
    python CEPM/scripts/multistep_cases.py --mode generate \
        --cases-filename cases_cepm.csv --stem WECC-SW \
        --token v20260902m1 --out cases_cepm__v20260902m1.csv

Exit codes:
    0  success
    1  usage error, missing file, or failed validation
"""

import argparse
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import reeds  # noqa: E402


SUFFIXES = ('baseline', 'limitre', 'optimized')

# Expected GSw_CEPM_TgCap value per case, once defaults are resolved. This is the
# whole point of the factorial in section 1 of the guidance doc: exactly one of the
# three cases may carry a ceiling.
EXPECTED_TGCAP = {'baseline': 0, 'limitre': 1, 'optimized': 0}


def fail(msg):
    print(f'[multistep_cases] ERROR: {msg}', file=sys.stderr)
    return 1


def case_names(stem):
    return {sfx: f'{stem}_{sfx}' for sfx in SUFFIXES}


def validate(cases_filename, stem):
    """Check the cases file can support a two-step run on `stem`."""
    names = case_names(stem)

    try:
        df = reeds.inputs.parse_cases(cases_filename=cases_filename, skip_checks=True)
    except Exception as err:  # noqa: BLE001 - surface whatever parse_cases objected to
        return fail(f'could not parse {cases_filename}: {err}')

    missing = [n for n in names.values() if n not in df.columns]
    if missing:
        return fail(
            f'{cases_filename} has no case column(s): {", ".join(missing)}. '
            f'A two-step run needs all three of {", ".join(names.values())}.'
        )

    if 'GSw_CEPM_TgCap' not in df.index:
        return fail(
            f'GSw_CEPM_TgCap is not a switch in {cases_filename} or cases.csv. '
            'The cumulative tech-group caps are not plumbed into this checkout.'
        )

    problems = []
    for sfx, name in names.items():
        raw = df.loc['GSw_CEPM_TgCap', name]
        try:
            got = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            problems.append(f'  {name}: GSw_CEPM_TgCap is {raw!r}, which is not 0 or 1')
            continue
        want = EXPECTED_TGCAP[sfx]
        if got != want:
            problems.append(f'  {name}: GSw_CEPM_TgCap is {got}, expected {want}')

    if problems:
        return fail(
            'the three cases do not form a clean factorial -- exactly one of them '
            '(_limitre) may carry a ceiling:\n' + '\n'.join(problems)
        )

    # cepmtgcapscen must exist as a row we can substitute into during --mode generate.
    if 'cepmtgcapscen' not in df.index:
        return fail(
            f'cepmtgcapscen is not a switch in {cases_filename} or cases.csv, so there '
            'is nowhere to point the generated ceiling.'
        )

    # Advisory only: the two load cases should agree on everything but the ceiling.
    # A mismatch is not necessarily wrong (someone may be testing something), so warn.
    ignore_rows = {'GSw_CEPM_TgCap', 'cepmtgcapscen', 'ignore'}
    differing = [
        switch
        for switch in df.index
        if switch not in ignore_rows
        and str(df.loc[switch, names['limitre']]) != str(df.loc[switch, names['optimized']])
    ]
    if differing:
        print(
            f'[multistep_cases] WARNING: {names["limitre"]} and {names["optimized"]} differ '
            f'in {len(differing)} switch(es) besides the ceiling: {", ".join(differing)}. '
            'They are supposed to differ ONLY in the ceiling.',
            file=sys.stderr,
        )

    print(f'[multistep_cases] OK: {cases_filename} supports a two-step run on {stem}.',
          file=sys.stderr)

    # stdout line 1: the baseline case name (bootstraplog destination).
    print(names['baseline'])
    # stdout line 2 (optional): the baseline's model start year, for --startyear.
    yearset = str(df.loc['yearset', names['baseline']]).strip()
    if yearset[:4].isdigit():
        print(yearset[:4])
    else:
        print(
            f"[multistep_cases] WARNING: yearset '{yearset}' for {names['baseline']} does "
            'not start with 4 digits; omitting start year',
            file=sys.stderr,
        )
    return 0


def generate(cases_filename, stem, token, out_path):
    """Write a copy of the cases file with _limitre pointed at `token`."""
    names = case_names(stem)
    src = os.path.join(reeds.io.reeds_path, cases_filename)
    if not os.path.isfile(src):
        return fail(f'cases file not found: {src}')

    # Raw read, not parse_cases: we are writing a cases file back out, so every row,
    # column and blank has to survive untouched. parse_cases resolves defaults and
    # drops Choices/Description, which would rewrite the file's meaning.
    df = pd.read_csv(src, dtype=object, index_col=0)

    limitre = names['limitre']
    if limitre not in df.columns:
        return fail(f'{cases_filename} has no case column {limitre}')

    if 'cepmtgcapscen' not in df.index:
        # Legal but unexpected -- the switch may be inherited from cases.csv only.
        # Add the row so the token has somewhere to live.
        df.loc['cepmtgcapscen'] = pd.NA
        print(
            f'[multistep_cases] note: added a cepmtgcapscen row to {out_path} '
            f'({cases_filename} did not have one).',
            file=sys.stderr,
        )

    previous = df.loc['cepmtgcapscen', limitre]
    df.loc['cepmtgcapscen', limitre] = token

    out_abs = out_path if os.path.isabs(out_path) else os.path.join(reeds.io.reeds_path, out_path)
    # Match the source file's LF endings. Without this, to_csv writes CRLF on Windows and
    # every line of the generated file differs from the committed one, burying the single
    # cell that actually changed whenever someone diffs the two.
    df.to_csv(out_abs, lineterminator='\n')
    print(
        f'[multistep_cases] wrote {out_abs}: cepmtgcapscen for {limitre} '
        f'{previous!r} -> {token!r}',
        file=sys.stderr,
    )
    print(out_abs)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate/generate the cases file for run_cepm.ps1's two-step mode")
    parser.add_argument('--mode', required=True, choices=['validate', 'generate'])
    parser.add_argument('--cases-filename', required=True,
                        help="'cases.csv' or 'cases_<suffix>.csv'")
    parser.add_argument('--stem', required=True,
                        help='case stem, e.g. WECC-SW (without the _baseline suffix)')
    parser.add_argument('--token', default='',
                        help='generate mode: cepmtgcapscen value for the _limitre case')
    parser.add_argument('--out', default='',
                        help='generate mode: path of the cases file to write')
    args = parser.parse_args()

    if args.mode == 'validate':
        return validate(args.cases_filename, args.stem)

    if not args.token or not args.out:
        return fail('--mode generate requires both --token and --out')
    return generate(args.cases_filename, args.stem, args.token, args.out)


if __name__ == '__main__':
    sys.exit(main())

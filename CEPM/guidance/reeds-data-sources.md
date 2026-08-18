# How ReEDS finds its input files: `runfiles.csv` and `copy_files.py`

**Scope:** how a switch value in a `cases_*.csv` file turns into a path on disk,
and what that implies for where CEPM should put its own input data.

**Short version:** `reeds/input_processing/runfiles.csv` is the manifest that maps
switch values to input file paths. Because a switch only varies the *filename*
portion of a fixed directory template, every alternative for a given switch has
to be a sibling in the same directory. That is the constraint that decides where
CEPM inputs can live.

## What `runfiles.csv` is

Despite the name, it is not a list of CSVs — it is a **file-staging manifest**
with 270 data rows, and it governs the small, copyable, GAMS-bound inputs. Its
two load-bearing columns are the first two:

| Column | Meaning |
|---|---|
| `filename` | the **destination** name inside the case's `inputs_case/` folder |
| `filepath` | the **source** path, relative to the repo root, with `{switch_name}` placeholders |

The remaining columns (`required_if`, `aggfunc`, `disaggfunc`, `region_col`,
`fix_cols`, `wide`, `header`, `post_copy`, `GAMStype`, `GAMSname`, …) describe how
to filter, aggregate, and hand the file to GAMS. 60 rows carry `GAMStype`/
`GAMSname`, meaning they become GAMS symbols.

For the record, the extension distribution: 263 `.csv`, 2 `.yaml`, and one each of
`.gms`, `.h5`, `.toml`, `.txt`, `.py`. The `filename` and `filepath` extensions
match in all 270 rows, because staging a non-region file is a straight
`shutil.copy` (`copy_files.py:950`) with no format conversion.

Large binary timeseries mostly **bypass** this manifest: only one of the four
`.h5` files under `inputs/` is registered here. Profiles like `recf` and demand
are loaded by directly-constructed paths elsewhere (e.g. `reeds/io.py`, which
builds `inputs/profiles_demand/demand_{GSw_LoadProfiles}.h5` itself). So the CSV
dominance is partly a selection effect, not a claim that ReEDS inputs are all
CSVs.

## How the path gets resolved

The substitution is a single `str.format()` call in
`reeds/input_processing/copy_files.py` (in `read_runfiles`, around line 78):

```python
runfiles['full_filepath'] = runfiles.apply(
    axis=1,
    func=lambda row: os.path.join(inputs_case, row['filename'])
    if pd.isna(row['filepath'])
    else os.path.join(reeds_path, row['filepath'].format(**{**sw, **{'lvl': '{lvl}'}}))
)
```

Step by step:

1. `apply(axis=1)` runs once per manifest row.
2. If `filepath` is blank, the file is already in `inputs_case/` and only needs
   naming. (No row in this repo takes that branch — all 270 specify a source.)
3. Otherwise `{**sw, **{'lvl': '{lvl}'}}` builds the substitution mapping. `sw` is
   the switches `pd.Series` from `reeds.io.get_switches(inputs_case)`, read from
   the case's `inputs_case/switches.csv`.
4. `'lvl': '{lvl}'` maps `lvl` to its own placeholder text — a deliberate no-op,
   because `format()` raises `KeyError` on any placeholder it cannot resolve, and
   spatial resolution is not known to be single-valued yet. `{lvl}` therefore
   survives verbatim and is filled in later (around lines 103 and 601).
5. `format()` fills every other placeholder. 78 of 270 rows have at least one;
   some have two (`inputs/dgen_model_inputs/{distpvscen}/distpvcap_{distpvscen}.csv`).
6. `os.path.join(reeds_path, …)` makes it absolute.

Note for anyone tracing this in our fork: **no CSV in this repo uses `{lvl}`** —
it appears only inside `copy_files.py` itself. The mixed-resolution machinery that
explodes a row into `ba`/`county` variants is currently inert here. It is
forward-compatible with upstream rather than dead code, but it is not part of the
story for any file we actually stage.

### `required_if` and failure behavior

`required_if=1` makes a file mandatory: `copy_files.py` collects missing required
files and raises with the unresolved path listed (around lines 111-124). Note the
asymmetry — a **misspelled switch value** produces that helpful error, but a
**misspelled switch name** in the `filepath` template raises a bare
`KeyError: '<name>'` from inside the lambda, before the friendly check runs. If
you add a manifest row referencing a switch you forgot to declare in `cases.csv`,
that is the error you will see.

## What the `filename` column is really for

`inputs_case/` is a **flat namespace** — all 270 destination names are unique, and
each is a bare filename in one directory. The `filename` column exists to
normalize a hierarchy of scenario-specific source files into stable, flat,
scenario-independent names. It does three jobs:

**Strips the switch out of the name**, so downstream code reads a fixed filename.
`plantcostprep.py` reads `inputs_case/plantchar_gas.csv` without knowing which
variant was selected.

**Disambiguates collisions.** Four directories each contain a `dollaryear.csv`,
and the manifest renames them on copy:

```
inputs/consume/dollaryear.csv               -> dollaryear_consume.csv
inputs/plant_characteristics/dollaryear.csv -> dollaryear_plant.csv
inputs/fuelprices/dollaryear.csv            -> dollaryear_fuel.csv
inputs/supply_curve/dollaryear.csv          -> dollaryear_sc.csv
```

**Allows one source to serve two destinations.**
`inputs/upgrades/upgrade_mult_atb23_ccs_mid.csv` is staged twice, as
`upgrade_mult_advanced.csv` and `upgrade_mult_mid.csv`.

## Where the copy lands

This detail matters more than it looks. `write_non_region_files`
(`copy_files.py:965`) picks the destination directory from the **first path
segment of `filepath`**:

```python
if row['filepath'].split('/')[0] in ['inputs','postprocessing','tests']:
    dir_dst = inputs_case
else:
    dir_dst = os.path.dirname(inputs_case)   # the case root, runs/{case}/
```

Current distribution of that first segment: `inputs/` 265, `postprocessing/` 1,
`tests/` 1, and 3 rows with no directory at all (`Project.toml`, `gamslice.txt`,
`runreeds.py`) which are repo-root files that belong in the case root.

So the `else` branch exists to handle **repo-root files**, not to handle arbitrary
new top-level directories. Any path under a top-level directory not on that
allowlist gets copied to `runs/{case}/` instead of `runs/{case}/inputs_case/` —
silently, with no error, since the copy itself succeeds.

## Companion registries that are also location-aware

A file's path is not the only thing tied to its location. Two separate deflator
mechanisms exist, and both are registries you have to update alongside a new
input:

**`docs/sources.csv`** — read by `get_source_deflator_map` (`copy_files.py:158`),
keyed by `RelativeFilePath` (repo-root-relative, leading `/` stripped, e.g.
`/inputs/plant_characteristics/battery_ATB_2024_advanced.csv`) with a
`DollarYear` column. Files whose monetary values need deflating are looked up
directly in that dict, so a missing entry is a `KeyError`.

**Per-directory `dollaryear.csv`** — used by `plantcostprep.py`'s `deflate_func`,
keyed by the **switch value** rather than a path:

```python
def deflate_func(data, case):
    deflate = dollaryear.loc[dollaryear['Scenario'] == case, 'Deflator'].values[0]
```

The `.values[0]` means an unregistered scenario name raises `IndexError`, not a
clear message. Note this reads the *staged* copies
(`inputs_case/dollaryear_plant.csv` + `dollaryear_consume.csv`), which are
themselves staged through the manifest.

## Worked example: `plantchar_gas`

The full chain for `USA_gas_mvp` in `cases_cepm.csv`:

1. `cases_cepm.csv` sets `plantchar_gas = gas_CAPEX_ccgt_all`, overriding the
   `cases.csv` default `gas_ATB_2024_moderate`. `cases.csv` also documents the
   convention: `inputs\plant_characteristics\{plantchar_gas}.csv`.
2. `runreeds.py` writes the resolved switches to `inputs_case/switches.csv`.
3. `runfiles.csv` row: `plantchar_gas.csv,inputs/plant_characteristics/{plantchar_gas}.csv,1,…`
4. `copy_files.py` formats it to
   `inputs/plant_characteristics/gas_CAPEX_ccgt_all.csv` and copies it to
   `inputs_case/plantchar_gas.csv`.
5. `plantcostprep.py` reads the generic `inputs_case/plantchar_gas.csv`, and uses
   the switch value once more for the deflator lookup — which is why
   `inputs/plant_characteristics/dollaryear.csv` needs a
   `gas_CAPEX_ccgt_all,2022` row (it has one).

### The manifest itself can be swapped per case

`copy_files.py:49-53` prefers the `runfiles.csv` colocated with the executing
script (the case-local copy) over the repo one. Combined with the
`file_replacements` switch, a case can substitute a whole different manifest —
`USA_gas_mvp` sets:

```
reeds/input_processing/runfiles.csv << reeds/input_processing/runfiles_no_new_windsolar_ccs.csv
```

If a path is not resolving as you expect for a given case, check which manifest
that case is actually using.

## What this means for where CEPM inputs should live

The decisive mechanic is that **each logical input gets one row with one path
template, and the switch varies only the filename portion — never the
directory.** `inputs/plant_characteristics/{plantchar_gas}.csv` can only ever
resolve inside `inputs/plant_characteristics/`.

### If we want to keep access to ReEDS default options: use `inputs/`

Put bespoke CEPM input files in the existing `inputs/` subdirectories, alongside
the upstream files they are alternatives to.

Because the switch selects among **siblings in a single directory**, an upstream
default and a CEPM variant must co-locate for the switch to be able to choose
between them. `plantchar_gas` can only flip between `gas_ATB_2024_moderate` and
`gas_CAPEX_ccgt_all` because both are in `inputs/plant_characteristics/`. Moving
our file elsewhere would force us to either rewrite the template — losing the
ability to select the upstream default at all — or add a second switch and
another manifest row.

This is what we already do, and it is the right default. The cost is that our
files sit interleaved with upstream ones, so the divergence is not visible from
the directory tree; that is what `CEPM/reeds-to-cepm-log.md` is for. Practical
checklist when adding one:

- name it so it is recognizable as ours and matches the switch's documented
  prefix convention (`cases.csv` records the allowed pattern per switch)
- add the option to the switch's documentation row in `cases.csv`
- register the dollar year — `docs/sources.csv` and/or the directory's
  `dollaryear.csv`, per the mechanisms above
- if the file is genuinely new rather than an alternative, add a `runfiles.csv`
  row and keep the destination `filename` unique

### If a switch's options were entirely ours: `CEPM/inputs/` is possible

For an input where we never intend to select an upstream default, the source
directory is unconstrained. `filepath` is just `os.path.join`ed to `reeds_path`,
so any repo-relative path resolves — including `CEPM/inputs/…`. That would make
the fork's data surface visible in one place instead of scattered through
`inputs/`.

It is not free, though. Verified prerequisites:

1. **Extend the destination allowlist.** `copy_files.py:965` routes by first path
   segment. `CEPM/inputs/foo.csv` would fall to the `else` branch and land in
   `runs/{case}/` rather than `inputs_case/`, silently — downstream scripts
   reading `inputs_case/foo.csv` would then fail with a confusing missing-file
   error. Adding `'CEPM'` to that list is a one-line change, but it is a change to
   an upstream file, so it belongs in the divergence log.
2. **Register deflators by the new path.** `docs/sources.csv` is keyed by
   repo-relative path, so entries would need to read `/CEPM/inputs/…`.
3. **Carry the `dollaryear.csv` convention** into any new directory whose files
   feed `plantcostprep.py`, and stage it through the manifest as the four
   existing ones are.
4. **Keep destination names unique** across all manifest rows, since
   `inputs_case/` stays flat regardless of source layout.

### Recommendation

Default to `inputs/`. Reach for `CEPM/inputs/` only for a category of input that
is wholly CEPM's, where we would never want the upstream option — and treat items
1-4 above as the entry cost. A hybrid, where some switches resolve into `inputs/`
and others into `CEPM/inputs/`, is workable but makes "where does this input come
from?" a two-place question, so it is worth deciding per input category rather
than drifting into it.

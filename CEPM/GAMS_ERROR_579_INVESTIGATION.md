# GAMS Error 579 in the h5-to-gdx input pipeline

**Status:** Fixed on `fix/GAMS-h5-bugfix`
**Affected versions:** GAMS 44.4.0 (this repo's pinned version)
**Symptom:** `a_createmodel.gms` fails to compile with 16x `*** Error 579` in
`autocode/b_load_sets.gms`, immediately after `copy_files.py`/`h5_to_gdx.py`
finish input processing.

## The issue

Every ReEDS-CEPM run that reached the model-compile step failed with:

```
*** Error 579 in .../autocode/b_load_sets.gms
    Cannot clear a set used as a domain or used in lag/ord operations
```

repeated 16 times, followed by `*** Status: Compilation error(s)`. This
reproduced identically on two unrelated cases (`ND_small` and `Pacific`),
confirming it wasn't specific to any one case's switches — it was a
structural bug in how GAMS code gets generated for every run.

## Investigation

### What the pipeline does

`reeds/input_processing/h5_to_gdx.py` reads every set/parameter out of
`inputs.h5` (the consolidated output of `copy_files.py` and friends), writes
them to a GDX file (`inputs_0.gdx`), and auto-generates four GAMS snippets
that `reeds/core/setup/b_inputs.gms` includes:

```gams
$include autocode/b_declare_sets.gms       ' declares EVERY set
$include autocode/b_declare_parameters.gms ' declares EVERY parameter
$gdxin inputs_case/inputs_0.gdx
$include autocode/b_load_sets.gms          ' $loadDCR's EVERY set
$include autocode/b_load_parameters.gms
$gdxin
```

### Root cause

`b_declare_sets.gms` declares primary (domain-less) sets first, then the
domain-based subsets that depend on them, e.g.:

```gams
set r(*) ;
...
set offshore(r) ;      ' uses r as a domain
set e(eall) ;           ' uses eall as a domain
set fuel2tech(f,i) ;    ' uses f and i as domains
```

Because **all** declarations run before **any** loads, by the time GAMS
reaches `$loadDCR r = r`, `r` has already been referenced as a domain by
`offshore(r)` — and GAMS refuses to clear/reload (`$loadDCR`) a set once
anything else depends on it as a domain. This affects every primary set
that has at least one dependent subset or parameter: `r`, `i`, `v`, `e`,
`eall`, `f`, `p`, `wst`, `allt`, `geotech`, `h2_st`, `hintage_char`,
`ofstype`, `pcat`, `pvb_config`, `trtype` — exactly the 16 sets that
errored.

Confirmed directly by reproducing the mechanism in a minimal standalone
`.gms` script (declare a set, declare a subset domained on it, then
`$loadDCR` the parent) against the installed GAMS 44.4.0 — it fails with
the identical Error 579. Interleaving declare+load per set (load the
parent before declaring any subset of it) compiles clean on the same GAMS
install.

### Why upstream doesn't hit this

Upstream (`ReEDS-Model/ReEDS`) has the *identical* declare-all-then-load-all
structure in `b_inputs.gms` and `h5_to_gdx.py` — this isn't a fork-specific
regression. The only upstream commits touching this area are two narrow,
reactive patches (`special_keys = ['r']`, then `special_keys = ['r', 'v']`),
neither of which actually changes the declare-before-load ordering that
causes the lock (verified by inspecting `sort_primary_first()`, which
always groups all primary-set declarations before all subset declarations
regardless of input order).

The real explanation is a GAMS version difference. GAMS's official release
notes for **45.6.0** (2024-01-04) state:

> "Changed `$loadDCR` to not complain anymore when it should be used to
> clear a set, that is used as domain, if that set had no data so far."

That is precisely this bug. GAMS 44's full 44.x patch history (44.1.0
through 44.4.0) never received this fix — it first shipped in 45.6.0, a
full minor version later. Upstream tests on GAMS 49.6.0/51.3.0 (both well
past 45.6.0), so their identical code never trips this restriction. Since
this repo is pinned to GAMS 44.4.0, there is no upstream fix to adopt —
the incompatibility only exists on our GAMS version.

## The fix

Since GAMS 44.4.0 requires that a set never be used as a domain before
it's loaded, `h5_to_gdx.py` now generates a single `autocode/b_sets.gms`
that declares and `$loadDCR`s each set immediately, one at a time —
primary sets first, then domain-based subsets — instead of declaring every
set and only then loading every set. Parameters are unaffected (a
parameter can never be used as another symbol's domain in GAMS) and keep
their existing declare-then-load split, now placed after all sets have
finished loading.

Changed files:
- `reeds/input_processing/h5_to_gdx.py` — added
  `write_sets_declare_and_load()`; `main()` now calls it for sets instead
  of the old declare-all/load-all `write_declaration`/`write_gdxread`
  pair (still used for parameters).
- `reeds/core/setup/b_inputs.gms` — includes the new `autocode/b_sets.gms`
  in place of `b_declare_sets.gms`/`b_load_sets.gms`, with `$gdxin` opened
  first so sets can be loaded inline as they're declared.

Also cherry-picked from upstream for alignment (unrelated to this bug, but
touches the same function):
- `h5_to_gdx.py: add v to special_keys` (upstream commit `066d8fe6`)

## Verification

Regenerated `autocode/` for a previously-failing run
(`runs/v20260811_132136_ND_small`) using the fixed `h5_to_gdx.py` against
its existing `inputs.h5`, then recompiled `a_createmodel.gms` directly with
the same case switches originally used:

- **Before:** 16x `Error 579`, `Status: Compilation error(s)`
- **After:** `Status: Normal completion`, restart file (`.g00`) written
  successfully

No other case-specific behavior changed — the fix only reorders when
generated GAMS statements execute, not what sets/parameters exist or what
data they contain.

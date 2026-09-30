# Translating between `environment.yml` (mamba/conda) and `pyproject.toml`/`uv.lock` (uv)

This repo keeps both, per the decision to keep `environment.yml` as the
upstream-compatible fallback and `pyproject.toml`/`uv.lock` as RMI's primary
path.
Whenever one changes, the other should be updated by hand — there's no
automatic converter, so this is a manual mapping.

## Automated drift check

`CEPM/scripts/check_env_sync.py` compares the two files and warns when they drift beyond
a hard-coded allowlist of intentional exceptions (the "known-accepted" cases
below). `run_cepm.ps1` runs it as a non-fatal step, or run it directly:

```bash
uv run python CEPM/scripts/check_env_sync.py
```

It reports three things: packages only in `environment.yml`, packages only in
`pyproject.toml`, and packages pinned to incompatible versions. Exit code `0` means aligned (all differences are on the
allowlist); `1` means new/unexpected drift. When you intentionally add an
exception, update both the allowlist in `CEPM/scripts/check_env_sync.py` and the
"Known current drift" / "Things that don't map 1:1" sections below so the two
stay in agreement.

## Structural mapping

| environment.yml | pyproject.toml | Notes |
|---|---|---|
| `name: reeds` | `[project] name = "ReEDS"` | Names don't have to match; conda's is the env name, uv's is the package/distribution name. |
| `dependencies: - python=3.14` | `[project] requires-python = "==3.14.*"` | Also mirrored in `.python-version` (`3.14`); the two must move together. `run_cepm.ps1` reads `requires-python` automatically. |
| `dependencies:` (conda channel packages, no `pip:` block) | `[project] dependencies = [...]` | Top-level conda deps → top-level uv deps. |
| `dependencies: - pip: - ...` (the nested pip list) | `[project] dependencies = [...]` | Conda draws a line between conda-channel and pip-installed packages; uv doesn't — everything just goes in one `dependencies` list. |
| Comment-delimited "optional" blocks (`## vvv ... ## ^^^`) | `[project.optional-dependencies]` groups (`interactive`, `maps`, `reporting`, `network`, `testing`, `dev`) | conda has no native optional-group syntax, so it uses a comment convention. uv has real extras — prefer putting new optional packages in the right extras group instead of a top-level comment block. |
| version pins like `bokeh=3.2` | `"bokeh==3.2.*"` | conda's single `=` is a "starts with" match; uv/pip needs `==` plus an explicit `.*` to get the same "any patch version" behavior. |
| N/A | `dev = [...]` group | uv's `dev` extra is just a bundle of the others (currently duplicates `interactive` + `maps` + `reporting` + `network` + `testing`). Keep it in sync manually — there's no "include another extra" syntax in this pyproject's toml version. |

**No `docs` extra**: the docs build (`.github/workflows/build-docs.yaml`)
pip-installs its own dependencies on Python 3.12.

## Adding a new dependency

1. **Figure out where it's used.** Is it a hard runtime dependency (imported directly in `reeds/`, `hourlize/`, or `runreeds.py`) or something only needed for docs/interactive/testing?
2. **Add it to `environment.yml`:**
   - If it's on conda-forge/defaults, add it as a top-level line under `dependencies:` with a conda-style pin (`package=X.Y`).
   - If it's pip-only, add it under the nested `pip:` list with a `==X.Y.Z` pin.
   - If it's optional, put it inside the commented `## vvv ... ## ^^^` block (top-level optional) or the nested pip optional block.
3. **Add it to `pyproject.toml`:**
   - Hard dependency → `[project.dependencies]`, using `==X.Y.*` (or an exact pin if you want to match conda's pin precisely).
   - Optional → the matching `[project.optional-dependencies]` group, **and** add it to the `dev` group too if `dev` is supposed to be "everything."
4. **Regenerate the lockfile:** `uv lock` (or `uv sync --extra dev` if you also want your local venv updated). Don't hand-edit `uv.lock`.
5. **Sanity-check both paths still work:**
   - `uv sync --extra dev && uv run python runreeds.py -h`
   - `mamba env update -f environment.yml` (or recreate the env) if you're validating the conda side too.

## Removing a dependency

Same as above in reverse — pull it from both files, then `uv lock` to drop it (and anything only it depended on) from `uv.lock`.

## Things that don't map 1:1

- **Non-Python packages.** `environment.yml` has `git-lfs=3.7` and `mscorefonts=0.0` — these aren't pip-installable and have no uv equivalent. They just don't appear in `pyproject.toml`; document them in setup docs instead.
- **`pip` itself and its version.** conda pins `pip=26.1` as a bootstrap tool; uv manages its own resolver, so this has no uv equivalent either.
- **Exact vs. fuzzy pins.** conda's `package=X.Y` conventionally means "X.Y.* is fine"; the uv side in this repo mostly uses explicit `==X.Y.*` to match that intent, but `tables==3.11.1` and `pyproj==3.8.0` are pinned to an exact patch version in `pyproject.toml` (conda pins `pytables=3.11` and has no `pyproj` line). `gdxpds`, `pulp`, `gamsapi` and `gamspy-base` are pinned exactly on both sides. If you tighten/loosen a pin on one side, consider whether the other side should match.
- **PyTables naming.** conda's package is `pytables`, but its importable/pip name is `tables`, so it appears as `pytables=3.11` in `environment.yml` and `tables==3.11.1` in `pyproject.toml` — same version, different name, handled by `NAME_ALIASES` in `check_env_sync.py`.
- **Git-sourced packages.** None currently. Don't re-add `rmi.etoolbox` (it pins `pandas<2.4`).
- **`pyproj` and `networkx`.** `pyproj` (`reeds/plots.py`) and `networkx` (`preprocessing/downselect_hvdc.py`) are declared only in `pyproject.toml`. Allowlisted in `check_env_sync.py`'s `UV_ONLY_OK`.
- **`pillow`.** Declared only in `pyproject.toml` (`reporting`/`dev`), no `environment.yml` line. Added explicitly to force a Python 3.14-compatible release, overriding `python-pptx`'s own old floor — see "Deliberate deviations from environment.yml" in `reeds-to-cepm-log.md`. Allowlisted in `UV_ONLY_OK`.
- **`myst-parser`, `sphinx`, `sphinx-design`, `sphinx-rtd-theme`, `sphinxcontrib-bibtex`.** Declared only in `environment.yml` as of the August 2026 sync — the `docs` extra was removed from `pyproject.toml` entirely, since the real docs build bypasses `uv`/`pyproject.toml` (see the "No `docs` extra" note above). Allowlisted in `CONDA_ONLY_OK`.
- **`python-abi`.** Appears in `environment.yml` as conda's ABI-tagging metadata, not a real installable package — has no `pyproject.toml` equivalent by nature, allowlisted in `CONDA_ONLY_OK`.

## Known pre-existing gaps (not introduced by this cleanup, not yet fixed)

`seaborn` (`postprocessing/uncertainty_plots.py`) and `loguru`
(`postprocessing/run_r2x.py`, installed alongside `r2x-reeds` in CI) are in
neither file. `jinja2`, `lxml` and `six` resolve transitively.

## Known current drift between the two files

None (`KNOWN_DRIFT_*` sets are empty).

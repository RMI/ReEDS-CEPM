# Translating between `environment.yml` (mamba/conda) and `pyproject.toml`/`uv.lock` (uv)

This repo keeps both, per the decision to keep `environment.yml` as the
upstream-compatible fallback and `pyproject.toml`/`uv.lock` as RMI's primary
path (see `pyproject.toml` at repo root and `dev`'s `environment.yml`).
Whenever one changes, the other should be updated by hand — there's no
automatic converter, so this is a manual mapping.

## Structural mapping

| environment.yml | pyproject.toml | Notes |
|---|---|---|
| `name: reeds2` | `[project] name = "ReEDS"` | Names don't have to match; conda's is the env name, uv's is the package/distribution name. |
| `dependencies: - python=3.11` | `[project] requires-python = "==3.11.*"` | Also mirrored in `.python-version` (`3.11`). |
| `dependencies:` (conda channel packages, no `pip:` block) | `[project] dependencies = [...]` | Top-level conda deps → top-level uv deps. |
| `dependencies: - pip: - ...` (the nested pip list) | `[project] dependencies = [...]` | Conda draws a line between conda-channel and pip-installed packages; uv doesn't — everything just goes in one `dependencies` list. |
| Comment-delimited "optional" blocks (`## vvv ... ## ^^^`) | `[project.optional-dependencies]` groups (`interactive`, `maps`, `docs`, `reporting`, `network`, `testing`, `dev`) | conda has no native optional-group syntax, so mvp used a comment convention. uv has real extras — prefer putting new optional packages in the right extras group instead of a top-level comment block. |
| version pins like `bokeh=3.2` | `"bokeh==3.2.*"` | conda's single `=` is a "starts with" match; uv/pip needs `==` plus an explicit `.*` to get the same "any patch version" behavior. |
| N/A | `dev = [...]` group | uv's `dev` extra is just a bundle of the others (currently duplicates `interactive` + `maps` + `docs` + `reporting` + `network` + `testing`). Keep it in sync manually — there's no "include another extra" syntax in this pyproject's toml version. |

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

- **Non-Python packages.** `environment.yml` has `git-lfs=2.13` and `mscorefonts=0.0` — these aren't pip-installable and have no uv equivalent. They just don't appear in `pyproject.toml`; document them in setup docs instead.
- **`pip` itself and its version.** conda pins `pip=23.2` as a bootstrap tool; uv manages its own resolver, so this has no uv equivalent either.
- **Exact vs. fuzzy pins.** conda's `package=X.Y` conventionally means "X.Y.* is fine"; the uv side in this repo mostly uses explicit `==X.Y.*` to match that intent, but a few packages (`tables`, `gdxpds`, `geopandas`, `pulp`, `shapely`, `cmocean`) are pinned to an exact patch version in `pyproject.toml` where conda only pins minor. If you tighten/loosen a pin on one side, consider whether the other side should match.
- **Git-sourced packages.** `rmi.etoolbox @ git+https://github.com/rmi/etoolbox.git` in `pyproject.toml` has no equivalent line in `environment.yml` yet — conda's `pip:` block *can* take a `git+https://...` URL the same way, so if `environment.yml` needs to stay fully equivalent, add a matching line there.

## Known pre-existing gaps (not introduced by this cleanup, not yet fixed)

A few packages are imported directly in `postprocessing/` (`jinja2`, `loguru`, `lxml`, `seaborn`, `six`) but aren't declared as explicit dependencies in *either* file — they currently work only because something else pulls them in transitively. This gap already exists on the `dev`/upstream base itself, independent of the RMI rebase, so it wasn't in scope for the pyproject.toml restoration. Worth its own follow-up if these ever stop being transitively satisfied.

## Note: `environment.yml` is currently missing from this branch

The "keep both" decision assumes `environment.yml` exists alongside
`pyproject.toml`, but it was deleted by the mvp-branch commit that introduced
uv (`801ae3eb`, "changes to pyproject toml for UV, removed environment.yml
and added python version") and that deletion is still in effect on this
branch. `dev` still has it. Until it's restored from `dev`, this guide
describes a mapping that only exists on one side.

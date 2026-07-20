"""Check that environment.yml (mamba/conda) and pyproject.toml (uv) stay aligned.

RMI/CEPM keeps `environment.yml` as an upstream-compatible conda/mamba fallback
and `pyproject.toml`/`uv.lock` as the primary uv path (see
CEPM/UV_MAMBA_GUIDE.md). There is no automatic converter, so the two are kept in
sync by hand and drift easily. This script reports drift and warns only when it
finds a difference that is NOT already on the known-accepted allowlist below.

It is intentionally stdlib-only (tomllib is in Python 3.11) so it can run as a
bootstrap step without depending on a fully synced environment.

Exit codes:
    0  aligned (all differences are on the allowlist)
    1  unexpected drift found (bootstrap turns this into a warning, not a failure)
    2  could not run the check (e.g. a file is missing or unparseable)

Keeping the allowlist current: as drift is reconciled, remove entries here. The
script also notes allowlist entries that no longer apply, so the list does not
silently rot.
"""

import os
import re
import sys
import tomllib

# --- Known-accepted exceptions (see CEPM/UV_MAMBA_GUIDE.md) ------------------

# Packages expected to live ONLY in environment.yml -- no uv/pip equivalent by
# nature (non-Python packages, conda bootstrap tooling, the interpreter itself).
CONDA_ONLY_OK = {"git-lfs", "mscorefonts", "pip", "python"}

# Packages expected to live ONLY in pyproject.toml (e.g. git-sourced deps that
# have no conda-channel equivalent line yet).
UV_ONLY_OK = {"rmi-etoolbox"}

# Currently-accepted drift, documented in CEPM/UV_MAMBA_GUIDE.md. Trim as fixed.
KNOWN_DRIFT_CONDA_ONLY = {"proj"}          # in environment.yml, not in pyproject
KNOWN_DRIFT_UV_ONLY = {"pyyaml"}           # in pyproject, not in environment.yml
KNOWN_VERSION_MISMATCH = {"tables"}        # pytables 3.8 (conda) vs tables 3.11.1 (uv)

# conda package name -> pip/import name, so the same package matches across files.
NAME_ALIASES = {"pytables": "tables"}


def normalize(name):
    """PEP 503-style normalization (collapse runs of . _ - to a single -) plus
    conda->pip aliasing."""
    n = re.sub(r"[-_.]+", "-", name.strip().lower())
    return NAME_ALIASES.get(n, n)


def _clean_version(ver):
    """Strip a trailing '.*' / '*' wildcard and surrounding dots/space."""
    ver = ver.strip().rstrip("*").rstrip(".").strip()
    return ver or None


def split_conda_spec(item):
    """Parse a conda/pip dependency line ('bokeh=3.2', 'pulp==2.7.0', 'python')."""
    for sep in ("==", "="):
        if sep in item:
            name, _, ver = item.partition(sep)
            return name.strip(), _clean_version(ver)
    return item.strip(), None


def parse_requirement(spec):
    """Parse a PEP 508 requirement from pyproject ('bokeh==3.2.*', 'x @ git+...')."""
    spec = spec.strip()
    if " @ " in spec:  # url/git form: 'name @ https://...'
        return spec.split(" @ ", 1)[0].strip(), None
    match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", spec)
    if not match:
        return spec, None
    name, rest = match.group(1), match.group(2)
    ver_match = re.search(r"==\s*([0-9][0-9A-Za-z.\-]*)", rest)
    ver = _clean_version(ver_match.group(1)) if ver_match else None
    return name, ver


def parse_environment_yml(path):
    """Minimal parser for our environment.yml -> {normalized_name: version|None}.

    Tailored to this file's shape (a top-level `dependencies:` list plus a nested
    `- pip:` list); not a general YAML parser. Both conda-channel and pip entries
    are collected into one map since the comparison is by package, not channel.
    """
    deps = {}
    in_deps = False
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if "#" in line:  # drop inline/full-line comments (incl. '## vvv' blocks)
                line = line[: line.index("#")]
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "dependencies:":
                in_deps = True
                continue
            if not in_deps:
                continue
            indent = len(line) - len(line.lstrip(" "))
            # A new top-level key (e.g. `channels:`) ends the dependencies block.
            if indent == 0 and not stripped.startswith("-"):
                in_deps = False
                continue
            if not stripped.startswith("-"):
                continue
            item = stripped[1:].strip()  # drop the leading '- '
            if not item or item.rstrip(":") == "pip":  # the '- pip:' sub-list header
                continue
            name, version = split_conda_spec(item)
            if name:
                deps[normalize(name)] = version
    return deps


def parse_pyproject(path):
    """Return {normalized_name: version|None} across dependencies + all extras."""
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project", {})
    specs = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        specs.extend(group)
    deps = {}
    for spec in specs:
        name, version = parse_requirement(spec)
        if name:
            deps[normalize(name)] = version
    return deps


def versions_align(conda_ver, uv_ver):
    """True if versions are compatible. conda's 'X.Y' means 'X.Y.*', so treat a
    shorter version as a prefix match of the longer one (e.g. 3.2 ~ 3.2.*)."""
    if conda_ver is None or uv_ver is None:
        return True  # nothing to compare (e.g. a git dep with no pinned version)
    left = conda_ver.split(".")
    right = uv_ver.split(".")
    shared = min(len(left), len(right))
    return left[:shared] == right[:shared]


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) == 3:  # optional explicit paths, mostly for testing
        env_path, pyproject_path = sys.argv[1], sys.argv[2]
    else:
        env_path = os.path.join(repo_root, "environment.yml")
        pyproject_path = os.path.join(repo_root, "pyproject.toml")

    try:
        env_deps = parse_environment_yml(env_path)
        uv_deps = parse_pyproject(pyproject_path)
    except FileNotFoundError as exc:
        print(f"[check_env_sync] could not read a dependency file: {exc}")
        return 2
    except Exception as exc:  # never let this check crash the bootstrap
        print(f"[check_env_sync] failed to parse dependency files: {exc}")
        return 2

    env_names = set(env_deps)
    uv_names = set(uv_deps)

    conda_only = env_names - uv_names
    uv_only = uv_names - env_names
    mismatches = {
        name
        for name in (env_names & uv_names)
        if not versions_align(env_deps[name], uv_deps[name])
    }

    unexpected_conda_only = sorted(conda_only - CONDA_ONLY_OK - KNOWN_DRIFT_CONDA_ONLY)
    unexpected_uv_only = sorted(uv_only - UV_ONLY_OK - KNOWN_DRIFT_UV_ONLY)
    unexpected_mismatch = sorted(mismatches - KNOWN_VERSION_MISMATCH)

    # Note allowlist entries that no longer apply, so the list does not rot.
    stale_allowlist = sorted(
        (KNOWN_DRIFT_CONDA_ONLY - conda_only)
        | (KNOWN_DRIFT_UV_ONLY - uv_only)
        | (KNOWN_VERSION_MISMATCH - mismatches)
    )

    has_drift = bool(unexpected_conda_only or unexpected_uv_only or unexpected_mismatch)

    if has_drift:
        print("[check_env_sync] Unexpected drift between environment.yml and pyproject.toml:")
        for name in unexpected_conda_only:
            print(f"  - only in environment.yml: {name} ({env_deps[name] or 'no pin'})")
        for name in unexpected_uv_only:
            print(f"  - only in pyproject.toml:  {name} ({uv_deps[name] or 'no pin'})")
        for name in unexpected_mismatch:
            print(
                f"  - version mismatch: {name} "
                f"(environment.yml={env_deps[name]} vs pyproject.toml={uv_deps[name]})"
            )
        print(
            "  Update both files, or add an intentional exception to the allowlist "
            "in CEPM/check_env_sync.py (and note it in CEPM/UV_MAMBA_GUIDE.md)."
        )
    else:
        print("[check_env_sync] environment.yml and pyproject.toml are aligned "
              "(all differences are on the known-accepted allowlist).")

    if stale_allowlist:
        print(
            "[check_env_sync] note: these allowlist entries no longer drift and can "
            f"be removed from CEPM/check_env_sync.py: {', '.join(stale_allowlist)}"
        )

    return 1 if has_drift else 0


if __name__ == "__main__":
    sys.exit(main())

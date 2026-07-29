from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_LOAD_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.io import write_csv
from utils.load import build_load


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description=(
            "Build a chart-ready annual load comparison CSV with large loads "
            "from inputs_case/loadsite_annual.csv separated from base load."
        ),
        default_output=DEFAULT_LOAD_OUTPUT,
    )

    config = load_config(
        args.config,
        output_override=args.output,
        output_kind="load",
    )

    load = build_load(config)

    write_csv(load, config.load_output_csv)

    print(
        f"Wrote {len(load):,} load rows to "
        f"{config.load_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_EMISSIONS_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.emissions import build_emissions
from utils.io import write_csv


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description=(
            "Build a line-chart-ready annual emissions comparison CSV "
            "from two existing ReEDS runs."
        ),
        default_output=DEFAULT_EMISSIONS_OUTPUT,
    )

    config = load_config(
        args.config,
        output_override=args.output,
        output_kind="emissions",
    )

    emissions = build_emissions(config)

    write_csv(emissions, config.emissions_output_csv)

    print(
        f"Wrote {len(emissions):,} emissions rows to "
        f"{config.emissions_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

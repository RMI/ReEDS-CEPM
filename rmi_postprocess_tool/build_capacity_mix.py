from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_CAPACITY_MIX_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.capacity_mix import build_installed_capacity_mix
from utils.io import write_csv


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description=(
            "Build a stacked-bar-ready installed capacity mix CSV "
            "from two existing ReEDS runs."
        ),
        default_output=DEFAULT_CAPACITY_MIX_OUTPUT,
    )

    config = load_config(args.config, output_override=args.output)
    capacity_mix = build_installed_capacity_mix(config)

    write_csv(capacity_mix, config.capacity_mix_output_csv)

    print(
        f"Wrote {len(capacity_mix):,} capacity mix rows to "
        f"{config.capacity_mix_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

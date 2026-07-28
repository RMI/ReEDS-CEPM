from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_CAPACITY_CHANGES_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.capacity_changes import build_capacity_changes
from utils.io import write_csv


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description=(
            "Build a waterfall-ready installed capacity changes CSV "
            "from two existing ReEDS runs."
        ),
        default_output=DEFAULT_CAPACITY_CHANGES_OUTPUT,
    )

    config = load_config(
        args.config,
        output_override=args.output,
        output_kind="capacity_changes",
    )

    capacity_changes = build_capacity_changes(config)

    write_csv(capacity_changes, config.capacity_changes_output_csv)

    print(
        f"Wrote {len(capacity_changes):,} capacity change rows to "
        f"{config.capacity_changes_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

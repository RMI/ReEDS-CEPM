from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_COST_COMPARISON_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.cost_comparison import build_cost_comparison
from utils.io import write_csv


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description=(
            "Build a stacked-bar-ready portfolio cost comparison CSV "
            "from two existing ReEDS runs."
        ),
        default_output=DEFAULT_COST_COMPARISON_OUTPUT,
    )

    config = load_config(
        args.config,
        output_override=args.output,
        output_kind="cost_comparison",
    )

    cost_comparison = build_cost_comparison(config)

    write_csv(cost_comparison, config.cost_comparison_output_csv)

    print(
        f"Wrote {len(cost_comparison):,} cost comparison rows to "
        f"{config.cost_comparison_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

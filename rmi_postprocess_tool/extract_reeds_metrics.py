from __future__ import annotations

import sys
from typing import Iterable

from utils.config import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_PRIMARY_METRICS_OUTPUT,
    load_config,
    parse_common_args,
)
from utils.io import write_csv
from utils.metrics import build_primary_metrics_comparison


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_common_args(
        argv,
        description="Extract and compare primary metrics from two existing ReEDS runs.",
        default_output=DEFAULT_PRIMARY_METRICS_OUTPUT,
    )

    config = load_config(args.config, output_override=args.output)
    comparison = build_primary_metrics_comparison(config)

    write_csv(comparison, config.primary_metrics_output_csv)

    print(
        f"Wrote {len(comparison):,} primary metric comparison rows to "
        f"{config.primary_metrics_output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ReEDS primary metrics extractor

Standalone Python postprocessor for comparing selected outputs from two existing ReEDS runs without rerunning ReEDS.

## Requirements

- Python 3.11+
- pandas

```

## Run

```bash
uv run extract_reeds_metrics.py --config config.example.toml
```

The script reads the two run folders configured in `config.toml`, looks under each run's `outputs/` folder, extracts configured metrics, and writes a comparison CSV.
Default for config file is `config.toml`, only differently named config files must be specified with --config

The output CSV has three data columns:

1. values from the first run
2. values from the second run
3. percent difference, calculated as `(run2 - run1) / abs(run1) * 100`

The metric label is written as the CSV row index named `metric`.

## Config notes

Each `[[metrics]]` block declares one output file and how to aggregate it.

Important fields:

- `file`: CSV under `<run>/outputs/`
- `columns`: full column order for headerless ReEDS CSVs; omit for headered CSVs
- `value_column`: numeric value column
- `filters`: optional key-value filters, such as `t = ["2026", "2032"]`
- `group_by`: dimensions to preserve in the output
- `aggregation`: `sum`, `mean`, `min`, `max`, or `first`
- `scale`: unit conversion; examples include fraction to percent (`100`) and Quads to MMBtu (`1000000000`)
- `missing_ok`: when true, a missing file is skipped instead of failing

## Initial metrics included

- Planning reserve margin: `prm.csv`, fraction to percent
- Transmission utilization: `tran_util_ann_rep.csv` and `tran_util_ann_stress.csv`, fraction to percent
- Curtailment: `curt_ann.csv` and `curt_tech.csv`, MWh
- Natural gas consumption: `repgasquant_nat.csv` and `repgasquant_irt.csv`, Quads to MMBtu

Adjust column orders if your ReEDS output files include different dimensions or headers.

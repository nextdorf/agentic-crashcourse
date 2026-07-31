# TinyBI

TinyBI is a local CSV analytics dashboard. Upload a dataset and it automatically detects numeric, categorical, and date columns, then presents summary metrics, charts, a data preview, and plain-English observations.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Install and run

```bash
uv sync
make serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). You can also start the server directly:

```bash
uv run uvicorn main:app --reload
```

## CSV data

CSV files may contain any mix of date, category, and numeric columns. TinyBI auto-detects their roles and uses the first numeric column as its primary metric, the first likely date as its time axis, and the first category as its grouping dimension. Missing values are handled automatically. UTF-8, UTF-8 with BOM, Windows-1252, and Latin-1 encodings are supported.

For the best result, include headers and at least one numeric column. The included `sample_data.csv` can be loaded from the homepage.

## API options

`POST /analyze` accepts a multipart field named `file`. Optional query parameters include:

- `query`: a pandas query expression, such as `Sales > 100`
- `x` and `y`: chart columns
- `aggregation`: `sum`, `mean`, `count`, `min`, or `max`
- `sort`: `index`, `value_asc`, or `value_desc`
- `limit`: number of chart groups, from 1 to 100
- `chart_type`: `auto`, `bar`, `line`, `pie`, or `doughnut`

`POST /config` accepts any subset of `metrics`, `charts`, `insights`, and `preview` as booleans to control dashboard visibility.

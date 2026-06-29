# TinyBI

TinyBI is a small local FastAPI dashboard for exploring CSV files. Upload a CSV and it automatically detects likely date, numeric, and categorical columns to show summary metrics, charts, a preview table, and short plain-English insights.

## Install

This project uses `uv` for dependency management.

```bash
uv sync
```

## Run

```bash
make serve
```

Equivalent direct command:

```bash
uv run uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## CSV Format

TinyBI works best with a CSV that has at least one numeric column and optional date and category columns. Example columns are `date`, `category`, `revenue`, `users`, and `region`.

The app auto-detects columns, so exact names are not required. Missing values are ignored in charts and metric calculations where possible.

## API

- `GET /` serves the dashboard.
- `POST /analyze` accepts a multipart upload with field name `file`.
- `GET /sample-data` analyzes the included `sample_data.csv`.
- `POST /config` toggles dashboard sections such as metrics, charts, insights, and preview.

`/analyze` accepts optional form fields or query parameters such as `filter_query`, `chart_type`, `x_column`, `y_column`, `aggregation`, `sort_by`, and `limit`.

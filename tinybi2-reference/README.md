# TinyBI 2

TinyBI 2 is a local FastAPI CSV dashboard shared by a browser and a purpose-built MCP server. It detects likely dates, measures, dimensions, and identifiers; applies typed pandas filters; and publishes bounded metrics, Chart.js data, deterministic insights, and a 10-row normalized preview.

This refinement adds explicit validation, encoding and row-count metadata, a configurable input limit, chronological time charts, safer insights, column dropdowns, sorting controls, accessible request feedback, stale-request cancellation, and revision polling. Browser and MCP actions update the same in-memory dashboard.

## Install And Run

```bash
uv sync
make serve
```

The direct equivalent is:

```bash
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Run one Uvicorn worker only: the shared workspace is process-local. Server restart and `--reload` clear the active dataset and revision.

Run tests with:

```bash
uv run pytest
```

## Sample And Filters

The included `sample_data.csv` has 9,994 Superstore rows and these columns:

`Row ID`, `Order ID`, `Order Date`, `Ship Date`, `Ship Mode`, `Customer ID`, `Customer Name`, `Segment`, `Country`, `City`, `State`, `Postal Code`, `Region`, `Product ID`, `Category`, `Sub-Category`, `Product Name`, `Sales`, `Quantity`, `Discount`, and `Profit`.

Filters are case-sensitive `pandas.DataFrame.query` expressions. Numeric and date-like text is coerced before filtering. Use exact column names and backticks for spaces or punctuation:

```text
Sales > 100 and Region == 'West'
`Order Date` >= '2016-01-01'
`Sub-Category` == 'Chairs'
```

The default input limit is 10 MB. Set `TINYBI_MAX_INPUT_BYTES` before startup to change it. MCP path input is restricted to `.csv` files whose resolved path, including symlinks, remains inside this project directory. Use inline input for data elsewhere.

## HTTP API

- `GET /` serves the dashboard.
- `POST /analyze` accepts multipart CSV field `file` plus optional `filter_query`, `chart_type`, `x_column`, `y_column`, `aggregation`, `sort_by`, and `limit` fields.
- `GET /sample-data` analyzes and activates the sample with the same optional controls.
- `GET /sample-data?download=true` downloads the sample CSV.
- `POST /config` validates and shares metrics, charts, insights, and preview visibility.
- `GET /state` returns the current bounded snapshot and synchronization revision.
- `GET /state?after_revision=N` returns HTTP 204 when revision `N` is current, otherwise the newer snapshot.

Responses expose safe source labels, never uploaded bytes, complete datasets, inline CSV text, or absolute paths. Each successful state-changing action increments the revision exactly once. A failed parse, filter, or control validation leaves the prior state unchanged.

## MCP

The Streamable HTTP MCP endpoint is `http://127.0.0.1:8000/mcp` and exposes exactly three tools:

- `inspect_dataset`: discover exact columns, heuristic roles, missingness, ranges, valid choices, and filter examples without changing state. Example intent: "Inspect the open CSV and tell me valid measures."
- `analyze_dataset`: publish a broad dashboard with selected metrics, charts, insights, or preview. Example intent: "Analyze the open data for West-region orders."
- `create_chart`: publish one explicit bounded X/Y aggregation. Example intent: "Chart total Sales by Order Date chronologically."

Omitting `dataset` means "use the active shared dataset", falling back to the sample only when the workspace is empty. The schema-enforced alternatives are:

```json
{"source": "sample"}
{"source": "path", "path": "data/orders.csv"}
{"source": "inline", "inline_csv": "Region,Revenue\nWest,100\nEast,80\n"}
```

An explicit dataset on `analyze_dataset` or `create_chart` becomes active only after successful validation. An explicit dataset on `inspect_dataset` remains read-only.

To use MCP Inspector, start TinyBI and connect its Streamable HTTP transport to `http://127.0.0.1:8000/mcp`. Any MCP client supporting Streamable HTTP can use the same URL. The endpoint is an MCP transport, not a normal JSON `GET` API.

## Local Limitations

- Every browser and MCP client shares one workspace; there are no workspace IDs or accounts.
- State exists only in memory and resets on restart or reload.
- Run exactly one Uvicorn worker; multiple workers would have separate state.
- Charts load pinned Chart.js 4.5.0 from jsDelivr and require network access unless that asset is vendored locally.
- Role detection is heuristic. Verify identifiers and business meaning against the source domain.

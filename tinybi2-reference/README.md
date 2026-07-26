# TinyBI 2

TinyBI 2 is a local FastAPI CSV dashboard shared by a browser and a purpose-built MCP server. It detects likely dates, measures, dimensions, and identifiers; applies typed pandas filters; and publishes bounded metrics, Chart.js data, deterministic insights, and a normalized preview.

The browser and MCP operate on one versioned in-memory workspace. Automatic analysis produces disposable overview charts. MCP clients can also maintain an ordered collection of explicit bar, line, scatter, and heatmap charts.

## Install And Run

```bash
uv sync
make serve
```

The direct equivalent is:

```bash
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Use one Uvicorn worker: the workspace is process-local. Restart and `--reload` create a new workspace incarnation and clear all state.

Run verification with:

```bash
uv run pytest
node --test static/app-core.test.js
node --check static/app.js
```

## Datasets And Filters

The default input limit is 10 MB. Set `TINYBI_MAX_INPUT_BYTES` before startup to change it. Numeric infinities are treated as missing values, previews contain at most 10 rows, and chart results are bounded.

Filters are case-sensitive `pandas.DataFrame.query` expressions. Use exact column names and backticks around names containing spaces:

```text
Sales > 100 and Region == 'West'
`Order Date` >= '2016-01-01'
`Sub-Category` == 'Chairs'
```

MCP path input is restricted to `.csv` files whose resolved path, including symlinks, remains inside this project directory. Use inline input for data elsewhere.

## Workspace Versioning

Every state-changing call requires:

```json
{
  "expected_incarnation": "process-lifetime token",
  "expected_revision": 4
}
```

Read the current values with `GET /state`, `inspect_dataset`, or `list_charts`. A stale mutation returns HTTP 409 or an MCP tool error without changing state. Refresh the workspace and retry with the returned version.

The revision increments once for each successful changed transaction. No-op visibility updates and no-op chart reordering do not increment it. Browser analysis requests also carry a client ID and increasing request sequence so an aborted or superseded request cannot commit later.

## HTTP API

- `GET /` serves the dashboard and initial workspace version.
- `POST /analyze` accepts multipart field `file`, workspace/request version fields, and optional analysis controls. It explicitly replaces the dataset.
- `POST /analyze-active` applies JSON controls to the committed dataset without reuploading or selecting the sample.
- `POST /sample-data` explicitly activates and analyzes the included sample.
- `GET /sample-data` downloads the sample CSV.
- `POST /config` applies a versioned visibility update.
- `GET /state` returns the current bounded snapshot.
- `GET /state?incarnation=TOKEN&after_revision=N` returns HTTP 204 only when that exact workspace version remains current.

Browser analysis mutations additionally require `request_client` and positive `request_sequence` fields. Successful explicit dataset replacement clears managed charts but does not reset their ID counter.

Responses expose safe source labels, never uploaded bytes, complete datasets, inline CSV text, DataFrames, or absolute paths.

## MCP Tools

The Streamable HTTP MCP endpoint is `http://127.0.0.1:8000/mcp` and exposes seven tools:

- `inspect_dataset`: inspect roles, missingness, ranges, valid choices, filter examples, and current version without changing state.
- `analyze_dataset`: publish the broad automatic dashboard. Omit `dataset` to preserve managed charts; provide one to replace the dataset and clear them atomically.
- `list_charts`: list managed chart IDs, order, titles, and definitions, optionally with bounded rendered data.
- `create_charts`: atomically add one to ten managed chart definitions.
- `update_charts`: atomically replace selected definitions while preserving IDs.
- `delete_charts`: atomically remove selected IDs.
- `reorder_charts`: atomically set the complete managed-chart order.

Dataset alternatives are schema-enforced:

```json
{"source": "sample"}
{"source": "path", "path": "data/orders.csv"}
{"source": "inline", "inline_csv": "Region,Revenue\nWest,100\nEast,80\n"}
```

An explicit dataset on `analyze_dataset` or `create_charts` becomes active only when the complete operation validates. `inspect_dataset` never changes active state.

## Managed Charts

Managed chart IDs are monotonically increasing positive integers. Updating and reordering preserve IDs; deleted IDs are never reused during the process lifetime. Automatic charts render first, followed by managed charts in registry order.

Grouped bar or line definition:

```json
{
  "type": "bar",
  "x_column": "Region",
  "y_column": "Revenue",
  "aggregation": "sum",
  "sort_by": "value_desc",
  "limit": 20
}
```

Scatter definition; both axes must be detected measures:

```json
{
  "type": "scatter",
  "x_column": "Discount",
  "y_column": "Profit",
  "limit": 50
}
```

Heatmap definition; both axes must be grouping columns and the value must be a measure:

```json
{
  "type": "heatmap",
  "x_column": "Region",
  "y_column": "Category",
  "value_column": "Sales",
  "aggregation": "sum",
  "x_limit": 10,
  "y_limit": 10
}
```

All chart definitions support an optional `title` and `filter_query`. Batch validation is atomic: one invalid ID, column, definition, filter, or order rejects the entire call without consuming IDs.

## Local Limitations

- Every browser and MCP client shares one workspace; there are no accounts or workspace IDs.
- State and chart IDs reset on process restart.
- Run exactly one Uvicorn worker; multiple workers would have separate state.
- Charts load pinned Chart.js 4.5.0 and `chartjs-chart-matrix` 2.0.1 from jsDelivr and require network access unless vendored locally.
- Role detection is heuristic. Verify identifiers and business meaning against the source domain.

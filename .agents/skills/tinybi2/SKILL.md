---
name: tinybi2
description: Use when the user asks to analyze CSV data, build a TinyBI2 dashboard, or create, update, delete, list, or reorder charts through the my_mcp TinyBI2 server.
---

# TinyBI2 MCP

Use the `my_mcp` tools to turn the user's request into a CSV analysis or a set of managed charts. Work from the user's stated goal rather than exposing the MCP mechanics unless they are relevant.

## Core Rules

- Inspect before mutating. Obtain the current `workspace.incarnation`, `workspace.revision`, detected column roles, and valid options with `inspect_dataset`.
- Pass the latest `expected_incarnation` and `expected_revision` to every mutation.
- Treat the workspace as shared with the browser and other agents. Do not reuse a version from before another successful mutation.
- If a mutation reports a stale version, inspect or list again, reconsider the request against the new state, and retry only if it remains safe.
- Omit `dataset` to work with the active shared dataset. Supplying an explicit dataset to `analyze_dataset` or `create_charts` replaces the active dataset and clears all managed charts.
- `inspect_dataset` never activates or replaces a dataset, even when given an explicit input.
- Do not replace a dataset, clear charts, or delete charts unless the user's request clearly authorizes that effect. Ask one concise question when intent is ambiguous.
- Use exact, case-sensitive column names returned by inspection.
- Keep results bounded and useful. Prefer a small set of charts that directly answer the request.

## Choose A Workflow

Use `analyze_dataset` for a broad, disposable dashboard with metrics, automatic charts, insights, or a preview.

Use managed chart tools when the user asks for specific visualizations, persistent charts, chart edits, deletion, or ordering:

- `list_charts` reads IDs, definitions, and order. Use `include_data: true` only when rendered values are needed.
- `create_charts` atomically adds one to ten charts.
- `update_charts` replaces complete definitions while preserving IDs and order.
- `delete_charts` atomically removes selected IDs. Deleted IDs are not reused.
- `reorder_charts` requires every current managed chart ID exactly once.

## Dataset Inputs

Translate an explicitly requested source into one of these forms:

```json
{"source":"sample"}
```

```json
{"source":"path","path":"data/orders.csv"}
```

```json
{"source":"inline","inline_csv":"Region,Revenue\nWest,100\nEast,80\n"}
```

Path inputs must be CSV files inside the TinyBI2 project directory. For data outside it, use complete inline CSV content when practical. Omit the dataset argument when the user means the currently active dataset.

When replacing the active dataset:

1. Call `inspect_dataset` with the explicit dataset.
2. Validate that its detected roles support the requested analysis or charts.
3. Use the same explicit dataset in the intended `analyze_dataset` or `create_charts` mutation.

## Analysis Workflow

1. Inspect the intended dataset.
2. Derive a valid filter and requested sections from the user's goal.
3. Call `analyze_dataset` with the current workspace version.
4. Request only needed sections when the request is narrow; otherwise return the broad dashboard.
5. Summarize the important metrics, trends, filters, and row counts rather than dumping the full payload.

Filters are case-sensitive pandas `DataFrame.query` expressions. Wrap columns containing spaces in backticks:

```text
Sales > 100 and Region == 'West'
`Order Date` >= '2016-01-01'
`Sub-Category` == 'Chairs'
```

An empty filter string clears the current filter.

## Chart Selection

Choose chart definitions only from roles returned by `inspect_dataset`:

- Bar: compare aggregated measures across categories.
- Line: show ordered or date-based trends.
- Scatter: examine relationships between two detected numeric measures.
- Heatmap: compare one measure across two grouping dimensions.

Grouped bar or line chart:

```json
{
  "type": "bar",
  "x_column": "Region",
  "y_column": "Sales",
  "aggregation": "sum",
  "sort_by": "value_desc",
  "limit": 20
}
```

Scatter chart:

```json
{
  "type": "scatter",
  "x_column": "Discount",
  "y_column": "Profit",
  "limit": 50
}
```

Heatmap:

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

Supported aggregations are `sum`, `mean`, `median`, `min`, `max`, and `count`. Supported sort modes are `label_asc`, `label_desc`, `value_asc`, and `value_desc`. Use inspection output for current limits and valid columns instead of assuming them.

## Chart Mutation Workflow

1. Inspect the dataset and call `list_charts` when existing chart IDs or order matter.
2. Build complete, valid definitions from detected roles.
3. Submit related changes as one atomic batch where possible.
4. Use the workspace version from the most recent successful call.
5. After each mutation, use the returned workspace version for the next mutation.
6. Report affected chart IDs, titles, ordering, and any dataset replacement.

For updates, provide each chart's complete replacement definition, not a partial patch. For reorder operations, include every current ID exactly once. Never invent IDs.

## Response Style

- State what was analyzed or changed.
- Mention active filters and dataset replacement when applicable.
- For managed charts, report chart IDs and concise titles.
- Highlight useful findings from returned data, but do not claim conclusions unsupported by the tool output.
- Surface validation failures plainly and suggest the nearest valid alternative.

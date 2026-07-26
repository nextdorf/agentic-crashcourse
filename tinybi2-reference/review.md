# TinyBI 2 Codebase Review

Scope reviewed: `analytics.py`, `mcp_server.py`, `main.py`, `static/app.js`, `templates/index.html`, `README.md`, and the tests under `tests/`.

This review focuses on what TinyBI 2 adds: the MCP server, the shared browser/MCP workspace, revision polling, stricter machine-readable contracts, improved validation, and focused chart creation. The inherited dashboard, CSV parsing, basic metrics, Chart.js rendering, and general UI are covered in the [TinyBI 1 review](../tinybi-reference/review.md) and are not repeated here unless they interact with a new TinyBI 2 feature.

## Executive Summary

TinyBI 2 is a substantial refinement rather than a thin MCP wrapper. The analysis code has moved out of `main.py`, large response sections are bounded, MCP schemas are unusually descriptive, validation failures are mostly atomic, and browser and MCP clients genuinely share one in-memory dashboard. The three-tool MCP surface is compact enough for an LLM to understand, and the tests cover more than a typical generated proof of concept.

The main weakness is that the shared-workspace contract is not yet reliable under realistic cross-client interaction. The backend serializes writes, but it does not protect them from stale clients. More importantly, the browser cannot rerun the dataset selected by MCP: changing a browser control after an MCP action can silently replace the active source with the sample or an older browser upload. Revision polling also has a restart edge case, and aborting a browser request does not prevent that request from committing server-side later.

The current `create_chart` behavior is also too destructive for exploratory work. It replaces the entire chart list with one chart whose ID is always `custom`. The next focused refinement should turn explicitly created charts into a managed collection with monotonic IDs, atomic subset operations, reordering, and optimistic revision checks. Scatter plots and heatmaps should use type-specific, dataset-agnostic specifications rather than stretching the current grouped label/value schema.

## What TinyBI 2 Improves Well

### The MCP is purpose-built rather than an API dump

`mcp_server.py` does a good job of presenting analysis capabilities in terms an LLM can use:

- `inspect_dataset` is explicitly read-only and returns detected roles, valid choices, missingness, date ranges, and executable filter examples (`mcp_server.py:226-244`).
- `analyze_dataset` is positioned as the broad automatic workflow, while `create_chart` is the focused X/Y aggregation path (`mcp_server.py:246-306`).
- Tool descriptions explain active-dataset behavior, case-sensitive filtering, spaced column names, aggregation semantics, sorting, and limits.
- MCP annotations correctly distinguish read-only inspection from state-changing analysis (`mcp_server.py:235`, `mcp_server.py:254`, `mcp_server.py:286`).
- `mask_error_details=True` prevents accidental traceback and filesystem disclosure (`mcp_server.py:213-224`).

This matters because MCP tool names, descriptions, and schemas are prompt context. TinyBI 2 gives the model enough information to choose a tool and construct a valid call without loading a separate manual.

### The input schemas are strict and discoverable

The discriminated `sample`, `path`, and `inline` dataset union is a strong contract (`mcp_server.py:29-63`). `extra='forbid'` catches misspelled and incompatible fields instead of silently ignoring them. The path variant restricts reads to `.csv` files inside the TinyBI project after resolution, checks existence and size, and returns only a safe basename (`mcp_server.py:193-210`, `analytics.py:556-561`).

Dataset inspection also exposes valid X and Y columns and bounded option sets before the model attempts a chart (`analytics.py:343-347`). This is much better than accepting arbitrary strings and returning pandas errors after the fact.

### The shared store gives browser and MCP one source of truth

`main.py` creates one `DashboardStore` and injects it into both FastAPI and FastMCP (`main.py:18-24`). That avoids the easy mistake of giving the web app and MCP server separate process-local state.

The store centralizes:

- active CSV bytes and a safe source label;
- detected dataset metadata;
- dashboard controls and visibility;
- the latest constrained dashboard snapshot;
- a monotonic workspace revision;
- the interface that last committed the state.

Parsing, filtering, chart generation, and output cleanup complete before `_commit()` changes the active workspace (`analytics.py:85-125`, `analytics.py:148-156`). The tested parsing and control-validation failures therefore leave the previous revision and dataset intact (`tests/test_analytics.py:64-74`, `tests/test_mcp.py:119-140`). Response-model validation and transport serialization happen after `_commit()` (`mcp_server.py:270-306`), so atomicity does not yet extend to invalid output values such as infinity.

### State exposure is deliberately constrained

The state API and MCP responses return metadata, up to 10 preview rows, and charts with at most 50 groups. They do not return uploaded bytes, complete datasets, inline CSV text, DataFrames, or absolute server paths (`analytics.py:514-520`, `mcp_server.py:87-190`). The HTTP test checks the most important leakage cases (`tests/test_app.py:38-49`). Column-dependent structures such as `missing_values`, detected-role lists, and aggregate table width are not independently capped, so the response is bounded by input bytes and row/group limits rather than by one strict output-size ceiling.

That is the correct default for an MCP: tool responses go directly into model context, so returning entire datasets would be expensive and potentially unsafe.

### Validation and response contracts are significantly stronger

TinyBI 2 separates measures, dimensions, dates, and identifiers; coerces likely numeric and date columns before filtering; rejects invalid controls; rejects filters that remove every row; and returns chosen encoding plus before/after row counts (`analytics.py:168-228`, `analytics.py:254-347`).

The Pydantic MCP output models make metrics and chart structures machine-readable instead of leaving every response as an undocumented dictionary (`mcp_server.py:127-190`). The test suite checks strict output schemas and generated input constraints, not only successful Python calls (`tests/test_mcp.py:25-50`).

### The synchronization UI has useful foundations

The browser polls `/state` with its current revision, ignores older dashboard responses, applies remote controls without retriggering analysis, and shows revision, source, and last updater (`static/app.js:88-143`). Chart instances are destroyed before rerendering, and server-provided values are escaped before entering HTML (`static/app.js:165-196`).

The request ID/`AbortController` logic prevents an older browser response from rendering over a newer browser response (`static/app.js:52-70`). This is an improvement over TinyBI 1, even though it does not cancel a server-side commit.

### The tests are compact but high-value

The 12 tests cover:

- non-UTF-8 input, empty input, and input-size limits;
- identifier exclusion and typed filtering;
- chronological date charts and JSON-safe previews;
- failed-store atomicity;
- route revisions, bounded state, and source redaction;
- generated MCP schemas and all three tools;
- browser-to-MCP and MCP-to-browser state sharing;
- repairable MCP errors without tracebacks or leaked paths.

`uv run pytest` passes all 12 tests. `node --check static/app.js` also passes.

## Findings

### High: browser controls can replace an MCP-selected dataset

Polling updates the rendered dashboard and controls, but it does not update `state.currentFile` to represent the remotely active source (`static/app.js:88-103`). When the user changes a chart control, `rerunCurrentAnalysis()` either reuploads the browser's previous `File` object or calls `/sample-data` (`static/app.js:23-25`, `static/app.js:45-50`).

The HTTP API has no route that means "reanalyze the currently active store dataset with these controls." `/sample-data` always activates the sample, and `/analyze` always requires an upload (`main.py:67-83`).

A normal failure sequence is therefore:

1. A browser previously loaded the sample or uploaded file A.
2. MCP activates file B and publishes a chart.
3. Polling correctly shows file B in the browser.
4. The user changes aggregation or sort order.
5. The browser silently activates the sample or reuploads file A.

This breaks the central promise that both interfaces operate on one shared dataset. Add an HTTP operation that applies controls to the active store dataset, and use it whenever the rendered source came from MCP or another browser.

### High: writes are serialized but still last-write-wins

`DashboardStore` uses one `RLock`, which prevents simultaneous mutation but does not prevent a stale request from committing after a newer one (`analytics.py:51-62`, `analytics.py:85-125`). Neither HTTP nor MCP mutations accept an expected revision.

`AbortController.abort()` only stops the original browser from consuming the response (`static/app.js:52-70`). Once FastAPI has accepted the request, synchronous pandas work can continue and `_commit()` can publish it. A slow, supposedly cancelled analysis can therefore become the newest workspace revision after a faster MCP or browser action.

Browser and managed-chart mutations should require `expected_revision`; allowing it to be omitted preserves last-write-wins behavior. The store should validate it under the same lock immediately before committing and return a repairable conflict when it is stale.

### High: non-finite values can escape the machine-readable contract

Numeric coercion accepts `inf` and `-inf` as measures (`analytics.py:219-223`). Automatic analysis can then fail inside histogram generation at `pd.cut()` (`analytics.py:434-443`), producing an uncaught server error rather than `AnalysisError`. Focused aggregation can instead return infinity because `clean_json()` converts missing values but not non-finite numbers (`analytics.py:538-553`). The Pydantic numeric unions do not require finite numbers, so the store can commit the result and increment its revision before strict JSON transport serialization fails.

Normalize non-finite values to `None` or reject them with a clear analysis error before metrics, charts, insights, and commits. Add HTTP and MCP tests for raw infinity and aggregate overflow, including assertions that a failed response does not change workspace state.

### Medium: revision polling cannot recover from a server restart

`snapshot()` returns no update whenever `after_revision >= current_revision` (`analytics.py:68-74`). Equality correctly means "unchanged," but a greater client revision usually means the process restarted and its in-memory counter returned to zero.

A browser at revision 20 will receive HTTP 204 after restart until the new process reaches revision 21. The page can remain stuck on stale data indefinitely. Returning the lower revision is not sufficient because the frontend also rejects lower revisions (`static/app.js:94`, `static/app.js:117-130`). Add a workspace-incarnation token that changes on process start, include it in polling and optimistic-concurrency checks, and reset client state when the incarnation changes. This also prevents revision-number ABA across restarts.

### Medium: resolved controls become sticky workspace inputs

`analyze()` commits `result['effective_config']` (`analytics.py:97-99`). `effective_controls()` resolves `chart_type='auto'` to `line` or `bar` and chooses default columns and sorting (`analytics.py:379-393`). Those resolved values then become the starting point for future analyses through `_merged_controls()` (`analytics.py:138-146`).

This mixes two different concepts:

- requested controls, such as `chart_type='auto'`;
- resolved controls, such as `chart_type='line'` for the current date column.

The history of the shared workspace can therefore affect a later "automatic" analysis. After a focused chart, `analyze_dataset` exposes only `filter_query`, inherits the focused X/Y, aggregation, chart type, sort, and limit, and can insert the old custom chart into its supposedly broad automatic result (`mcp_server.py:256-274`, `analytics.py:444-446`). There is no MCP input that clears those inherited chart controls.

The focused tool has the same problem in reverse: its description says an omitted `sort_by` chooses the chart-appropriate default (`mcp_server.py:295`), but `_merged_controls()` ignores `None` and can inherit a previous workspace sort (`analytics.py:138-146`). Keep requested automatic controls separate from focused chart definitions, return resolved controls only as output metadata, and stop using unrelated workspace history as an undocumented default.

### Medium: synchronous pandas work blocks the web event loop and state polling

The async `/sample-data` and `/analyze` handlers directly run synchronous parsing and pandas analysis (`main.py:67-83`, `main.py:97-100`). Store methods hold the global lock throughout that work (`analytics.py:76-125`). A large allowed input can block `/state`, `/config`, and other requests precisely when synchronization feedback matters most.

Focused chart creation also parses the same content repeatedly: once in `create_chart_bytes`, again in `analyze_bytes`, and again in `_commit()` (`analytics.py:109-125`, `analytics.py:148-150`). `_dataset` is stored but not reused.

Run CPU-bound analysis outside the event loop, shorten the locked section, and reuse a validated parsed dataset within one transaction. The single-process design can remain simple without doing all computation under the workspace lock.

### Medium: a stale config response can roll back local visibility

`updateConfig()` assigns `state.config = result.config` before `applyWorkspace()` checks the response revision (`static/app.js:73-85`, `static/app.js:128-133`). Polling is allowed while a config request is in flight. If a newer workspace arrives first, the older config response can still overwrite local visibility even though its workspace revision is rejected. Later polls then receive 204 and may never repair the checkboxes.

Apply the same revision guard to the entire response, not only the workspace metadata. Config mutations should also require `expected_revision`.

### Low: snapshots expose mutable nested state

`snapshot()` returns only a shallow copy of `_snapshot` (`analytics.py:68-74`). Nested metrics, charts, preview rows, and config remain shared references. A caller can mutate returned state without taking the store lock or incrementing the revision.

Return a deep copy or an already serialized immutable snapshot. This is mostly contained by FastAPI serialization today, but `DashboardStore` itself does not enforce the boundary its API implies.

### Low: revision semantics include no-op updates

`update_visibility()` increments the revision even when the request is empty or all values already match (`analytics.py:127-136`). This creates unnecessary polling and weakens the useful invariant that a new revision represents changed state.

Do not commit or increment when normalized state is unchanged.

### Low: some MCP errors and schemas could be more repairable

Path reads can still raise `OSError` or `PermissionError`, but MCP tools convert only `AnalysisError` to `ToolError` (`mcp_server.py:193-210`, `mcp_server.py:240-306`). The details are safely masked, but the client receives a generic failure instead of an actionable unreadable-file error.

The output `Controls` model also uses unrestricted strings for aggregation, chart type, and sort mode even though the input schema has literals (`mcp_server.py:77-84`). `sections` is accepted as a set and converted back to a list, so `returned_sections` order is not stable (`mcp_server.py:256-274`). These are not major defects, but stronger output literals and deterministic lists would improve generated clients.

## Current Chart-Management Limitation

`create_chart` is useful for one focused result, but `DashboardStore.create_chart()` explicitly replaces the complete chart list with `[focused['chart']]` (`analytics.py:109-125`). Every focused chart has the ID `custom` (`analytics.py:450-475`). There is no way to list published chart definitions, add several charts, update one, delete a subset, or control their order.

This forces an exploratory agent to destroy its previous visualization every time it tests another relationship. It also makes the shared browser less useful as a durable output surface for MCP analysis.

Automatic charts and explicitly curated charts should be separate concepts:

- `analyze_dataset` may refresh its disposable automatic charts.
- Explicit charts should survive automatic analysis of the same active dataset.
- Changing the active dataset should clear explicit charts because their columns and filters may no longer be valid.
- Clearing charts must not reset the chart-ID counter.

## Missing Verification

The existing tests are a strong start, but the new shared-workspace behavior needs adversarial tests rather than only sequential happy paths.

Highest-value additions:

- Change browser controls after MCP activates a different dataset and verify the active source is preserved.
- Delay and reorder browser analysis, config, polling, and MCP writes; verify stale commits are rejected.
- Poll across a changed workspace incarnation and verify restart recovery and revision reset.
- Verify requested `auto` controls do not become sticky resolved controls across analyses.
- Exercise `inf`, `-inf`, and overflow through direct analytics, HTTP, and MCP.
- Verify returned snapshots cannot mutate store state.
- Exercise the mounted Streamable HTTP `/mcp` transport; current MCP tests use the in-process `Client(mcp)`.
- Verify path traversal, symlink escape, unreadable files, and path-read races return repairable errors without changing state.
- Add browser JavaScript tests for revision guards, source reconciliation, overlapping requests, and multi-chart rendering.
- Construct a fresh store/app fixture per test instead of mutating the imported singleton across test cases.

## Focused Refinement Plan

### 1. Fix the shared-workspace contract first

- Add a browser-facing operation to analyze the currently active dataset without reuploading or selecting the sample.
- Require `expected_revision` for browser and managed-chart mutations and reject stale writes atomically.
- Add a workspace-incarnation token and reset polling clients when it changes.
- Store requested controls separately from resolved output controls.
- Prevent superseded browser requests from committing, not merely from rendering.
- Move pandas work off the async event loop and minimize work under the store lock.

These changes are prerequisites for reliable chart management. Stable chart IDs do not help if stale requests can overwrite the whole workspace.

### 2. Add a managed explicit-chart collection

Add an ordered chart registry to `DashboardStore` with a session-level `_next_chart_id` counter:

- New charts receive monotonically increasing positive integer IDs.
- Updating or reordering a chart preserves its ID.
- Deleted IDs are never reused during the process lifetime.
- A successfully validated explicit dataset replacement clears managed charts but does not reset `_next_chart_id`, even when the new file has the same basename.
- Server restart resets both state and IDs, consistent with the documented in-memory lifecycle.
- Automatic charts remain separate and are rendered before managed charts.

Expose a small dataset-agnostic MCP surface:

- `list_charts` returns managed IDs, order, title, definition, and optionally bounded rendered data.
- `create_charts` atomically adds one or more definitions.
- `update_charts` atomically replaces definitions for selected IDs while retaining those IDs.
- `delete_charts` atomically removes selected IDs.
- `reorder_charts` accepts the complete desired managed-ID order and rejects missing, duplicate, or unknown IDs.

Every mutation should require `expected_revision`, validate all requested operations before changing state, and increment the workspace revision exactly once on success. Invalid IDs, invalid columns, or invalid chart definitions must leave charts, order, active dataset, counter, and revision unchanged. Track dataset identity with an internal generation or fingerprint rather than the safe display basename. Omitting `dataset` preserves managed charts; any successfully validated explicit replacement advances the dataset generation and clears them atomically.

### 3. Use type-specific chart specifications

Do not force scatter plots and heatmaps into the existing grouped `labels`/`values` structure. Use a strict discriminated union based on chart type.

Grouped bar and line charts:

```text
type, x_column, y_column, aggregation, filter_query, sort_by, limit
```

Scatter plots:

```text
type="scatter", x_column, y_column, filter_query, limit
```

Both scatter axes must be detected numeric measures. The result should contain bounded `{x, y}` points. Scatter does not need grouped aggregation semantics.

Heatmaps:

```text
type="heatmap", x_column, y_column, value_column,
aggregation, filter_query, x_limit, y_limit
```

The two axes are grouping columns and `value_column` is a detected numeric measure. The result should contain bounded `{x, y, value}` cells. Explicit per-axis and total-cell limits keep MCP responses and browser rendering predictable for any dataset.

Keep bar, line, scatter, and heatmap definitions dataset-agnostic: schemas should refer only to detected column roles and generic aggregation behavior, never to sample-specific field names or hierarchies.

### 4. Extend rendering without hiding dependencies

Chart.js already renders scatter plots. Heatmaps require a matrix renderer; `chartjs-chart-matrix` supports Chart.js 4 and accepts cells with X, Y, and value data. Load a pinned compatible version, document that it is another CDN dependency, and add type-specific rendering and tooltip logic in `static/app.js`.

The frontend should compose automatic charts with managed charts in registry order. Canvas DOM IDs should include a stable prefix and managed integer ID so automatic string IDs cannot collide.

### 5. Lock the behavior down with tests

Add tests for:

- creating several charts in one atomic call;
- updating a subset without changing IDs or untouched charts;
- deleting a subset and proving IDs are not reused;
- reordering and rejecting incomplete or duplicate orders;
- stale `expected_revision` conflicts;
- chart clearing on dataset replacement while the counter continues;
- preserving managed charts during automatic analysis of the same dataset;
- scatter role validation, null handling, and point bounds;
- heatmap role validation, aggregation, axis limits, and cell bounds;
- `/state` returning several charts in deterministic order;
- browser rendering of bar, line, scatter, and heatmap payloads.

Update the README and MCP tool-contract tests together. Tool descriptions should explain the managed/automatic distinction, ID lifetime, atomic batch behavior, and revision-conflict recovery.

## Overall Assessment

TinyBI 2 succeeds at its main architectural goal: it turns a local CSV dashboard into a compact MCP-enabled shared workspace without exposing raw datasets to the model. The MCP contracts, bounded responses, strict dataset inputs, atomic validation failures, and initial synchronization tests are all strong reference material.

The next work should not broaden the analytics engine indiscriminately. It should make the new shared-state promise dependable and make focused MCP visualizations composable. Fix active-source reruns and stale-write handling first; then implement the managed chart registry, subset operations, reordering, scatter plots, and heatmaps described above. That produces a more capable MCP while keeping the design small, dataset-agnostic, and understandable.

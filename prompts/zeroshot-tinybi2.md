Build TinyBI 2 as a refined version of the TinyBI FastAPI CSV dashboard and add a purpose-designed MCP interface.

Goal:
Create a polished local CSV analytics app that preserves TinyBI's existing browser and HTTP API behavior, fixes its most important usability and robustness problems, and lets an AI perform the meaningful dashboard workflow through well-designed MCP tools. The browser and MCP server must operate on one shared, stateful dashboard workspace so actions through either interface are visible in the other. Complete the migration from start to finish in one run.

Important behavior:

* At the beginning, ask the user for these setup choices in one short batch:
  * whether to copy an existing TinyBI project or recreate version 1 from `prompts/zeroshot-tinybi.md`
  * source directory, defaulting to `tinybi-reference` when copying
  * destination directory, defaulting to `tinybi2-reference`
  * app name, defaulting to `TinyBI 2`
* Limit follow-up questions strictly to that initial setup batch. Make reasonable assumptions afterward.
* Prefer an empty or not-yet-existing destination. Never overwrite a non-empty destination without explicit approval.
* In copy mode, copy the source project into the destination but exclude generated artifacts such as `.venv`, `__pycache__`, `.pytest_cache`, and compiled Python files.
* In recreate mode, read `prompts/zeroshot-tinybi.md`, create its version 1 app at the destination, and then apply all requirements in this prompt. Do not stop after recreating version 1.
* If the requested source is unavailable, fall back to recreate mode and state that choice in the final summary.
* Inspect the selected source enough to preserve its behavior, but do not spend the task producing another general code review. The required refinements are specified below.
* Prefer a small, coherent, working implementation over a broad rewrite. Do not add a database, authentication, a frontend framework, a task queue, or external backend services.

Technology and dependencies:

* Keep FastAPI, pandas, Jinja2, plain HTML/CSS/JavaScript, Chart.js, and `uv`.
* Add the `fastmcp` package with `uv add fastmcp`.
* Add a small pytest-based test setup with development dependencies managed through `uv add --dev`.
* Inherit the source TinyBI project's Python version requirement unchanged in `pyproject.toml`.
* Keep `make serve` and `uv run uvicorn main:app --reload` working.
* Keep the frontend build-free.

Preserve the existing application:

* Preserve `GET /` as the browser dashboard.
* Preserve `POST /analyze` for multipart CSV uploads with field name `file`.
* Preserve `GET /sample-data` for analyzing the included sample and `?download=true` for downloading it.
* Preserve `POST /config` and its dashboard visibility fields.
* Preserve support for `filter_query`, `chart_type`, `x_column`, `y_column`, `aggregation`, `sort_by`, and `limit` where applicable.
* Preserve the existing dashboard outputs: detected columns, summary metrics, charts, insights, and a preview capped at 10 rows.
* Add a small `GET /state` synchronization endpoint that returns the current bounded dashboard snapshot and revision, or indicates that nothing changed when given the browser's current revision.
* Refactoring route internals and response models is allowed, but existing browser behavior and endpoint purposes must continue to work.

Bounded backend refactor:

* Extract shared CSV parsing and analytics into a small reusable module instead of duplicating logic between FastAPI and MCP. Keep the route layer and MCP tool layer thin.
* Do not over-split the project. A reasonable target is `main.py`, one analytics module, and tests; add one additional MCP module only if it clearly prevents coupling or circular imports.
* Use typed request/response structures or focused validation where they materially improve the API contract, but do not build a large domain-model hierarchy.
* Keep errors concise and actionable. Do not expose long pandas internals to browser or MCP users.

Shared dashboard state:

* TinyBI 2 intentionally has one shared local workspace. The browser, preserved HTTP endpoints, and all MCP clients operate on the same active dashboard state.
* Define one focused `DashboardState` or `DashboardStore` and attach the same instance to the parent FastAPI application's `app.state`. Inject or close over that exact instance in the MCP tools; do not create a separate MCP copy.
* Do not use FastMCP `Context` session state as the source of truth. FastMCP session state is isolated to an MCP session and would not automatically be shared with browser requests.
* Keep at least the active dataset content or parsed representation, a safe source label, detected metadata, filter query, X/Y columns, aggregation, chart type, sorting, limit, dashboard visibility configuration, current bounded results, monotonically increasing revision, and last update source (`browser` or `mcp`) in the shared state.
* Never expose raw uploaded bytes, the full DataFrame, or an absolute server path through `GET /state`, API responses, or MCP output. Return only bounded results and safe source metadata.
* Route browser uploads, sample loading, control changes, config changes, `analyze_dataset`, and `create_chart` through the same state-update service and analytics functions.
* `analyze_dataset` commits the automatic dashboard result. `create_chart` commits its focused chart as the active chart and also keeps or recomputes coherent bounded metrics, insights, and preview data for the same filtered dataset so `GET /state` always remains directly renderable by the browser.
* Make state updates atomic with a small lock. Compute and validate a candidate result before committing it; a failed parse, filter, or analysis must leave the active state and revision unchanged.
* Increment the revision exactly once after each successful state-changing action. Include the resulting revision and update source in browser API and state-changing MCP responses.
* Define `GET /state` with an optional non-negative `after_revision` query parameter. Return the current bounded snapshot when it is newer; otherwise return a small unchanged response or HTTP 204. Do not hold long-running requests open.
* This state is intentionally in-memory and process-local. Do not add a database or persistence layer. Document that server restart/reload clears it and that the shared-workspace mode must run with one Uvicorn worker.
* Initialize with no uploaded dataset. When an operation needs data and no active dataset exists, use the included sample as the initial active dataset.

Required analytics fixes:

* Keep the common encoding fallback order: `utf-8`, `utf-8-sig`, `cp1252`, then `latin1`.
* Return the selected encoding in analysis metadata.
* Add an explicit configurable upload/input size limit with a sensible local-demo default, and return a clear error when it is exceeded.
* Report row counts before filtering and after filtering.
* Distinguish likely measures, dates, dimensions, and identifier-like numeric columns. Fields such as IDs, postal codes, ZIP codes, and code columns must not become the primary measure merely because they are numeric.
* Perform numeric/date coercion needed for analysis before applying typed filters, or otherwise make filtering semantics clear and correct. Do not silently compare date-like or numeric-text fields only as raw strings.
* Keep pandas-query-style filtering if practical, but document its syntax, validate failures cleanly, and include examples using actual detected column names. Mention case sensitivity and backticks for names containing spaces.
* Invalid `x_column`, `y_column`, aggregation, chart type, sort mode, or limit values must produce clear validation feedback rather than silently changing to an unrelated value.
* Custom charts using a date X axis must be chronologically ordered by default. Do not sort a time series by metric value unless the caller explicitly requests that.
* Treat equal median and mean as equal; never describe equality as "below average".
* Make trend insights compare date aggregates rather than only the first and last individual rows.
* Keep insight claims modest and deterministic. Do not imply statistical significance or causality.
* Return normalized preview values consistently with the analyzed data, including readable date values and JSON-safe missing values.

Required browser refinements:

* Replace free-text X and Y column fields with dropdowns populated from the detected metadata after an initial analysis. Preserve the currently valid selection when possible.
* Surface detected dates, measures, dimensions, and identifiers in a compact way so users do not have to guess column names.
* Add concise filter help and at least one example based on the active dataset.
* Expose sorting in the controls because the backend already supports it.
* Keep upload, drag-and-drop, sample loading, loading status, errors, dashboard toggles, charts, insights, and preview working.
* Prevent stale requests from replacing newer results. Use `AbortController` or an equivalently small approach when uploads or control changes overlap.
* Disable or clearly mark relevant controls while an analysis request is active.
* Make request parsing robust when an error response is not JSON.
* Treat `POST /config` as an intentional shared-workspace update. Store validated visibility settings in the shared dashboard state so MCP responses and every open browser view observe the same configuration.
* If a config update fails, restore the checkbox state or otherwise keep UI state consistent.
* Poll `GET /state` with the last seen revision at a modest interval while the page is visible. When MCP changes the workspace, update the controls, visibility, status, metrics, charts, insights, and preview from the returned snapshot without starting another analysis request.
* Ignore snapshots older than the browser's last rendered revision and do not dispatch form `change` handlers while applying remote state. Avoid feedback loops in which rendering MCP state triggers a new browser analysis.
* Show a compact indication of whether the latest state was updated from the browser or MCP so the shared behavior is visible during the workshop.
* Improve accessibility with an accessible file-input label, an `aria-live` status region, visible keyboard focus, and useful text context for charts.
* Use a pinned Chart.js version rather than an unversioned CDN URL. Keeping the CDN is acceptable for this local workshop app; document that charts require network access unless Chart.js is vendored.
* Keep the information-dense responsive layout working on laptop and mobile sizes. Refine the current design rather than replacing it with a large new design system.

FastMCP integration:

* Add a FastMCP server and mount it into the existing FastAPI application at `/mcp`.
* Follow the current FastMCP mounting pattern documented at https://gofastmcp.com/integrations/fastapi#mounting-an-mcp-server.
* Create the MCP ASGI app with `mcp.http_app(path='/')`, pass its lifespan to FastAPI, and mount it with `app.mount('/mcp', mcp_app)`. If the application gains its own lifespan, combine the lifespans correctly rather than dropping either one.
* The MCP transport endpoint must be reachable at `/mcp` while all existing FastAPI routes remain reachable at their original paths.
* Register tools before creating the MCP ASGI app unless the installed FastMCP version explicitly supports dynamic registration safely.
* Give the MCP tools the same `DashboardStore` instance attached to the parent FastAPI `app.state`. Mounting alone does not make FastAPI application state and FastMCP session state interchangeable.
* Do not generate an MCP server mechanically from FastAPI/OpenAPI.
* Do not expose every HTTP endpoint as an MCP tool.
* Do not create tools named after transport mechanics such as `post_analyze` or `get_sample_data`.

MCP tool design:

Expose exactly three tools centered on the AI's tasks:

1. `inspect_dataset`
   * Lets an AI inspect the active shared dataset, the built-in sample, a local CSV path, or inline CSV text before deciding how to analyze it.
   * When dataset input is omitted, inspect the active browser/MCP dataset, falling back to the sample only when the workspace has no active dataset. Explicit inspection of another dataset remains read-only and does not replace the active workspace dataset.
   * Returns compact metadata: encoding, row/column counts, likely dates, measures, dimensions, identifiers, missing-value counts, useful date range/category summaries, and valid analysis options.
   * Returns one or two valid filter examples based on real columns and values.
   * Does not return the entire CSV or large chart payloads.

2. `analyze_dataset`
   * Produces and commits the complete automatic dashboard workflow available in the browser: use the active shared dataset or explicitly replace it with sample/path/inline CSV input, apply an optional filter, and request desired result sections.
   * Reuses exactly the same validated analytics pipeline as `POST /analyze` and `/sample-data`.
   * Returns machine-readable metadata, metrics, charts, insights, and an optional preview, with the same size caps as the browser API.
   * Makes reasonable defaults when neither shared state nor explicit controls provide a value, reports the effective values, commits the resulting dashboard snapshot, and returns the new state revision.

3. `create_chart`
   * Creates and commits one focused analysis view when the AI or user wants to control the filter query, X column, Y column, aggregation, chart type, sorting, or result limit directly.
   * Uses the active shared dataset when dataset input is omitted; explicit sample/path/inline input replaces the active dataset after successful validation.
   * Accepts `filter_query`, `x_column`, `y_column`, `aggregation`, `chart_type`, `sort_by`, and `limit` as explicit typed parameters and stores the effective values in shared state so the browser immediately reflects the MCP-created chart.
   * Validates requested columns and options against the selected dataset and returns actionable valid choices when an input is wrong.
   * Returns the effective configuration, row counts before and after filtering, one bounded Chart.js-compatible chart payload, and the small aggregated table behind that chart. It does not return the entire automatic dashboard.
   * Reuses the same filtering, coercion, aggregation, sorting, and chart-building functions as the browser API and `analyze_dataset`.

MCP discovery and prompting contract:

* Treat `tools/list` metadata as prompt engineering, not generated API documentation. Assume the calling AI has no README, source code, browser UI, prior TinyBI knowledge, or hidden explanation beyond the tool list.
* Keep the tool list compact, but give the AI enough context to select the correct tool, construct valid arguments, understand defaults, interpret output, and recover from errors.
* A tool description must state the user goal it serves, when to choose it, when to choose a neighboring tool instead, whether inspection is needed first, what it returns, and important omissions or bounds.
* A field description must explain domain meaning rather than restating its Python type. State omission/default behavior, relationships to other fields, exact-name or case-sensitivity rules, processing order, units or limits, and whether returned data is raw, normalized, aggregated, bounded, or heuristic where applicable.
* Put rules the schema can enforce into JSON Schema through literals, discriminated unions, required fields, `additionalProperties: false`, `minLength`, `minimum`, `maximum`, `minItems`, `maxItems`, and `uniqueItems`. Do not rely on prose for machine-enforceable constraints.
* Do not duplicate complete enum lists in descriptions. Use descriptions to explain what choices mean and how defaults are resolved.
* Include examples only where a format is otherwise easy to misunderstand, especially pandas filter expressions and local paths.
* Tool descriptions must remain independently useful even if a client does not expose FastMCP server instructions to the model.

Use these exact LLM-facing tool descriptions:

* `inspect_dataset`: "Discover how TinyBI can analyze a CSV without changing the shared dashboard. Omit dataset to inspect the dataset currently open in the browser or selected by an earlier MCP call; if none exists, TinyBI inspects its sample. Supply dataset only to inspect another source without making it active. Use this when exact column names, inferred roles, missingness, ranges, or filter syntax are unknown. Returns compact metadata, valid choices, filter examples, and the current workspace revision; it does not return dashboard sections, raw rows, or charts."
* `analyze_dataset`: "Run TinyBI's broad automatic dashboard workflow and publish the result to the shared browser/MCP workspace. Omit dataset to analyze what is currently open; supply dataset to replace the active source after successful validation. Use this for an overview, metrics, automatic charts, deterministic insights, or a preview. Use create_chart for one explicit X/Y aggregation. Returns bounded results, effective settings, and the committed workspace revision; the browser will display the same state."
* `create_chart`: "Create one focused grouped chart and publish it to the shared browser/MCP workspace. Omit dataset to use what is currently open; supply dataset to replace the active source after successful validation. Use this for explicit filtering, X/Y columns, aggregation, chart type, sorting, or group limit. Inspect first if valid columns are unknown. Returns the effective configuration, row counts, aligned chart data, bounded aggregate table, and committed workspace revision; it does not return raw rows or the full automatic dashboard."

Dataset input contract:

* Replace independently optional `source`, `path`, and `inline_csv` tool arguments with one optional `dataset` argument represented by a schema-enforced discriminated union. Invalid source/payload combinations should fail schema validation rather than depend only on runtime checks.
* The `dataset` field description must be: "Optionally selects one CSV input. Omit this field to use the dataset active in TinyBI's shared browser/MCP workspace, falling back to the included sample only when no dataset is active. Supply it to use the included sample, a permitted project-local CSV path, or complete inline CSV text. For state-changing tools, a successfully validated explicit dataset becomes active; inspect_dataset never changes active state."
* The `sample` variant contains only `source: Literal['sample']`. Describe `source` as: "Use TinyBI's included sample_data.csv. This source has no additional input fields."
* The `path` variant requires `source: Literal['path']` and a non-empty `path`. Describe `source` as: "Analyze a .csv file available inside TinyBI's permitted project directory." Describe `path` as: "Path to a .csv file that resolves inside TinyBI's permitted project directory. Relative and absolute paths are accepted only when their resolved location remains inside that directory. Example: data/orders.csv."
* The `inline` variant requires `source: Literal['inline']` and non-empty `inline_csv`. Describe `source` as: "Analyze CSV text supplied directly in this tool call." Describe `inline_csv` as: "Complete CSV text, including its header row. Use this when the data is not available through a permitted server-local path. The configured input-size limit applies."
* Use focused Pydantic models and `Annotated[..., Field(...)]`, or an equivalently clear FastMCP-supported approach, so these descriptions and constraints appear in `tools/list`.
* Restrict path-based reads to CSV files in the project directory or another explicitly documented safe data directory. Resolve paths and symlinks before checking the boundary. Inline CSV input provides the alternative for data outside that directory.

Analysis input field descriptions and constraints:

* Use this exact `filter_query` description on both tools that accept it: "Optional, case-sensitive pandas DataFrame.query expression applied after likely numeric and date columns are coerced, but before metrics, grouping, and aggregation. Use exact column names and wrap names containing spaces or punctuation in backticks. String comparisons are case-sensitive. Examples: Revenue > 100 and Region == 'West', or `Order Date` >= '2026-01-01'. Pass an expression, not SQL or natural-language instructions. Omit to keep the active workspace filter; pass an empty string to clear it and analyze all rows. When no workspace filter exists, omission analyzes all rows."
* Describe `sections` as: "Selects which dashboard payloads to return. Omit or pass null to return metrics, charts, insights, and preview. Metadata, detected columns, effective configuration, and filter examples are always returned." Constrain a provided list to one through four unique members of `metrics`, `charts`, `insights`, and `preview`.
* Describe `x_column` as: "Exact, case-sensitive CSV column used to group rows and produce chart labels. Date columns create time groups; dimensions and identifiers create category groups. Use a value from inspect_dataset.valid_options.x_columns." Require a non-empty string.
* Describe `y_column` as: "Exact, case-sensitive detected numeric measure aggregated within each X-column group. Identifier-like numeric columns are not valid measures. Use a value from inspect_dataset.valid_options.y_columns." Require a non-empty string.
* Describe `aggregation` as: "Operation applied to y_column values inside each x_column group. count counts non-missing Y values rather than all source rows." Keep the default `sum` and the constrained aggregation literal.
* Describe `chart_type` as: "Chart.js chart type for the returned specification. auto resolves to line when X is a detected date and bar otherwise. The result is structured chart data, not a rendered image." Keep the default `auto` and the constrained chart-type literal.
* Describe `sort_by` as: "Controls aggregated-group order. Label modes sort by X labels; date labels are chronological. Value modes sort by the aggregated Y result. Omit to use chronological ascending labels for date X columns and descending aggregate values otherwise." Keep it optional and constrained to supported sort literals.
* Describe `limit` as: "Maximum number of aggregated groups returned after filtering, grouping, and sorting. This limits chart points or bars, not source rows. The aggregate table uses the same bound and order." Keep the default `20` and expose `minimum: 1` and `maximum: 50` in the schema.

Structured output contract:

* Do not annotate tool returns as an unrestricted `dict` that generates `outputSchema: {type: object, additionalProperties: true}`. Define focused Pydantic, dataclass, TypedDict, or explicit FastMCP output schemas so the tool list tells the AI how to interpret successful results.
* Keep output models focused and shared where useful; this requirement justifies a small response-model set but not a large domain hierarchy.
* Add descriptions to output fields and nested fields. At minimum, expose and describe the following contracts.
* Include a compact `workspace` object in every tool result. Describe it as: "Current shared browser/MCP workspace identity and synchronization metadata. This contains bounded state metadata, not raw CSV content."
* Describe `workspace.revision` as: "Monotonically increasing shared-state revision. Browser and MCP results with the same revision describe the same committed dashboard state. inspect_dataset does not increment it."
* Describe `workspace.last_updated_by` as: "Interface that most recently committed the shared state: browser or mcp. Null before the first state-changing action."
* Describe `workspace.active_source` as: "Safe label for the dataset currently active in the shared workspace. Absolute server paths and inline CSV content are never returned."
* Describe `workspace.visibility` as the shared metrics/charts/insights/preview visibility configuration and `workspace.controls` as the currently committed filter/X/Y/aggregation/chart/sort/limit values.

`inspect_dataset` output:

* `workspace`: report the current revision and active workspace summary without mutating it. If an explicit different dataset was inspected, distinguish `inspected_source` from `workspace.active_source`.
* `metadata`: "Compact facts about the parsed dataset and TinyBI's inferred column roles. Role detection is heuristic and should be verified against the user's domain knowledge when necessary."
* `metadata.encoding`: "Text encoding successfully used to parse the CSV after applying TinyBI's documented encoding fallback order."
* `metadata.row_count`: "Number of non-blank data rows found in the parsed CSV. The header row is not counted."
* `metadata.column_count`: "Number of CSV columns detected from the header."
* `metadata.dates`: "Columns successfully coerced to date values and suitable for chronological grouping or filtering."
* `metadata.measures`: "Numeric columns considered suitable for aggregation. Identifier-like numeric fields are excluded. These are the valid Y-column choices for create_chart."
* `metadata.dimensions`: "Non-measure columns suitable for grouping, categorization, or filtering. High-cardinality dimensions may still produce many groups."
* `metadata.identifiers`: "Columns that appear to identify records or entities, such as IDs, postal codes, ZIP codes, SKUs, or code fields. They may be used as X columns but are not treated as measures."
* `missing_values`: "Mapping from every column name to its count of missing values. A count of 0 means the column is complete in the parsed dataset."
* `date_ranges`: "Mapping from each detected date column to its earliest and latest non-missing values. Dates use ISO YYYY-MM-DD form. Columns without usable dates are omitted."
* `category_summaries`: "Bounded frequency summaries for selected detected dimensions. Each nested mapping contains observed category labels and row counts; omitted categories or dimensions may still exist in the dataset."
* `filter_examples`: "One or two executable, case-sensitive pandas-query expressions generated from actual columns and values in this dataset. These can be reused or adapted in another TinyBI tool call."
* `valid_options`: "Dataset-specific columns and server-supported control values accepted by analysis tools. Prefer these choices over guessing field names."
* Describe `valid_options.x_columns` as exact case-sensitive values accepted by `x_column`, `valid_options.y_columns` as detected measures accepted by `y_column`, and the other valid-option fields as the supported aggregations, chart types, sort modes, and limit bounds.

`analyze_dataset` output:

* `workspace`: report the newly committed revision, active source, controls, visibility, and `last_updated_by: mcp`.
* `metadata`: "Parsing and row-count facts for this analysis, including the effect of filtering."
* `metadata.row_count_before_filter`: "Number of non-blank data rows available before applying filter_query."
* `metadata.row_count_after_filter`: "Number of rows retained after applying filter_query. Equal to row_count_before_filter when no filter was supplied."
* `effective_config`: "Resolved analysis choices TinyBI actually used after applying defaults. Use these values to understand how automatic charts and metrics were selected."
* `columns`: "Exact detected column names and their inferred analysis roles."
* Add `returned_sections`: "Result sections explicitly included in this response. Use this to distinguish an unrequested section from a requested section that produced no results."
* `metrics`: "Requested summary metrics. Empty when not requested or when no applicable metric can be computed; consult returned_sections to distinguish these cases."
* Make metrics machine-readable: return a JSON-native `value`, a separate human-readable `display_value`, and a `hint` describing what was calculated. Do not make a formatted numeric string the only metric value.
* `charts`: "Requested bounded Chart.js-compatible chart specifications. These are structured chart data, not rendered images."
* Describe chart `labels` and `values` with the invariant that `labels[i]` corresponds to `values[i]`.
* `insights`: "Requested deterministic observations derived from the filtered data. These statements describe the observed dataset and do not claim causality or statistical significance."
* `preview`: "Up to 10 normalized rows from the filtered dataset. Dates are readable strings and missing values are null. This is a preview, not the complete CSV."

`create_chart` output:

* `workspace`: report the newly committed revision, active source, controls, visibility, and `last_updated_by: mcp`.
* `effective_config`: "Exact configuration used to produce the chart after resolving defaults."
* `row_counts`: "Source-row counts before and after filtering. These are not counts of aggregated groups."
* `row_counts.before_filter`: "Number of non-blank source rows before applying filter_query."
* `row_counts.after_filter`: "Number of source rows retained after applying filter_query and used for aggregation."
* `chart`: "Bounded Chart.js-compatible specification for one grouped aggregation. It is not an image."
* `chart.labels`: "Ordered group labels. labels[i] corresponds to values[i] and to the table row at the same position."
* `chart.values`: "Ordered aggregated values. values[i] corresponds to labels[i] and to the table row at the same position."
* `table`: "Bounded records underlying the chart, in chart order. Each record represents one aggregated X group, not one raw CSV row. Dynamic property names match the selected X and Y columns."

FastMCP metadata and errors:

* Initialize FastMCP with concise server instructions: "TinyBI provides three CSV analytics tools connected to one shared browser/MCP dashboard workspace. Omit dataset to use what is currently open; an explicit dataset on analyze_dataset or create_chart replaces the active source after successful validation. inspect_dataset never changes state. Use analyze_dataset for a broad dashboard and create_chart for one explicit aggregation. Successful state-changing calls are reflected in the browser and return a new revision."
* Give every tool a useful human title and explicit annotations. Set `readOnlyHint: true` only for `inspect_dataset`. Set `readOnlyHint: false`, `destructiveHint: false`, and `openWorldHint: false` for `analyze_dataset` and `create_chart`: they mutate only the in-memory shared dashboard, not files or external systems.
* Enable FastMCP error masking for unexpected exceptions. Convert expected CSV, source, filter, column, and control validation failures into explicit `ToolError` messages so the AI receives an MCP tool execution error it can repair.
* Actionable tool errors must identify the invalid field and value when safe, state the accepted constraint or detected choices, and explain whether inspection or changed arguments can fix the call. Include one corrected example for malformed filter syntax. State-changing tool errors must not increment the revision or partially alter the workspace. Do not expose stack traces, long pandas internals, or absolute server paths.

General tool requirements:

* Use explicit Python type hints, constrained literals, defaults that make the sample easy to analyze, and LLM-facing field metadata as specified above.
* Keep control overrides explicit while making dataset and dashboard continuity stateful. A tool must be usable directly without a preparatory mutation call, but omitted dataset/filter values intentionally inherit the active workspace as documented.
* Apply the same size, encoding, validation, and JSON-cleaning behavior to HTTP and MCP calls.
* Keep tool output bounded and useful in an LLM context. Never return all dataset rows, raw uploaded bytes, HTML, or redundant prose around structured results.
* Include shared visibility and current controls in bounded workspace metadata so the AI can understand the browser state. Do not add a fourth tool only for presentation preferences.

Sample data and repository correctness:

* Keep or create `sample_data.csv` in the local destination so the app can be verified with it.
* `sample_data.csv` will be distributed separately with the workshop. It may remain covered by `*.csv` in `.gitignore`; do not add a `!sample_data.csv` exception.
* Remove copied generated artifacts from the destination.
* Keep a lockfile generated by `uv`.

Documentation requirements:

Update `README.md` to include:

* what TinyBI 2 does and what was refined
* `uv sync`, `make serve`, and the direct Uvicorn command
* the actual included sample schema rather than fictitious lowercase column names
* practical filter examples, including spaces/backticks and case sensitivity
* upload-size and local-file-path restrictions
* all preserved HTTP endpoints
* the shared-workspace behavior, `GET /state`, revision synchronization, and the fact that browser and MCP actions update the same dashboard
* the MCP URL `http://127.0.0.1:8000/mcp`
* a short explanation of the three MCP tools and example user intentions for each
* omission of `dataset` as "use the active shared dataset", plus the schema-enforced sample, path, and inline variants with one valid example for each
* how to connect with MCP Inspector or another HTTP-capable MCP client
* the pinned CDN/network limitation for Chart.js
* the in-memory limitations: restart/reload resets state, every client shares one workspace, and the app must run with one worker

Update `AGENTS.md` to preserve the `uv add` and `uv add --dev` dependency rules and add the exact test command.

Verification requirements:

* Add focused tests for the shared analytics pipeline and critical regressions rather than exhaustive coverage.
* At minimum test: sample analysis, non-UTF-8 parsing, empty/oversized input errors, identifier exclusion from primary measures, filtering, chronological date charts, equal median/mean wording, and JSON-safe previews.
* Test that the preserved FastAPI routes respond, `POST /analyze` still accepts multipart field `file`, and successful browser API changes return increasing revisions.
* Test `GET /state` with no state, a newer revision, and an `after_revision` that is already current. Assert that its payload remains bounded and contains no raw CSV bytes, inline CSV text, full dataset, or absolute path.
* Test FastMCP in-process with `fastmcp.Client`: list the three tools, call `inspect_dataset`, call `analyze_dataset`, and call `create_chart` with explicit filter/X/Y/aggregation/chart/sort/limit options.
* Prove browser-to-MCP sharing: upload a distinctive multipart CSV through `POST /analyze`, then call `inspect_dataset` and `analyze_dataset` without a `dataset` argument and assert that both use the uploaded active dataset.
* Prove MCP-to-browser sharing: call `create_chart` with a distinctive configuration and no dataset argument, then call `GET /state` and assert that the revision, controls, active chart, update source, and browser-renderable results match the MCP change.
* Prove configuration sharing: update visibility through `POST /config`, then assert that a subsequent MCP result reports the same visibility and that `GET /state` retains it.
* Prove atomic failure behavior: record state and revision, trigger invalid MCP and HTTP filter/column requests, and assert that neither the state nor revision changed.
* Treat the `tools/list` response as a tested product contract. Assert that all three tools expose the intended routing descriptions, every input property has a useful description, dataset sources form an optional discriminated union, numeric/list constraints appear in JSON Schema, output schemas expose named documented fields rather than an unrestricted object, `inspect_dataset` is read-only, and both state-changing tools are marked non-read-only and non-destructive.
* Test model-repairable MCP errors through `fastmcp.Client`: an invalid source payload, unknown X or Y column, malformed filter, and out-of-range limit must return `isError: true` with concise corrective guidance and no internal path or stack trace.
* Run the tests.
* Verify imports and application startup.
* Verify the mounted MCP server can initialize and list tools at `/mcp`, using an MCP client or Inspector-compatible check rather than treating it as a normal JSON GET endpoint.
* Fix failures and obvious regressions before finishing.

Scope control:

* Do not implement arbitrary natural-language-to-pandas-query generation inside the server; the calling AI already handles language understanding.
* Do not add chat, an embedded LLM, model-provider dependencies, vector storage, persistence, accounts, deployment infrastructure, or speculative BI features.
* Do not create more than three MCP tools without a concrete necessity.
* Do not add user accounts, browser-session middleware, workspace IDs, Redis, a database, WebSockets, or cross-worker synchronization. This version deliberately demonstrates one in-memory workspace; bounded revision polling is enough.
* Do not rewrite the frontend into React/Vue/Svelte or add a frontend build pipeline.
* Do not split the backend into many layers or introduce abstractions used only once.

Deliverable:
A complete working TinyBI 2 project in the selected destination. Do not stop after planning or analysis. Copy or recreate the baseline, implement the refinements and mounted MCP server, run verification, fix failures, and provide a concise final summary containing the selected mode, destination, important changes, MCP URL and tools, test results, and run instructions.

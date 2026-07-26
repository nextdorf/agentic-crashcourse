from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from analytics import AnalysisError, DashboardStore, MAX_INPUT_BYTES


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / 'sample_data.csv'
DATASET_DESCRIPTION = (
  'Optionally selects one CSV input. Omit this field to use the dataset active in TinyBI\'s shared browser/MCP '
  'workspace, falling back to the included sample only when no dataset is active. Supply it to use the included '
  'sample, a permitted project-local CSV path, or complete inline CSV text. For state-changing tools, a successfully '
  'validated explicit dataset becomes active; inspect_dataset never changes active state.'
)
FILTER_DESCRIPTION = (
  'Optional, case-sensitive pandas DataFrame.query expression applied after likely numeric and date columns are '
  'coerced, but before metrics, grouping, and aggregation. Use exact column names and wrap names containing spaces '
  'or punctuation in backticks. String comparisons are case-sensitive. Examples: Revenue > 100 and Region == '
  "'West', or `Order Date` >= '2026-01-01'. Pass an expression, not SQL or natural-language instructions. Omit to "
  'keep the active workspace filter; pass an empty string to clear it and analyze all rows. When no workspace filter '
  'exists, omission analyzes all rows.'
)


class StrictModel(BaseModel):
  model_config = ConfigDict(extra='forbid')


class SampleDataset(StrictModel):
  source: Literal['sample'] = Field(
    description="Use TinyBI's included sample_data.csv. This source has no additional input fields."
  )


class PathDataset(StrictModel):
  source: Literal['path'] = Field(
    description="Analyze a .csv file available inside TinyBI's permitted project directory."
  )
  path: str = Field(
    min_length=1,
    description=(
      "Path to a .csv file that resolves inside TinyBI's permitted project directory. Relative and absolute paths "
      'are accepted only when their resolved location remains inside that directory. Example: data/orders.csv.'
    ),
  )


class InlineDataset(StrictModel):
  source: Literal['inline'] = Field(description='Analyze CSV text supplied directly in this tool call.')
  inline_csv: str = Field(
    min_length=1,
    description=(
      'Complete CSV text, including its header row. Use this when the data is not available through a permitted '
      'server-local path. The configured input-size limit applies.'
    ),
  )


DatasetInput = Annotated[SampleDataset | PathDataset | InlineDataset, Field(discriminator='source')]
Aggregation = Literal['sum', 'mean', 'median', 'min', 'max', 'count']
ChartType = Literal['auto', 'bar', 'line']
SortMode = Literal['label_asc', 'label_desc', 'value_asc', 'value_desc']
Section = Literal['metrics', 'charts', 'insights', 'preview']


class Visibility(StrictModel):
  show_metrics: bool = Field(description='Whether browser and MCP consumers should show dashboard metrics.')
  show_charts: bool = Field(description='Whether browser and MCP consumers should show dashboard charts.')
  show_insights: bool = Field(description='Whether browser and MCP consumers should show deterministic insights.')
  show_preview: bool = Field(description='Whether browser and MCP consumers should show the bounded row preview.')


class Controls(StrictModel):
  filter_query: str | None = Field(description='Currently committed pandas query, or null when all rows are used.')
  x_column: str | None = Field(description='Currently committed exact grouping column, or null if unavailable.')
  y_column: str | None = Field(description='Currently committed numeric measure, or null if unavailable.')
  aggregation: str = Field(description='Currently committed grouped aggregation.')
  chart_type: str = Field(description='Currently committed resolved Chart.js chart type.')
  sort_by: str | None = Field(description='Currently committed group ordering mode.')
  limit: int = Field(description='Currently committed maximum chart groups.', ge=1, le=50)


class Workspace(StrictModel):
  revision: int = Field(
    description=(
      'Monotonically increasing shared-state revision. Browser and MCP results with the same revision describe the '
      'same committed dashboard state. inspect_dataset does not increment it.'
    ),
    ge=0,
  )
  last_updated_by: Literal['browser', 'mcp'] | None = Field(
    description='Interface that most recently committed the shared state: browser or mcp. Null before the first state-changing action.'
  )
  active_source: str | None = Field(
    description=(
      'Safe label for the dataset currently active in the shared workspace. Absolute server paths and inline CSV '
      'content are never returned.'
    )
  )
  visibility: Visibility = Field(description='Shared metrics/charts/insights/preview visibility configuration.')
  controls: Controls = Field(description='Currently committed filter/X/Y/aggregation/chart/sort/limit values.')


class Metadata(StrictModel):
  encoding: str = Field(description='Text encoding successfully used after TinyBI applied its documented fallback order.')
  row_count: int = Field(description='Number of non-blank CSV data rows; the header is not counted.', ge=0)
  column_count: int = Field(description='Number of CSV columns detected from the header.', ge=1)
  dates: list[str] = Field(description='Columns coerced to dates and suitable for chronological grouping or filtering.')
  measures: list[str] = Field(description='Numeric aggregation columns; identifier-like numeric fields are excluded.')
  dimensions: list[str] = Field(description='Non-measure columns suitable for grouping, categorization, or filtering.')
  identifiers: list[str] = Field(description='Columns heuristically identified as record/entity IDs, postal codes, SKUs, or codes.')


class ValidOptions(StrictModel):
  x_columns: list[str] = Field(description='Exact case-sensitive values accepted by x_column.')
  y_columns: list[str] = Field(description='Detected measures accepted by y_column.')
  aggregations: list[str] = Field(description='Server-supported grouped aggregation values.')
  chart_types: list[str] = Field(description='Server-supported Chart.js chart type choices.')
  sort_modes: list[str] = Field(description='Server-supported grouped-result ordering modes.')
  limit_bounds: dict[str, int] = Field(description='Inclusive minimum and maximum supported group limits.')


class InspectOutput(StrictModel):
  workspace: Workspace = Field(
    description='Current shared browser/MCP workspace identity and synchronization metadata. This contains bounded state metadata, not raw CSV content.'
  )
  inspected_source: str = Field(description='Safe label for the dataset inspected; it can differ from workspace.active_source.')
  metadata: Metadata = Field(
    description=(
      "Compact facts about the parsed dataset and TinyBI's inferred column roles. Role detection is heuristic and "
      "should be verified against the user's domain knowledge when necessary."
    )
  )
  missing_values: dict[str, int] = Field(description='Mapping from every column name to its missing-value count.')
  date_ranges: dict[str, dict[str, str]] = Field(description='Earliest and latest ISO dates for detected date columns.')
  category_summaries: dict[str, dict[str, int]] = Field(description='Bounded observed category frequencies for selected dimensions.')
  filter_examples: list[str] = Field(description='One or two executable case-sensitive pandas-query expressions from actual values.', max_length=2)
  valid_options: ValidOptions = Field(description='Dataset-specific columns and server-supported controls accepted by analysis tools.')


class AnalysisMetadata(Metadata):
  row_count_before_filter: int = Field(description='Number of non-blank rows before applying filter_query.', ge=0)
  row_count_after_filter: int = Field(description='Number of rows retained after applying filter_query.', ge=0)


class Metric(StrictModel):
  label: str = Field(description='Short metric name.')
  value: int | float | str | None = Field(description='JSON-native calculated value, before display formatting.')
  display_value: str = Field(description='Human-readable rendering of value.')
  hint: str = Field(description='What TinyBI calculated.')


class Chart(StrictModel):
  id: str = Field(description='Stable identifier within this dashboard response.')
  title: str = Field(description='Human-readable grouped-analysis title.')
  type: Literal['bar', 'line'] = Field(description='Chart.js chart type.')
  labels: list[str] = Field(description='Ordered group labels; labels[i] corresponds to values[i].', max_length=50)
  values: list[int | float | None] = Field(description='Ordered aggregates; values[i] corresponds to labels[i].', max_length=50)


class AnalyzeOutput(StrictModel):
  workspace: Workspace = Field(description='Current shared browser/MCP workspace identity and synchronization metadata. This contains bounded state metadata, not raw CSV content.')
  metadata: AnalysisMetadata = Field(description='Parsing and row-count facts for this analysis, including filtering.')
  effective_config: Controls = Field(description='Resolved analysis choices TinyBI actually used after applying defaults.')
  defaults: Controls = Field(description='Alias of effective_config retained for browser compatibility.')
  columns: dict[str, Any] = Field(description='Exact detected column names and their inferred analysis roles.')
  returned_sections: list[Section] = Field(description='Result sections explicitly included in this response.')
  metrics: list[Metric] = Field(description='Requested machine-readable summary metrics; empty when omitted or unavailable.')
  charts: list[Chart] = Field(description='Requested bounded Chart.js-compatible specifications, not rendered images.')
  insights: list[str] = Field(description='Requested deterministic observations without causal or significance claims.')
  preview: list[dict[str, Any]] = Field(description='Up to 10 normalized filtered rows; dates are strings and missing values are null.', max_length=10)
  filter_examples: list[str] = Field(description='One or two executable filter examples based on this dataset.', max_length=2)
  config: Visibility = Field(description='Shared dashboard section visibility retained for browser API compatibility.')


class RowCounts(StrictModel):
  before_filter: int = Field(description='Number of non-blank source rows before filter_query.', ge=0)
  after_filter: int = Field(description='Number of source rows retained for aggregation.', ge=0)


class ChartOutput(StrictModel):
  workspace: Workspace = Field(description='Current shared browser/MCP workspace identity and synchronization metadata. This contains bounded state metadata, not raw CSV content.')
  effective_config: Controls = Field(description='Exact configuration used to produce the chart after resolving defaults.')
  row_counts: RowCounts = Field(description='Source-row counts before and after filtering, not aggregate-group counts.')
  chart: Chart = Field(description='One bounded Chart.js-compatible grouped aggregation; it is not an image.')
  table: list[dict[str, Any]] = Field(description='Bounded aggregate records in chart order; dynamic keys match X and Y columns.', max_length=50)


def resolve_dataset(dataset: DatasetInput | None):
  if dataset is None:
    return None, None
  if dataset.source == 'sample':
    return SAMPLE_PATH.read_bytes(), 'sample_data.csv'
  if dataset.source == 'inline':
    return dataset.inline_csv.encode('utf-8'), 'inline CSV'
  candidate = Path(dataset.path)
  resolved = (BASE_DIR / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
  if resolved.suffix.lower() != '.csv':
    raise AnalysisError(f'Invalid dataset.path {dataset.path!r}; select a .csv file inside the project directory.')
  if not resolved.is_relative_to(BASE_DIR):
    raise AnalysisError('Invalid dataset.path; path reads are restricted to CSV files inside the TinyBI project directory.')
  if not resolved.is_file():
    raise AnalysisError(f'Invalid dataset.path {dataset.path!r}; the CSV file does not exist.')
  if resolved.stat().st_size > MAX_INPUT_BYTES:
    raise AnalysisError(f'The CSV exceeds the {MAX_INPUT_BYTES / 1024 / 1024:g} MB input limit.', 413)
  return resolved.read_bytes(), resolved.name


def create_mcp(store: DashboardStore):
  mcp = FastMCP(
    'TinyBI 2',
    instructions=(
      'TinyBI provides three CSV analytics tools connected to one shared browser/MCP dashboard workspace. Omit '
      'dataset to use what is currently open; an explicit dataset on analyze_dataset or create_chart replaces the '
      'active source after successful validation. inspect_dataset never changes state. Use analyze_dataset for a '
      'broad dashboard and create_chart for one explicit aggregation. Successful state-changing calls are reflected '
      'in the browser and return a new revision.'
    ),
    mask_error_details=True,
  )

  @mcp.tool(
    description=(
      'Discover how TinyBI can analyze a CSV without changing the shared dashboard. Omit dataset to inspect the '
      'dataset currently open in the browser or selected by an earlier MCP call; if none exists, TinyBI inspects '
      'its sample. Supply dataset only to inspect another source without making it active. Use this when exact '
      'column names, inferred roles, missingness, ranges, or filter syntax are unknown. Returns compact metadata, '
      'valid choices, filter examples, and the current workspace revision; it does not return dashboard sections, '
      'raw rows, or charts.'
    ),
    annotations=dict(title='Inspect CSV dataset', readOnlyHint=True, destructiveHint=False, openWorldHint=False),
  )
  def inspect_dataset(
    dataset: Annotated[DatasetInput | None, Field(description=DATASET_DESCRIPTION)] = None,
  ) -> InspectOutput:
    try:
      content, label = resolve_dataset(dataset)
      return InspectOutput.model_validate(store.inspect(content, label))
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description=(
      "Run TinyBI's broad automatic dashboard workflow and publish the result to the shared browser/MCP workspace. "
      'Omit dataset to analyze what is currently open; supply dataset to replace the active source after successful '
      'validation. Use this for an overview, metrics, automatic charts, deterministic insights, or a preview. Use '
      'create_chart for one explicit X/Y aggregation. Returns bounded results, effective settings, and the committed '
      'workspace revision; the browser will display the same state.'
    ),
    annotations=dict(title='Analyze CSV dashboard', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def analyze_dataset(
    dataset: Annotated[DatasetInput | None, Field(description=DATASET_DESCRIPTION)] = None,
    filter_query: Annotated[str | None, Field(description=FILTER_DESCRIPTION)] = None,
    sections: Annotated[
      set[Section] | None,
      Field(
        min_length=1,
        max_length=4,
        description=(
          'Selects which dashboard payloads to return. Omit or pass null to return metrics, charts, insights, and '
          'preview. Metadata, detected columns, effective configuration, and filter examples are always returned.'
        ),
      ),
    ] = None,
  ) -> AnalyzeOutput:
    try:
      content, label = resolve_dataset(dataset)
      result = store.analyze(content, label, dict(filter_query=filter_query), list(sections) if sections else None, 'mcp')
      return AnalyzeOutput.model_validate(result)
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description=(
      'Create one focused grouped chart and publish it to the shared browser/MCP workspace. Omit dataset to use what '
      'is currently open; supply dataset to replace the active source after successful validation. Use this for '
      'explicit filtering, X/Y columns, aggregation, chart type, sorting, or group limit. Inspect first if valid '
      'columns are unknown. Returns the effective configuration, row counts, aligned chart data, bounded aggregate '
      'table, and committed workspace revision; it does not return raw rows or the full automatic dashboard.'
    ),
    annotations=dict(title='Create focused chart', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def create_chart(
    x_column: Annotated[str, Field(min_length=1, description='Exact, case-sensitive CSV column used to group rows and produce chart labels. Date columns create time groups; dimensions and identifiers create category groups. Use a value from inspect_dataset.valid_options.x_columns.')],
    y_column: Annotated[str, Field(min_length=1, description='Exact, case-sensitive detected numeric measure aggregated within each X-column group. Identifier-like numeric columns are not valid measures. Use a value from inspect_dataset.valid_options.y_columns.')],
    dataset: Annotated[DatasetInput | None, Field(description=DATASET_DESCRIPTION)] = None,
    filter_query: Annotated[str | None, Field(description=FILTER_DESCRIPTION)] = None,
    aggregation: Annotated[Aggregation, Field(description='Operation applied to y_column values inside each x_column group. count counts non-missing Y values rather than all source rows.')] = 'sum',
    chart_type: Annotated[ChartType, Field(description='Chart.js chart type for the returned specification. auto resolves to line when X is a detected date and bar otherwise. The result is structured chart data, not a rendered image.')] = 'auto',
    sort_by: Annotated[SortMode | None, Field(description='Controls aggregated-group order. Label modes sort by X labels; date labels are chronological. Value modes sort by the aggregated Y result. Omit to use chronological ascending labels for date X columns and descending aggregate values otherwise.')] = None,
    limit: Annotated[int, Field(ge=1, le=50, description='Maximum number of aggregated groups returned after filtering, grouping, and sorting. This limits chart points or bars, not source rows. The aggregate table uses the same bound and order.')] = 20,
  ) -> ChartOutput:
    try:
      content, label = resolve_dataset(dataset)
      controls = dict(
        filter_query=filter_query, x_column=x_column, y_column=y_column, aggregation=aggregation,
        chart_type=chart_type, sort_by=sort_by, limit=limit,
      )
      return ChartOutput.model_validate(store.create_chart(controls, content, label, 'mcp'))
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  return mcp

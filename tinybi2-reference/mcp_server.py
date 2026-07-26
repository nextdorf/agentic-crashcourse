from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from analytics import (
  AnalysisError,
  CHART_BATCH_LIMIT,
  CHART_LIMIT,
  DashboardStore,
  HEATMAP_AXIS_LIMIT,
  MAX_INPUT_BYTES,
  SECTIONS,
)


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / 'sample_data.csv'
DATASET_DESCRIPTION = (
  'Optionally selects one CSV input. Omit it to use the active shared dataset. A successfully validated explicit '
  'dataset on analyze_dataset or create_charts replaces the active dataset and clears existing managed charts.'
)
VERSION_DESCRIPTION = (
  'Workspace version obtained from inspect_dataset, list_charts, or another successful call. Both fields are '
  'required for mutations; stale versions are rejected without changing state.'
)
FILTER_DESCRIPTION = (
  'Optional case-sensitive pandas DataFrame.query expression. Use exact column names and backticks around names '
  "containing spaces. Example: Revenue > 100 and Region == 'West'. Pass an empty string to clear the filter."
)


class StrictModel(BaseModel):
  model_config = ConfigDict(extra='forbid')


class SampleDataset(StrictModel):
  source: Literal['sample'] = Field(description="Use TinyBI's included sample_data.csv.")


class PathDataset(StrictModel):
  source: Literal['path'] = Field(description='Use a project-local CSV path.')
  path: str = Field(min_length=1, description='CSV path whose resolved location remains inside this project.')


class InlineDataset(StrictModel):
  source: Literal['inline'] = Field(description='Use complete CSV text supplied in this call.')
  inline_csv: str = Field(min_length=1, description='Complete CSV text including its header row.')


DatasetInput = Annotated[SampleDataset | PathDataset | InlineDataset, Field(discriminator='source')]
Aggregation = Literal['sum', 'mean', 'median', 'min', 'max', 'count']
SortMode = Literal['label_asc', 'label_desc', 'value_asc', 'value_desc']
Section = Literal['metrics', 'charts', 'insights', 'preview']


class GroupedDefinitionBase(StrictModel):
  title: str | None = Field(default=None, description='Optional display title; omit for a generated title.')
  x_column: str = Field(min_length=1, description='Exact case-sensitive grouping column.')
  y_column: str = Field(min_length=1, description='Exact detected numeric measure.')
  aggregation: Aggregation = Field(default='sum', description='Grouped aggregation applied to y_column.')
  filter_query: str | None = Field(default=None, description=FILTER_DESCRIPTION)
  sort_by: SortMode | None = Field(default=None, description='Group ordering; omit for a type-appropriate default.')
  limit: int = Field(default=20, ge=1, le=CHART_LIMIT, description='Maximum grouped labels returned.')


class BarDefinition(GroupedDefinitionBase):
  type: Literal['bar'] = Field(description='Grouped vertical bar chart.')


class LineDefinition(GroupedDefinitionBase):
  type: Literal['line'] = Field(description='Grouped line chart.')


class ScatterDefinition(StrictModel):
  type: Literal['scatter'] = Field(description='Ungrouped numeric X/Y scatter plot.')
  title: str | None = Field(default=None, description='Optional display title; omit for a generated title.')
  x_column: str = Field(min_length=1, description='Exact detected numeric measure for the X axis.')
  y_column: str = Field(min_length=1, description='Exact detected numeric measure for the Y axis.')
  filter_query: str | None = Field(default=None, description=FILTER_DESCRIPTION)
  limit: int = Field(default=50, ge=1, le=CHART_LIMIT, description='Maximum source-order points returned.')


class HeatmapDefinition(StrictModel):
  type: Literal['heatmap'] = Field(description='Two-dimensional grouped matrix heatmap.')
  title: str | None = Field(default=None, description='Optional display title; omit for a generated title.')
  x_column: str = Field(min_length=1, description='Exact grouping column for the horizontal axis.')
  y_column: str = Field(min_length=1, description='Exact grouping column for the vertical axis.')
  value_column: str = Field(min_length=1, description='Exact detected numeric measure represented by color.')
  aggregation: Aggregation = Field(default='sum', description='Aggregation applied within each X/Y cell.')
  filter_query: str | None = Field(default=None, description=FILTER_DESCRIPTION)
  x_limit: int = Field(default=10, ge=1, le=HEATMAP_AXIS_LIMIT, description='Maximum horizontal categories.')
  y_limit: int = Field(default=10, ge=1, le=HEATMAP_AXIS_LIMIT, description='Maximum vertical categories.')


ChartDefinition = Annotated[
  BarDefinition | LineDefinition | ScatterDefinition | HeatmapDefinition,
  Field(discriminator='type'),
]


class ChartUpdate(StrictModel):
  id: int = Field(ge=1, description='Existing managed chart ID to preserve.')
  definition: ChartDefinition = Field(description='Complete replacement definition for this chart.')


class Visibility(StrictModel):
  show_metrics: bool
  show_charts: bool
  show_insights: bool
  show_preview: bool


class Controls(StrictModel):
  filter_query: str | None
  x_column: str | None
  y_column: str | None
  aggregation: Aggregation
  chart_type: Literal['auto', 'bar', 'line']
  sort_by: SortMode | None
  limit: int = Field(ge=1, le=CHART_LIMIT)


class EffectiveControls(Controls):
  chart_type: Literal['bar', 'line']


class Workspace(StrictModel):
  incarnation: str = Field(description='Process-lifetime workspace identity used with revision to prevent restart ABA.')
  revision: int = Field(ge=0, description='Monotonic revision within this incarnation.')
  last_updated_by: Literal['browser', 'mcp'] | None
  active_source: str | None
  dataset_generation: int = Field(ge=0)
  visibility: Visibility
  requested_controls: Controls
  managed_chart_ids: list[int]


class Metadata(StrictModel):
  encoding: str
  row_count: int = Field(ge=0)
  column_count: int = Field(ge=1)
  dates: list[str]
  measures: list[str]
  dimensions: list[str]
  identifiers: list[str]


class AnalysisMetadata(Metadata):
  row_count_before_filter: int = Field(ge=0)
  row_count_after_filter: int = Field(ge=0)


class ValidOptions(StrictModel):
  x_columns: list[str]
  y_columns: list[str]
  grouping_columns: list[str]
  aggregations: list[Aggregation]
  automatic_chart_types: list[Literal['auto', 'bar', 'line']]
  managed_chart_types: list[Literal['bar', 'line', 'scatter', 'heatmap']]
  sort_modes: list[SortMode]
  limit_bounds: dict[str, int]
  heatmap_axis_limit: int
  heatmap_cell_limit: int


class GroupedChart(StrictModel):
  id: str | int | None
  scope: Literal['automatic', 'managed']
  title: str
  type: Literal['bar', 'line']
  labels: list[str] = Field(max_length=CHART_LIMIT)
  values: list[int | float | None] = Field(max_length=CHART_LIMIT)


class ScatterPoint(StrictModel):
  x: int | float | None
  y: int | float | None


class ScatterChart(StrictModel):
  id: int | None
  scope: Literal['managed']
  title: str
  type: Literal['scatter']
  x_column: str
  y_column: str
  points: list[ScatterPoint] = Field(max_length=CHART_LIMIT)


class HeatmapCell(StrictModel):
  x: str
  y: str
  value: int | float | None


class HeatmapChart(StrictModel):
  id: int | None
  scope: Literal['managed']
  title: str
  type: Literal['heatmap']
  x_column: str
  y_column: str
  value_column: str
  x_labels: list[str] = Field(max_length=HEATMAP_AXIS_LIMIT)
  y_labels: list[str] = Field(max_length=HEATMAP_AXIS_LIMIT)
  cells: list[HeatmapCell]


ChartPayload = Annotated[GroupedChart | ScatterChart | HeatmapChart, Field(discriminator='type')]


class Metric(StrictModel):
  label: str
  value: int | float | str | None
  display_value: str
  hint: str


class InspectOutput(StrictModel):
  workspace: Workspace
  inspected_source: str
  metadata: Metadata
  missing_values: dict[str, int]
  date_ranges: dict[str, dict[str, str]]
  category_summaries: dict[str, dict[str, int]]
  filter_examples: list[str] = Field(max_length=2)
  valid_options: ValidOptions


class AnalyzeOutput(StrictModel):
  workspace: Workspace
  metadata: AnalysisMetadata
  requested_config: Controls
  effective_config: EffectiveControls
  defaults: EffectiveControls
  columns: dict[str, Any]
  returned_sections: list[Section]
  metrics: list[Metric]
  charts: list[ChartPayload]
  insights: list[str]
  preview: list[dict[str, Any]] = Field(max_length=10)
  filter_examples: list[str] = Field(max_length=2)
  config: Visibility


class ManagedChart(StrictModel):
  id: int = Field(ge=1)
  title: str
  definition: ChartDefinition
  chart: ChartPayload | None = None


class ChartListOutput(StrictModel):
  workspace: Workspace
  charts: list[ManagedChart]


class DeleteOutput(StrictModel):
  workspace: Workspace
  deleted_ids: list[int]


class ReorderOutput(StrictModel):
  workspace: Workspace
  ordered_ids: list[int]


def resolve_dataset(dataset: DatasetInput | None):
  if dataset is None:
    return None, None
  try:
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
  except OSError as exc:
    raise AnalysisError('The selected CSV could not be read; verify that it exists and is readable.') from exc


def model_dict(value):
  return value.model_dump()


def create_mcp(store: DashboardStore):
  mcp = FastMCP(
    'TinyBI 2',
    instructions=(
      'TinyBI exposes one versioned browser/MCP CSV workspace. Inspect before mutating to obtain the current '
      'incarnation and revision. Automatic dashboard charts are disposable; managed charts have monotonic integer '
      'IDs, survive same-dataset analysis, and are cleared by explicit dataset replacement.'
    ),
    mask_error_details=True,
  )

  @mcp.tool(
    description='Inspect an explicit or active CSV without changing workspace state. Returns roles, valid choices, and the current workspace version.',
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
    description='Publish a broad automatic dashboard. Omitting dataset preserves managed charts; an explicit replacement clears them atomically.',
    annotations=dict(title='Analyze CSV dashboard', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def analyze_dataset(
    expected_incarnation: Annotated[str, Field(min_length=1, description=VERSION_DESCRIPTION)],
    expected_revision: Annotated[int, Field(ge=0, description=VERSION_DESCRIPTION)],
    dataset: Annotated[DatasetInput | None, Field(description=DATASET_DESCRIPTION)] = None,
    filter_query: Annotated[str | None, Field(description=FILTER_DESCRIPTION)] = None,
    sections: Annotated[set[Section] | None, Field(min_length=1, max_length=4, description='Dashboard sections to return.')] = None,
  ) -> AnalyzeOutput:
    try:
      content, label = resolve_dataset(dataset)
      ordered_sections = [section for section in SECTIONS if not sections or section in sections]
      result = store.analyze(
        expected_incarnation, expected_revision, content, label, dict(filter_query=filter_query), ordered_sections, 'mcp',
      )
      return AnalyzeOutput.model_validate(result)
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description='List managed chart IDs, order, titles, and definitions without changing state. Rendered bounded chart data is optional.',
    annotations=dict(title='List managed charts', readOnlyHint=True, destructiveHint=False, openWorldHint=False),
  )
  def list_charts(
    include_data: Annotated[bool, Field(description='Include bounded rendered chart payloads.')] = False,
  ) -> ChartListOutput:
    return ChartListOutput.model_validate(store.list_charts(include_data))

  @mcp.tool(
    description='Atomically add one or more managed charts. IDs increase monotonically and are never reused. An explicit dataset replaces the active source and clears old charts.',
    annotations=dict(title='Create managed charts', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def create_charts(
    definitions: Annotated[list[ChartDefinition], Field(min_length=1, max_length=CHART_BATCH_LIMIT, description='Strict type-specific chart definitions.')],
    expected_incarnation: Annotated[str, Field(min_length=1, description=VERSION_DESCRIPTION)],
    expected_revision: Annotated[int, Field(ge=0, description=VERSION_DESCRIPTION)],
    dataset: Annotated[DatasetInput | None, Field(description=DATASET_DESCRIPTION)] = None,
  ) -> ChartListOutput:
    try:
      content, label = resolve_dataset(dataset)
      result = store.create_charts(
        [model_dict(item) for item in definitions], expected_incarnation, expected_revision, content, label, 'mcp',
      )
      return ChartListOutput.model_validate(result)
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description='Atomically replace definitions for selected managed chart IDs while preserving those IDs and all untouched charts.',
    annotations=dict(title='Update managed charts', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def update_charts(
    updates: Annotated[list[ChartUpdate], Field(min_length=1, max_length=CHART_BATCH_LIMIT, description='Unique chart IDs and complete replacement definitions.')],
    expected_incarnation: Annotated[str, Field(min_length=1, description=VERSION_DESCRIPTION)],
    expected_revision: Annotated[int, Field(ge=0, description=VERSION_DESCRIPTION)],
  ) -> ChartListOutput:
    try:
      values = [dict(id=item.id, definition=model_dict(item.definition)) for item in updates]
      return ChartListOutput.model_validate(store.update_charts(values, expected_incarnation, expected_revision, 'mcp'))
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description='Atomically delete selected managed charts. Deleted IDs are never reused during this process lifetime.',
    annotations=dict(title='Delete managed charts', readOnlyHint=False, destructiveHint=True, openWorldHint=False),
  )
  def delete_charts(
    ids: Annotated[list[int], Field(min_length=1, description='Unique managed chart IDs to delete.')],
    expected_incarnation: Annotated[str, Field(min_length=1, description=VERSION_DESCRIPTION)],
    expected_revision: Annotated[int, Field(ge=0, description=VERSION_DESCRIPTION)],
  ) -> DeleteOutput:
    try:
      return DeleteOutput.model_validate(store.delete_charts(ids, expected_incarnation, expected_revision, 'mcp'))
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  @mcp.tool(
    description='Atomically set managed chart order. ids must contain every current managed ID exactly once.',
    annotations=dict(title='Reorder managed charts', readOnlyHint=False, destructiveHint=False, openWorldHint=False),
  )
  def reorder_charts(
    ids: Annotated[list[int], Field(description='Complete desired managed chart ID order.')],
    expected_incarnation: Annotated[str, Field(min_length=1, description=VERSION_DESCRIPTION)],
    expected_revision: Annotated[int, Field(ge=0, description=VERSION_DESCRIPTION)],
  ) -> ReorderOutput:
    try:
      return ReorderOutput.model_validate(store.reorder_charts(ids, expected_incarnation, expected_revision, 'mcp'))
    except AnalysisError as exc:
      raise ToolError(str(exc)) from exc

  return mcp

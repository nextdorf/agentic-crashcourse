from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import json
import math
import os
from threading import RLock
from typing import Any
from uuid import uuid4
import warnings

import pandas as pd


PREVIEW_LIMIT = 10
CHART_LIMIT = 50
CHART_BATCH_LIMIT = 10
HEATMAP_AXIS_LIMIT = 20
HEATMAP_CELL_LIMIT = 400
MAX_BROWSER_CLIENTS = 100
MAX_INPUT_BYTES = int(os.getenv('TINYBI_MAX_INPUT_BYTES', str(10 * 1024 * 1024)))
ENCODINGS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
AGGREGATIONS = ['sum', 'mean', 'median', 'min', 'max', 'count']
CHART_TYPES = ['auto', 'bar', 'line']
MANAGED_CHART_TYPES = ['bar', 'line', 'scatter', 'heatmap']
SORT_MODES = ['label_asc', 'label_desc', 'value_asc', 'value_desc']
SECTIONS = ['metrics', 'charts', 'insights', 'preview']
DEFAULT_CONTROLS = dict(
  filter_query=None,
  x_column=None,
  y_column=None,
  aggregation='sum',
  chart_type='auto',
  sort_by=None,
  limit=20,
)
DEFAULT_VISIBILITY = dict(
  show_metrics=True,
  show_charts=True,
  show_insights=True,
  show_preview=True,
)


class AnalysisError(ValueError):
  def __init__(self, message: str, status_code: int = 400):
    super().__init__(message)
    self.status_code = status_code


class WorkspaceConflict(AnalysisError):
  def __init__(self, incarnation: str, revision: int):
    super().__init__(
      f'Workspace changed; retry with expected_incarnation={incarnation!r} and expected_revision={revision}.',
      409,
    )
    self.incarnation = incarnation
    self.revision = revision


@dataclass
class Dataset:
  frame: pd.DataFrame
  encoding: str
  dates: list[str]
  measures: list[str]
  dimensions: list[str]
  identifiers: list[str]


class DashboardStore:
  def __init__(self, sample_content: bytes):
    self._lock = RLock()
    self._incarnation = uuid4().hex
    self._sample_content = sample_content
    self._content: bytes | None = None
    self._dataset: Dataset | None = None
    self._dataset_generation = 0
    self._active_source: str | None = None
    self._snapshot: dict[str, Any] | None = None
    self._requested_controls = DEFAULT_CONTROLS.copy()
    self._visibility = DEFAULT_VISIBILITY.copy()
    self._managed_charts: OrderedDict[int, dict[str, Any]] = OrderedDict()
    self._next_chart_id = 1
    self._browser_requests: dict[str, int] = {}
    self._revision = 0
    self._last_updated_by: str | None = None

  def workspace(self):
    with self._lock:
      return deepcopy(self._workspace_unlocked())

  def snapshot(self, after_revision: int | None = None, incarnation: str | None = None):
    with self._lock:
      if incarnation == self._incarnation and after_revision is not None and after_revision >= self._revision:
        return None
      return clean_json(dict(
        changed=True,
        workspace=self._workspace_unlocked(),
        dashboard=self._dashboard_unlocked(),
      ))

  def inspect(self, content: bytes | None = None, source_label: str | None = None):
    if content is not None:
      dataset = parse_csv(content)
      inspected_source = source_label or 'uploaded.csv'
      workspace = self.workspace()
    else:
      with self._lock:
        dataset = self._dataset
        selected = self._content or self._sample_content
        inspected_source = self._active_source or 'sample_data.csv'
        workspace = deepcopy(self._workspace_unlocked())
      dataset = dataset or parse_csv(selected)
    result = inspect_dataset(dataset)
    result['inspected_source'] = safe_source_label(inspected_source)
    result['workspace'] = workspace
    return clean_json(result)

  def analyze(
    self,
    expected_incarnation: str,
    expected_revision: int,
    content: bytes | None = None,
    source_label: str | None = None,
    overrides: dict[str, Any] | None = None,
    sections: list[str] | None = None,
    updated_by: str = 'browser',
    request_client: str | None = None,
    request_sequence: int | None = None,
  ):
    replacement = content is not None
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      self._register_request_unlocked(request_client, request_sequence)
      selected = content if replacement else self._content or self._sample_content
      dataset = None if replacement else self._dataset
      label = source_label if replacement else self._active_source or 'sample_data.csv'
      base_controls = DEFAULT_CONTROLS if replacement else self._requested_controls
      managed = [] if replacement else list(self._managed_charts.values())
    dataset = dataset or parse_csv(selected)
    requested_controls = merge_controls(base_controls, overrides)
    automatic = analyze_dataset(dataset, requested_controls)
    validate_json(automatic)
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      self._check_request_unlocked(request_client, request_sequence)
      if replacement or self._dataset is None:
        self._managed_charts.clear()
        self._dataset_generation += 1
      self._content = selected
      self._dataset = dataset
      self._active_source = safe_source_label(label)
      self._requested_controls = requested_controls
      self._snapshot = clean_json({**automatic, 'charts': automatic['charts'], 'config': self._visibility.copy()})
      self._commit_unlocked(updated_by)
      response = self._dashboard_unlocked()
      workspace = self._workspace_unlocked()
    requested = sections or SECTIONS
    response['returned_sections'] = list(requested)
    for section in SECTIONS:
      if section not in requested:
        response[section] = []
    response['workspace'] = workspace
    return clean_json(response)

  def update_visibility(
    self,
    changes: dict[str, bool],
    expected_incarnation: str,
    expected_revision: int,
    updated_by: str = 'browser',
  ):
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      candidate = {**self._visibility, **changes}
      if candidate == self._visibility:
        return deepcopy(self._workspace_unlocked())
      self._visibility = candidate
      if self._snapshot is not None:
        self._snapshot['config'] = candidate.copy()
      self._commit_unlocked(updated_by)
      return deepcopy(self._workspace_unlocked())

  def list_charts(self, include_data=False):
    with self._lock:
      charts = [managed_entry(entry, include_data) for entry in self._managed_charts.values()]
      return clean_json(dict(workspace=self._workspace_unlocked(), charts=charts))

  def create_charts(
    self,
    definitions: list[dict[str, Any]],
    expected_incarnation: str,
    expected_revision: int,
    content: bytes | None = None,
    source_label: str | None = None,
    updated_by: str = 'mcp',
  ):
    if not 1 <= len(definitions) <= CHART_BATCH_LIMIT:
      raise AnalysisError(f'Create from 1 to {CHART_BATCH_LIMIT} charts in one call.')
    replacement = content is not None
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      selected = content if replacement else self._content or self._sample_content
      dataset = None if replacement else self._dataset
      label = source_label if replacement else self._active_source or 'sample_data.csv'
      needs_dashboard = replacement or self._snapshot is None
    dataset = dataset or parse_csv(selected)
    normalized = [normalize_chart_definition(dataset, definition) for definition in definitions]
    rendered = [render_managed_chart(dataset, definition) for definition in normalized]
    automatic = analyze_dataset(dataset, DEFAULT_CONTROLS) if needs_dashboard else None
    validate_json(dict(rendered=rendered, automatic=automatic))
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      if replacement or self._dataset is None:
        self._managed_charts.clear()
        self._dataset_generation += 1
        self._requested_controls = DEFAULT_CONTROLS.copy()
      if automatic is not None:
        self._snapshot = clean_json({**automatic, 'charts': automatic['charts'], 'config': self._visibility.copy()})
      self._content = selected
      self._dataset = dataset
      self._active_source = safe_source_label(label)
      created = []
      for definition, rendered_chart in zip(normalized, rendered, strict=True):
        chart_id = self._next_chart_id
        self._next_chart_id += 1
        chart = {**rendered_chart['chart'], 'id': chart_id, 'scope': 'managed'}
        entry = dict(
          id=chart_id,
          definition=definition,
          chart=chart,
          table=rendered_chart['table'],
          row_counts=rendered_chart['row_counts'],
        )
        self._managed_charts[chart_id] = entry
        created.append(managed_entry(entry, True))
      self._commit_unlocked(updated_by)
      return clean_json(dict(workspace=self._workspace_unlocked(), charts=created))

  def update_charts(
    self,
    updates: list[dict[str, Any]],
    expected_incarnation: str,
    expected_revision: int,
    updated_by: str = 'mcp',
  ):
    if not 1 <= len(updates) <= CHART_BATCH_LIMIT:
      raise AnalysisError(f'Update from 1 to {CHART_BATCH_LIMIT} charts in one call.')
    ids = [update.get('id') for update in updates]
    if len(ids) != len(set(ids)):
      raise AnalysisError('Each chart ID may appear only once in an update batch.')
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      dataset = self._require_dataset_unlocked()
      self._require_chart_ids_unlocked(ids)
    normalized = [normalize_chart_definition(dataset, update.get('definition') or {}) for update in updates]
    rendered = [render_managed_chart(dataset, definition) for definition in normalized]
    validate_json(rendered)
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      self._require_chart_ids_unlocked(ids)
      changed = False
      result = []
      for chart_id, definition, rendered_chart in zip(ids, normalized, rendered, strict=True):
        candidate = dict(
          id=chart_id,
          definition=definition,
          chart={**rendered_chart['chart'], 'id': chart_id, 'scope': 'managed'},
          table=rendered_chart['table'],
          row_counts=rendered_chart['row_counts'],
        )
        if candidate != self._managed_charts[chart_id]:
          self._managed_charts[chart_id] = candidate
          changed = True
        result.append(managed_entry(self._managed_charts[chart_id], True))
      if changed:
        self._commit_unlocked(updated_by)
      return clean_json(dict(workspace=self._workspace_unlocked(), charts=result))

  def delete_charts(
    self,
    ids: list[int],
    expected_incarnation: str,
    expected_revision: int,
    updated_by: str = 'mcp',
  ):
    if not ids or len(ids) != len(set(ids)):
      raise AnalysisError('Provide one or more unique chart IDs to delete.')
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      self._require_chart_ids_unlocked(ids)
      for chart_id in ids:
        del self._managed_charts[chart_id]
      self._commit_unlocked(updated_by)
      return clean_json(dict(workspace=self._workspace_unlocked(), deleted_ids=ids))

  def reorder_charts(
    self,
    ids: list[int],
    expected_incarnation: str,
    expected_revision: int,
    updated_by: str = 'mcp',
  ):
    with self._lock:
      self._check_version_unlocked(expected_incarnation, expected_revision)
      current = list(self._managed_charts)
      if len(ids) != len(set(ids)) or set(ids) != set(current):
        raise AnalysisError('ids must contain every managed chart ID exactly once.')
      if ids != current:
        self._managed_charts = OrderedDict((chart_id, self._managed_charts[chart_id]) for chart_id in ids)
        self._commit_unlocked(updated_by)
      return clean_json(dict(workspace=self._workspace_unlocked(), ordered_ids=list(self._managed_charts)))

  def _dashboard_unlocked(self):
    if self._snapshot is None:
      return None
    dashboard = deepcopy(self._snapshot)
    dashboard['charts'] = dashboard.get('charts', []) + [deepcopy(entry['chart']) for entry in self._managed_charts.values()]
    dashboard['config'] = self._visibility.copy()
    return dashboard

  def _workspace_unlocked(self):
    return dict(
      incarnation=self._incarnation,
      revision=self._revision,
      last_updated_by=self._last_updated_by,
      active_source=self._active_source,
      dataset_generation=self._dataset_generation,
      visibility=self._visibility.copy(),
      requested_controls=self._requested_controls.copy(),
      managed_chart_ids=list(self._managed_charts),
    )

  def _check_version_unlocked(self, incarnation, revision):
    if incarnation != self._incarnation or revision != self._revision:
      raise WorkspaceConflict(self._incarnation, self._revision)

  def _commit_unlocked(self, updated_by):
    self._revision += 1
    self._last_updated_by = updated_by

  def _require_dataset_unlocked(self):
    if self._dataset is None:
      raise AnalysisError('Analyze or select a dataset before managing charts.')
    return self._dataset

  def _require_chart_ids_unlocked(self, ids):
    unknown = [chart_id for chart_id in ids if chart_id not in self._managed_charts]
    if unknown:
      raise AnalysisError(f'Unknown managed chart IDs: {", ".join(map(str, unknown))}.')

  def _register_request_unlocked(self, client, sequence):
    if client is None:
      return
    if sequence is None or sequence < self._browser_requests.get(client, -1):
      raise AnalysisError('This browser analysis request was superseded by a newer request.', 409)
    if client not in self._browser_requests and len(self._browser_requests) >= MAX_BROWSER_CLIENTS:
      del self._browser_requests[next(iter(self._browser_requests))]
    self._browser_requests[client] = sequence

  def _check_request_unlocked(self, client, sequence):
    if client is not None and self._browser_requests.get(client) != sequence:
      raise AnalysisError('This browser analysis request was superseded by a newer request.', 409)


def merge_controls(base, overrides):
  controls = {**DEFAULT_CONTROLS, **base}
  for key, value in (overrides or {}).items():
    if key == 'filter_query' and value == '':
      controls[key] = None
    elif value == '':
      controls[key] = DEFAULT_CONTROLS.get(key)
    elif value not in [None, '']:
      controls[key] = value
  return controls


def parse_csv(content: bytes) -> Dataset:
  if not content:
    raise AnalysisError('The CSV input is empty.')
  if len(content) > MAX_INPUT_BYTES:
    raise AnalysisError(f'The CSV exceeds the {MAX_INPUT_BYTES / 1024 / 1024:g} MB input limit.', 413)
  last_decode_error = None
  for encoding in ENCODINGS:
    try:
      frame = pd.read_csv(BytesIO(content), encoding=encoding)
      break
    except UnicodeDecodeError as exc:
      last_decode_error = exc
    except pd.errors.EmptyDataError as exc:
      raise AnalysisError('The CSV has no readable rows or columns.') from exc
    except (pd.errors.ParserError, ValueError) as exc:
      raise AnalysisError(f'Could not parse CSV: {str(exc).splitlines()[0]}') from exc
  else:
    raise AnalysisError('Could not decode the CSV as text.') from last_decode_error
  frame = frame.dropna(how='all')
  if frame.empty or not len(frame.columns):
    raise AnalysisError('The CSV must contain at least one non-blank row and one column.')
  frame, dates, measures, dimensions, identifiers = detect_columns(frame)
  return Dataset(frame, encoding, dates, measures, dimensions, identifiers)


def detect_columns(frame: pd.DataFrame):
  frame = frame.copy()
  dates = []
  numeric = []
  identifiers = []
  identifier_tokens = {'id', 'identifier', 'postal', 'postcode', 'zip', 'code', 'sku'}
  for column in frame.columns:
    series = frame[column]
    non_empty = series.dropna()
    if non_empty.empty:
      continue
    name = str(column).lower().strip()
    words = set(name.replace('_', ' ').replace('-', ' ').split())
    if words & identifier_tokens or name.endswith('id'):
      identifiers.append(column)
    likely_date_name = any(token in name for token in ['date', 'time', 'day', 'month'])
    sample = non_empty.astype(str).head(50)
    date_values = sample.str.contains(
      r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', regex=True,
    ).mean() >= 0.7
    if likely_date_name or date_values:
      parsed = pd.to_datetime(series, errors='coerce', format='mixed')
      if parsed.notna().sum() / len(non_empty) >= 0.7:
        frame[column] = parsed
        dates.append(column)
        continue
    parsed_numeric = pd.to_numeric(series, errors='coerce')
    if pd.api.types.is_numeric_dtype(series) or parsed_numeric.notna().sum() / len(non_empty) >= 0.8:
      parsed_numeric = parsed_numeric.replace([float('inf'), float('-inf')], pd.NA)
      frame[column] = parsed_numeric
      numeric.append(column)
  measures = [column for column in numeric if column not in identifiers]
  dimensions = [
    column for column in frame.columns
    if column not in dates and column not in measures and column not in identifiers
  ]
  return frame, dates, measures, dimensions, identifiers


def inspect_bytes(content: bytes):
  return inspect_dataset(parse_csv(content))


def inspect_dataset(dataset: Dataset):
  frame = dataset.frame
  category_summaries = {}
  for column in dataset.dimensions[:5]:
    category_summaries[column] = {
      str(key): int(value) for key, value in frame[column].dropna().astype(str).value_counts().head(5).items()
    }
  date_ranges = {}
  for column in dataset.dates:
    values = frame[column].dropna()
    if not values.empty:
      date_ranges[column] = dict(min=values.min().date().isoformat(), max=values.max().date().isoformat())
  return clean_json(dict(
    metadata=dataset_metadata(dataset),
    missing_values={str(key): int(value) for key, value in frame.isna().sum().items()},
    date_ranges=date_ranges,
    category_summaries=category_summaries,
    filter_examples=filter_examples(dataset),
    valid_options=valid_options(dataset),
  ))


def analyze_bytes(content: bytes, controls: dict[str, Any] | None = None):
  return analyze_dataset(parse_csv(content), merge_controls(DEFAULT_CONTROLS, controls))


def analyze_dataset(dataset: Dataset, controls: dict[str, Any]):
  validate_controls(dataset, controls)
  frame = apply_filter(dataset.frame, controls.get('filter_query'), dataset)
  measure = controls.get('y_column') or primary_measure(dataset.measures)
  x_column = controls.get('x_column')
  date_column = x_column if x_column in dataset.dates else first(dataset.dates)
  dimension = x_column if x_column in dataset.dimensions + dataset.identifiers else first(dataset.dimensions)
  effective = effective_controls(dataset, controls, measure, date_column, dimension)
  with warnings.catch_warnings():
    warnings.simplefilter('ignore', RuntimeWarning)
    result = dict(
      metadata={**dataset_metadata(dataset), 'row_count_before_filter': len(dataset.frame), 'row_count_after_filter': len(frame)},
      requested_config=controls.copy(),
      effective_config=effective,
      defaults=effective,
      columns=dict(
        all=list(frame.columns), dates=dataset.dates, measures=dataset.measures,
        dimensions=dataset.dimensions, identifiers=dataset.identifiers,
        numeric=dataset.measures, categorical=dataset.dimensions, date=dataset.dates,
        primary_numeric=measure, primary_date=date_column, primary_category=dimension,
      ),
      metrics=build_metrics(frame, dataset, measure, date_column, dimension),
      charts=build_charts(frame, dataset, effective, measure, date_column, dimension),
      insights=build_insights(frame, measure, date_column, dimension, len(dataset.frame)),
      preview=preview_records(frame),
      filter_examples=filter_examples(dataset),
    )
  return clean_json(result)


def create_chart_bytes(content: bytes, controls: dict[str, Any]):
  dataset = parse_csv(content)
  chart_type = controls.get('chart_type') if controls.get('chart_type') not in [None, 'auto'] else (
    'line' if controls.get('x_column') in dataset.dates else 'bar'
  )
  definition = dict(
    type=chart_type,
    title=controls.get('title'),
    x_column=controls.get('x_column'),
    y_column=controls.get('y_column'),
    filter_query=controls.get('filter_query'),
    limit=controls.get('limit'),
  )
  if chart_type in ['bar', 'line']:
    definition.update(aggregation=controls.get('aggregation'), sort_by=controls.get('sort_by'))
  definition = normalize_chart_definition(dataset, definition)
  chart = render_managed_chart(dataset, definition)
  return clean_json(dict(
    effective_config=definition,
    row_counts=chart['row_counts'],
    chart=chart['chart'],
    table=chart['table'],
  ))


def validate_controls(dataset: Dataset, controls: dict[str, Any]):
  x_column = controls.get('x_column')
  y_column = controls.get('y_column')
  if x_column and x_column not in dataset.frame.columns:
    raise AnalysisError(f'Invalid x_column {x_column!r}. Valid choices: {", ".join(map(str, dataset.frame.columns))}.')
  if y_column and y_column not in dataset.measures:
    raise AnalysisError(f'Invalid y_column {y_column!r}. Valid measures: {", ".join(map(str, dataset.measures)) or "none"}.')
  for name, choices in [('aggregation', AGGREGATIONS), ('chart_type', CHART_TYPES), ('sort_by', SORT_MODES)]:
    value = controls.get(name)
    if value not in [None, ''] and value not in choices:
      raise AnalysisError(f'Invalid {name} {value!r}. Valid choices: {", ".join(choices)}.')
  validate_limit(controls.get('limit'), 'limit', CHART_LIMIT)


def normalize_chart_definition(dataset: Dataset, definition: dict[str, Any]):
  chart_type = definition.get('type')
  if chart_type not in MANAGED_CHART_TYPES:
    raise AnalysisError(f'Invalid chart type {chart_type!r}. Valid choices: {", ".join(MANAGED_CHART_TYPES)}.')
  common_keys = {'type', 'title', 'x_column', 'y_column', 'filter_query'}
  type_keys = {
    'bar': {'aggregation', 'sort_by', 'limit'},
    'line': {'aggregation', 'sort_by', 'limit'},
    'scatter': {'limit'},
    'heatmap': {'value_column', 'aggregation', 'x_limit', 'y_limit'},
  }
  unknown = set(definition) - common_keys - type_keys[chart_type]
  if unknown:
    raise AnalysisError(f'Unexpected fields for {chart_type}: {", ".join(sorted(unknown))}.')
  common = dict(
    type=chart_type,
    title=definition.get('title') or None,
    x_column=definition.get('x_column'),
    y_column=definition.get('y_column'),
    filter_query=definition.get('filter_query') or None,
  )
  if chart_type in ['bar', 'line']:
    require_column(dataset, common['x_column'], list(dataset.frame.columns), 'x_column')
    require_column(dataset, common['y_column'], dataset.measures, 'y_column')
    aggregation = definition.get('aggregation') or 'sum'
    sort_by = definition.get('sort_by') or ('label_asc' if common['x_column'] in dataset.dates else 'value_desc')
    if aggregation not in AGGREGATIONS:
      raise AnalysisError(f'Invalid aggregation {aggregation!r}.')
    if sort_by not in SORT_MODES:
      raise AnalysisError(f'Invalid sort_by {sort_by!r}.')
    limit = validate_limit(definition.get('limit') or 20, 'limit', CHART_LIMIT)
    return {**common, 'aggregation': aggregation, 'sort_by': sort_by, 'limit': limit}
  if chart_type == 'scatter':
    require_column(dataset, common['x_column'], dataset.measures, 'x_column')
    require_column(dataset, common['y_column'], dataset.measures, 'y_column')
    return {**common, 'limit': validate_limit(definition.get('limit') or 50, 'limit', CHART_LIMIT)}
  grouping = dataset.dimensions + dataset.dates + dataset.identifiers
  require_column(dataset, common['x_column'], grouping, 'x_column')
  require_column(dataset, common['y_column'], grouping, 'y_column')
  value_column = definition.get('value_column')
  require_column(dataset, value_column, dataset.measures, 'value_column')
  aggregation = definition.get('aggregation') or 'sum'
  if aggregation not in AGGREGATIONS:
    raise AnalysisError(f'Invalid aggregation {aggregation!r}.')
  x_limit = validate_limit(definition.get('x_limit') or 10, 'x_limit', HEATMAP_AXIS_LIMIT)
  y_limit = validate_limit(definition.get('y_limit') or 10, 'y_limit', HEATMAP_AXIS_LIMIT)
  if x_limit * y_limit > HEATMAP_CELL_LIMIT:
    raise AnalysisError(f'Heatmap axis limits may produce at most {HEATMAP_CELL_LIMIT} cells.')
  return {
    **common,
    'value_column': value_column,
    'aggregation': aggregation,
    'x_limit': x_limit,
    'y_limit': y_limit,
  }


def render_managed_chart(dataset: Dataset, definition: dict[str, Any]):
  frame = apply_filter(dataset.frame, definition.get('filter_query'), dataset)
  chart_type = definition['type']
  if chart_type in ['bar', 'line']:
    return render_grouped_chart(frame, dataset, definition)
  if chart_type == 'scatter':
    return render_scatter_chart(frame, definition)
  return render_heatmap_chart(frame, dataset, definition)


def render_grouped_chart(frame, dataset, definition):
  x_column = definition['x_column']
  y_column = definition['y_column']
  data = frame.dropna(subset=[x_column]).groupby(x_column, dropna=True)[y_column].agg(definition['aggregation']).reset_index()
  data[y_column] = finite_series(data[y_column])
  data = data.dropna(subset=[y_column])
  data = sort_data(data, x_column, y_column, definition['sort_by']).head(definition['limit'])
  title = definition['title'] or f'{definition["aggregation"].title()} of {y_column} by {x_column}'
  chart = chart_payload(None, title, definition['type'], data, x_column, y_column, x_column in dataset.dates)
  return dict(
    chart={**chart, 'scope': 'managed'},
    table=preview_records(data, CHART_LIMIT),
    row_counts=dict(before_filter=len(dataset.frame), after_filter=len(frame)),
  )


def render_scatter_chart(frame, definition):
  x_column = definition['x_column']
  y_column = definition['y_column']
  data = frame[[x_column, y_column]].dropna().head(definition['limit'])
  points = [dict(x=clean_json(row[x_column]), y=clean_json(row[y_column])) for _, row in data.iterrows()]
  title = definition['title'] or f'{y_column} versus {x_column}'
  return dict(
    chart=dict(id=None, scope='managed', title=title, type='scatter', x_column=x_column, y_column=y_column, points=points),
    table=points,
    row_counts=dict(before_filter=len(frame), after_filter=len(frame)),
  )


def render_heatmap_chart(frame, dataset, definition):
  x_column = definition['x_column']
  y_column = definition['y_column']
  value_column = definition['value_column']
  data = frame.dropna(subset=[x_column, y_column]).groupby(
    [x_column, y_column], dropna=True,
  )[value_column].agg(definition['aggregation']).reset_index()
  data[value_column] = finite_series(data[value_column])
  data = data.dropna(subset=[value_column])
  x_values = ranked_groups(data, x_column, value_column, definition['x_limit'])
  y_values = ranked_groups(data, y_column, value_column, definition['y_limit'])
  data = data[data[x_column].isin(x_values) & data[y_column].isin(y_values)].copy()
  x_order = {value: index for index, value in enumerate(x_values)}
  y_order = {value: index for index, value in enumerate(y_values)}
  data['_x_order'] = data[x_column].map(x_order)
  data['_y_order'] = data[y_column].map(y_order)
  data = data.sort_values(['_y_order', '_x_order'])
  cells = [
    dict(x=display_label(row[x_column], x_column in dataset.dates), y=display_label(row[y_column], y_column in dataset.dates), value=clean_json(row[value_column]))
    for _, row in data.iterrows()
  ]
  title = definition['title'] or f'{definition["aggregation"].title()} of {value_column} by {x_column} and {y_column}'
  chart = dict(
    id=None,
    scope='managed',
    title=title,
    type='heatmap',
    x_column=x_column,
    y_column=y_column,
    value_column=value_column,
    x_labels=[display_label(value, x_column in dataset.dates) for value in x_values],
    y_labels=[display_label(value, y_column in dataset.dates) for value in y_values],
    cells=cells,
  )
  return dict(
    chart=chart,
    table=cells[:HEATMAP_CELL_LIMIT],
    row_counts=dict(before_filter=len(dataset.frame), after_filter=len(frame)),
  )


def managed_entry(entry, include_data):
  result = dict(id=entry['id'], title=entry['chart']['title'], definition=deepcopy(entry['definition']))
  if include_data:
    result['chart'] = deepcopy(entry['chart'])
  return result


def apply_filter(frame, query, dataset):
  if not query:
    return frame.copy()
  try:
    filtered = frame.query(str(query))
  except Exception as exc:
    example = first(filter_examples(dataset)) or "Revenue > 100 and Region == 'West'"
    raise AnalysisError(
      f'Invalid filter_query {query!r}. Use case-sensitive pandas query syntax and backticks around spaced names, '
      f'for example: {example}.'
    ) from exc
  if filtered.empty:
    raise AnalysisError(f'filter_query {query!r} removed all rows; change or clear the filter.')
  return filtered.copy()


def dataset_metadata(dataset):
  return dict(
    encoding=dataset.encoding, row_count=len(dataset.frame), column_count=len(dataset.frame.columns),
    dates=dataset.dates, measures=dataset.measures, dimensions=dataset.dimensions, identifiers=dataset.identifiers,
  )


def valid_options(dataset):
  return dict(
    x_columns=list(dataset.frame.columns),
    y_columns=dataset.measures,
    grouping_columns=dataset.dimensions + dataset.dates + dataset.identifiers,
    aggregations=AGGREGATIONS,
    automatic_chart_types=CHART_TYPES,
    managed_chart_types=MANAGED_CHART_TYPES,
    sort_modes=SORT_MODES,
    limit_bounds=dict(minimum=1, maximum=CHART_LIMIT),
    heatmap_axis_limit=HEATMAP_AXIS_LIMIT,
    heatmap_cell_limit=HEATMAP_CELL_LIMIT,
  )


def filter_examples(dataset):
  examples = []
  if dataset.dimensions:
    column = dataset.dimensions[0]
    values = dataset.frame[column].dropna()
    if not values.empty:
      escaped = str(values.iloc[0]).replace("'", "\\'")
      examples.append(f'{quote_column(column)} == \'{escaped}\'')
  if dataset.measures:
    column = dataset.measures[0]
    values = dataset.frame[column].dropna()
    if not values.empty:
      median = float(values.median())
      if math.isfinite(median):
        examples.append(f'{quote_column(column)} >= {median:g}')
  return examples[:2]


def quote_column(column):
  text = str(column)
  return f'`{text}`' if not text.isidentifier() else text


def primary_measure(columns):
  for token in ['sales', 'revenue', 'profit', 'amount', 'price', 'cost', 'quantity', 'users', 'count']:
    for column in columns:
      if token in str(column).lower():
        return column
  return first(columns)


def effective_controls(dataset, controls, measure, date_column, dimension):
  x_column = controls.get('x_column') or date_column or dimension or first(dataset.identifiers)
  requested_type = controls.get('chart_type') or 'auto'
  resolved_type = 'line' if requested_type == 'auto' and x_column in dataset.dates else 'bar' if requested_type == 'auto' else requested_type
  return dict(
    filter_query=controls.get('filter_query') or None,
    x_column=x_column,
    y_column=measure,
    aggregation=controls.get('aggregation') or 'sum',
    chart_type=resolved_type,
    sort_by=controls.get('sort_by') or ('label_asc' if x_column in dataset.dates else 'value_desc'),
    limit=int(controls.get('limit') or 20),
  )


def build_metrics(frame, dataset, measure, date_column, dimension):
  metrics = [
    metric('Rows after filtering', len(frame), 'Rows used in this analysis'),
    metric('Total columns', len(frame.columns), 'Columns detected in the CSV'),
    metric('Measures', len(dataset.measures), ', '.join(map(str, dataset.measures)) or 'None found'),
    metric('Dimensions', len(dataset.dimensions), ', '.join(map(str, dataset.dimensions[:5])) or 'None found'),
  ]
  numeric = frame[measure].dropna() if measure else pd.Series(dtype='float64')
  if measure and not numeric.empty:
    metrics.extend([
      metric(f'Total {measure}', numeric.sum(), f'Sum of {measure}'),
      metric(f'Average {measure}', numeric.mean(), f'Mean value for {measure}'),
      metric(f'Min {measure}', numeric.min(), f'Lowest {measure} value'),
      metric(f'Max {measure}', numeric.max(), f'Highest {measure} value'),
    ])
  if measure and dimension:
    grouped = finite_series(frame.groupby(dimension, dropna=True)[measure].sum()).dropna().sort_values(ascending=False)
    if not grouped.empty:
      metrics.append(metric('Best category', str(grouped.index[0]), f'Highest total {measure}'))
  if measure and date_column:
    grouped = finite_series(frame.dropna(subset=[date_column]).groupby(date_column)[measure].sum()).dropna().sort_values(ascending=False)
    if not grouped.empty:
      metrics.append(metric('Best date', grouped.index[0].date().isoformat(), f'Highest total {measure}'))
  return metrics


def build_charts(frame, dataset, controls, measure, date_column, dimension):
  charts = []
  aggregation = controls['aggregation']
  limit = controls['limit']
  if measure and date_column:
    data = frame.dropna(subset=[date_column]).groupby(date_column)[measure].agg(aggregation).reset_index()
    data[measure] = finite_series(data[measure])
    data = data.dropna(subset=[measure]).sort_values(date_column).tail(limit)
    charts.append(chart_payload('time', f'{measure} over time', 'line', data, date_column, measure, True))
  if measure and dimension:
    data = frame.groupby(dimension, dropna=True)[measure].agg(aggregation).reset_index()
    data[measure] = finite_series(data[measure])
    data = sort_data(data.dropna(subset=[measure]), dimension, measure, controls['sort_by']).head(limit)
    charts.append(chart_payload('category', f'{measure} by {dimension}', 'bar', data, dimension, measure))
  if measure:
    numeric = frame[measure].dropna()
    if not numeric.empty:
      bins = min(10, max(3, int(numeric.nunique())))
      if numeric.nunique() == 1:
        charts.append(dict(
          id='distribution', scope='automatic', title=f'{measure} distribution', type='bar',
          labels=[format_number(numeric.iloc[0])], values=[len(numeric)],
        ))
        histogram = None
      else:
        value_range = float(numeric.max()) - float(numeric.min())
        histogram = False if math.isfinite(value_range) else None
      if histogram is False:
        try:
          candidate = pd.cut(numeric, bins=bins, duplicates='drop').value_counts().sort_index()
          boundaries = [boundary for interval in candidate.index for boundary in [interval.left, interval.right]]
          histogram = candidate if all(math.isfinite(float(boundary)) for boundary in boundaries) else None
        except (OverflowError, ValueError):
          histogram = None
      if histogram is not None:
        charts.append(dict(
          id='distribution', scope='automatic', title=f'{measure} distribution', type='bar',
          labels=[f'{interval.left:.2f} to {interval.right:.2f}' for interval in histogram.index],
          values=histogram.tolist(),
        ))
  return charts


def chart_payload(identifier, title, chart_type, data, x_column, y_column, is_date=False):
  labels = [display_label(value, True) for value in data[x_column]] if is_date else data[x_column].astype(str).tolist()
  return dict(
    id=identifier, scope='automatic' if identifier is not None else 'managed', title=title,
    type=chart_type, labels=labels, values=clean_json(data[y_column].tolist()),
  )


def sort_data(data, label_column, value_column, sort_by):
  if sort_by == 'label_asc':
    return data.sort_values(label_column)
  if sort_by == 'label_desc':
    return data.sort_values(label_column, ascending=False)
  if sort_by == 'value_asc':
    return data.sort_values(value_column)
  return data.sort_values(value_column, ascending=False)


def build_insights(frame, measure, date_column, dimension, before):
  insights = [f'The analysis uses {len(frame):,} of {before:,} rows across {len(frame.columns):,} columns.']
  if measure:
    numeric = frame[measure].dropna()
    if not numeric.empty:
      insights.append(f'{measure} ranges from {format_number(numeric.min())} to {format_number(numeric.max())}.')
      mean = numeric.mean()
      median = numeric.median()
      if math.isfinite(float(mean)) and math.isfinite(float(median)):
        if abs(float(mean) - float(median)) <= max(1e-9, abs(float(mean)) * 1e-9):
          relation = 'equal to'
        else:
          relation = 'above' if median > mean else 'below'
        insights.append(f'The median {measure} is {relation} the average.')
  if measure and dimension:
    grouped = finite_series(frame.groupby(dimension, dropna=True)[measure].sum()).dropna().sort_values(ascending=False)
    if len(grouped) >= 2:
      insights.append(f'{grouped.index[0]} has the highest observed total {measure} by {dimension}.')
  if measure and date_column:
    grouped = finite_series(frame.dropna(subset=[date_column]).groupby(date_column)[measure].sum()).dropna().sort_index()
    if len(grouped) >= 2:
      direction = 'higher' if grouped.iloc[-1] > grouped.iloc[0] else 'lower' if grouped.iloc[-1] < grouped.iloc[0] else 'equal to'
      insights.append(f'The latest date aggregate for {measure} is {direction} the earliest date aggregate.')
  insights.append('Metrics and charts ignore missing values where aggregation requires a value.')
  return insights[:5]


def preview_records(frame, limit=PREVIEW_LIMIT):
  preview = frame.head(limit).copy()
  for column in preview.columns:
    if pd.api.types.is_datetime64_any_dtype(preview[column]):
      preview[column] = preview[column].dt.strftime('%Y-%m-%d')
    preview[column] = preview[column].astype(object).where(preview[column].notna(), None)
  return clean_json(preview.to_dict(orient='records'))


def metric(label, value, hint):
  return dict(label=label, value=clean_json(value), display_value=format_number(value), hint=hint)


def format_number(value):
  if isinstance(value, str):
    return value
  if pd.isna(value) or not math.isfinite(float(value)):
    return 'n/a'
  if float(value).is_integer():
    return f'{int(value):,}'
  return f'{float(value):,.2f}'


def clean_json(value):
  if isinstance(value, dict):
    return {str(key): clean_json(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [clean_json(item) for item in value]
  if isinstance(value, pd.Timestamp):
    return value.isoformat()
  if hasattr(value, 'item'):
    value = value.item()
  if isinstance(value, float) and not math.isfinite(value):
    return None
  if not isinstance(value, (str, bytes, dict, list)):
    try:
      if pd.isna(value):
        return None
    except (TypeError, ValueError):
      pass
  return value


def validate_json(value):
  try:
    json.dumps(clean_json(value), allow_nan=False)
  except (TypeError, ValueError) as exc:
    raise AnalysisError('Analysis produced a value that cannot be represented as strict JSON.') from exc


def finite_series(series):
  return series.replace([float('inf'), float('-inf')], pd.NA)


def ranked_groups(data, column, value_column, limit):
  ranked = data.groupby(column, dropna=True)[value_column].sum().reset_index()
  ranked['_label'] = ranked[column].astype(str)
  ranked = ranked.sort_values([value_column, '_label'], ascending=[False, True])
  return ranked[column].head(limit).tolist()


def display_label(value, is_date=False):
  if is_date and hasattr(value, 'isoformat'):
    if all(getattr(value, name, 0) == 0 for name in ['hour', 'minute', 'second', 'microsecond']):
      return value.date().isoformat()
    return value.isoformat()
  return str(value)


def require_column(dataset, value, choices, name):
  if not value:
    raise AnalysisError(f'{name} is required.')
  if value not in choices:
    raise AnalysisError(f'Invalid {name} {value!r}. Valid choices: {", ".join(map(str, choices)) or "none"}.')


def validate_limit(value, name, maximum):
  try:
    limit = int(value)
  except (TypeError, ValueError) as exc:
    raise AnalysisError(f'{name} must be an integer from 1 to {maximum}.') from exc
  if not 1 <= limit <= maximum:
    raise AnalysisError(f'Invalid {name} {limit!r}; use a value from 1 to {maximum}.')
  return limit


def safe_source_label(label):
  if not label:
    return None
  if label.startswith('inline'):
    return 'inline CSV'
  return os.path.basename(label)


def first(items):
  return items[0] if items else None

from dataclasses import dataclass
from io import BytesIO
import os
from threading import RLock
from typing import Any

import pandas as pd


PREVIEW_LIMIT = 10
CHART_LIMIT = 50
MAX_INPUT_BYTES = int(os.getenv('TINYBI_MAX_INPUT_BYTES', str(10 * 1024 * 1024)))
ENCODINGS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
AGGREGATIONS = ['sum', 'mean', 'median', 'min', 'max', 'count']
CHART_TYPES = ['auto', 'bar', 'line']
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
    self._sample_content = sample_content
    self._content: bytes | None = None
    self._dataset: Dataset | None = None
    self._active_source: str | None = None
    self._snapshot: dict[str, Any] | None = None
    self._controls = DEFAULT_CONTROLS.copy()
    self._visibility = DEFAULT_VISIBILITY.copy()
    self._revision = 0
    self._last_updated_by: str | None = None

  def workspace(self):
    with self._lock:
      return clean_json(self._workspace_unlocked())

  def snapshot(self, after_revision: int | None = None):
    with self._lock:
      if after_revision is not None and after_revision >= self._revision:
        return None
      if self._snapshot is None:
        return dict(changed=True, workspace=self._workspace_unlocked(), dashboard=None)
      return dict(changed=True, workspace=self._workspace_unlocked(), dashboard=self._snapshot.copy())

  def inspect(self, content: bytes | None = None, source_label: str | None = None):
    with self._lock:
      selected = content if content is not None else self._content or self._sample_content
      inspected_source = source_label if content is not None else self._active_source or 'sample_data.csv'
      result = inspect_bytes(selected)
      result['inspected_source'] = inspected_source
      result['workspace'] = self._workspace_unlocked()
      return clean_json(result)

  def analyze(
    self,
    content: bytes | None = None,
    source_label: str | None = None,
    overrides: dict[str, Any] | None = None,
    sections: list[str] | None = None,
    updated_by: str = 'browser',
  ):
    with self._lock:
      selected = content if content is not None else self._content or self._sample_content
      label = source_label if content is not None else self._active_source or 'sample_data.csv'
      controls = self._merged_controls(overrides, content is not None)
      result = analyze_bytes(selected, controls)
      self._commit(selected, label, result['effective_config'], result, updated_by)
      requested = sections or SECTIONS
      response = result.copy()
      response['config'] = self._visibility.copy()
      response['returned_sections'] = list(requested)
      for section in SECTIONS:
        if section not in requested:
          response[section] = []
      response['workspace'] = self._workspace_unlocked()
      return clean_json(response)

  def create_chart(
    self,
    controls: dict[str, Any],
    content: bytes | None = None,
    source_label: str | None = None,
    updated_by: str = 'mcp',
  ):
    with self._lock:
      selected = content if content is not None else self._content or self._sample_content
      label = source_label if content is not None else self._active_source or 'sample_data.csv'
      merged = self._merged_controls(controls)
      focused = create_chart_bytes(selected, merged)
      dashboard = analyze_bytes(selected, merged)
      dashboard['charts'] = [focused['chart']]
      self._commit(selected, label, focused['effective_config'], dashboard, updated_by)
      focused['workspace'] = self._workspace_unlocked()
      return clean_json(focused)

  def update_visibility(self, changes: dict[str, bool], updated_by: str = 'browser'):
    with self._lock:
      candidate = self._visibility.copy()
      candidate.update(changes)
      self._visibility = candidate
      if self._snapshot is not None:
        self._snapshot['config'] = candidate.copy()
      self._revision += 1
      self._last_updated_by = updated_by
      return self._workspace_unlocked()

  def _merged_controls(self, overrides, new_dataset=False):
    controls = self._controls.copy()
    if new_dataset:
      controls['x_column'] = None
      controls['y_column'] = None
    for key, value in (overrides or {}).items():
      if value is not None:
        controls[key] = value
    return controls

  def _commit(self, content, label, controls, result, updated_by):
    dataset = parse_csv(content)
    self._content = content
    self._dataset = dataset
    self._active_source = safe_source_label(label)
    self._controls = {**DEFAULT_CONTROLS, **controls}
    self._snapshot = clean_json({**result, 'config': self._visibility.copy()})
    self._revision += 1
    self._last_updated_by = updated_by

  def _workspace_unlocked(self):
    return dict(
      revision=self._revision,
      last_updated_by=self._last_updated_by,
      active_source=self._active_source,
      visibility=self._visibility.copy(),
      controls=self._controls.copy(),
    )


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
      frame[column] = parsed_numeric
      numeric.append(column)
  measures = [column for column in numeric if column not in identifiers]
  dimensions = [
    column for column in frame.columns
    if column not in dates and column not in measures and column not in identifiers
  ]
  return frame, dates, measures, dimensions, identifiers


def inspect_bytes(content: bytes):
  dataset = parse_csv(content)
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
  dataset = parse_csv(content)
  controls = controls or DEFAULT_CONTROLS.copy()
  validate_controls(dataset, controls)
  frame = apply_filter(dataset.frame, controls.get('filter_query'), dataset)
  measure = controls.get('y_column') or primary_measure(dataset.measures)
  x_column = controls.get('x_column')
  date_column = x_column if x_column in dataset.dates else first(dataset.dates)
  dimension = x_column if x_column in dataset.dimensions + dataset.identifiers else first(dataset.dimensions)
  effective = effective_controls(dataset, controls, measure, date_column, dimension)
  result = dict(
    metadata={**dataset_metadata(dataset), 'row_count_before_filter': len(dataset.frame), 'row_count_after_filter': len(frame)},
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
  validate_controls(dataset, controls, require_chart=True)
  frame = apply_filter(dataset.frame, controls.get('filter_query'), dataset)
  chart, table, effective = custom_chart(frame, dataset, controls)
  return clean_json(dict(
    effective_config=effective,
    row_counts=dict(before_filter=len(dataset.frame), after_filter=len(frame)),
    chart=chart,
    table=table,
  ))


def validate_controls(dataset: Dataset, controls: dict[str, Any], require_chart=False):
  x_column = controls.get('x_column')
  y_column = controls.get('y_column')
  if require_chart and not x_column:
    raise AnalysisError(f'x_column is required. Valid choices: {", ".join(map(str, dataset.frame.columns))}.')
  if require_chart and not y_column:
    raise AnalysisError(f'y_column is required. Valid measures: {", ".join(map(str, dataset.measures)) or "none"}.')
  if x_column and x_column not in dataset.frame.columns:
    raise AnalysisError(f'Invalid x_column {x_column!r}. Valid choices: {", ".join(map(str, dataset.frame.columns))}.')
  if y_column and y_column not in dataset.measures:
    raise AnalysisError(f'Invalid y_column {y_column!r}. Valid measures: {", ".join(map(str, dataset.measures)) or "none"}.')
  for name, choices in [('aggregation', AGGREGATIONS), ('chart_type', CHART_TYPES), ('sort_by', SORT_MODES)]:
    value = controls.get(name)
    if value not in [None, ''] and value not in choices:
      raise AnalysisError(f'Invalid {name} {value!r}. Valid choices: {", ".join(choices)}.')
  if controls.get('limit') not in [None, '']:
    try:
      limit = int(controls['limit'])
    except (TypeError, ValueError) as exc:
      raise AnalysisError(f'limit must be an integer from 1 to {CHART_LIMIT}.') from exc
    if not 1 <= limit <= CHART_LIMIT:
      raise AnalysisError(f'Invalid limit {limit!r}; use a value from 1 to {CHART_LIMIT}.')


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
    x_columns=list(dataset.frame.columns), y_columns=dataset.measures, aggregations=AGGREGATIONS,
    chart_types=CHART_TYPES, sort_modes=SORT_MODES, limit_bounds=dict(minimum=1, maximum=CHART_LIMIT),
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
      examples.append(f'{quote_column(column)} >= {float(values.median()):g}')
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
  chart_type = controls.get('chart_type') or 'auto'
  resolved_type = 'line' if x_column in dataset.dates else 'bar' if chart_type == 'auto' else chart_type
  if chart_type != 'auto':
    resolved_type = chart_type
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
    grouped = frame.groupby(dimension, dropna=True)[measure].sum().sort_values(ascending=False)
    if not grouped.empty:
      metrics.append(metric('Best category', str(grouped.index[0]), f'Highest total {measure}'))
  if measure and date_column:
    grouped = frame.dropna(subset=[date_column]).groupby(date_column)[measure].sum().sort_values(ascending=False)
    if not grouped.empty:
      metrics.append(metric('Best date', grouped.index[0].date().isoformat(), f'Highest total {measure}'))
  return metrics


def build_charts(frame, dataset, controls, measure, date_column, dimension):
  charts = []
  aggregation = controls['aggregation']
  limit = controls['limit']
  if measure and date_column:
    data = frame.dropna(subset=[date_column]).groupby(date_column)[measure].agg(aggregation).reset_index()
    data = data.sort_values(date_column).tail(limit)
    charts.append(chart_payload('time', f'{measure} over time', 'line', data, date_column, measure, True))
  if measure and dimension:
    data = frame.groupby(dimension, dropna=True)[measure].agg(aggregation).reset_index()
    data = sort_data(data, dimension, measure, controls['sort_by']).head(limit)
    charts.append(chart_payload('category', f'{measure} by {dimension}', 'bar', data, dimension, measure))
  if measure:
    numeric = frame[measure].dropna()
    if not numeric.empty:
      bins = min(10, max(3, int(numeric.nunique())))
      histogram = pd.cut(numeric, bins=bins, duplicates='drop').value_counts().sort_index()
      charts.append(dict(
        id='distribution', title=f'{measure} distribution', type='bar',
        labels=[f'{interval.left:.2f} to {interval.right:.2f}' for interval in histogram.index],
        values=histogram.tolist(),
      ))
  if controls.get('x_column') and controls.get('y_column'):
    custom, _, _ = custom_chart(frame, dataset, controls)
    charts.insert(0, custom)
  return charts


def custom_chart(frame, dataset, controls):
  x_column = controls['x_column']
  y_column = controls['y_column']
  aggregation = controls.get('aggregation') or 'sum'
  limit = int(controls.get('limit') or 20)
  is_date = x_column in dataset.dates
  sort_by = controls.get('sort_by') or ('label_asc' if is_date else 'value_desc')
  chart_type = controls.get('chart_type') or 'auto'
  if chart_type == 'auto':
    chart_type = 'line' if is_date else 'bar'
  data = frame.dropna(subset=[x_column]).groupby(x_column)[y_column].agg(aggregation).reset_index()
  data = sort_data(data, x_column, y_column, sort_by).head(limit)
  chart = chart_payload(
    'custom', f'{aggregation.title()} of {y_column} by {x_column}', chart_type,
    data, x_column, y_column, is_date,
  )
  effective = dict(
    filter_query=controls.get('filter_query') or None, x_column=x_column, y_column=y_column,
    aggregation=aggregation, chart_type=chart_type, sort_by=sort_by, limit=limit,
  )
  return chart, preview_records(data, CHART_LIMIT), effective


def chart_payload(identifier, title, chart_type, data, x_column, y_column, is_date=False):
  labels = [value.date().isoformat() for value in data[x_column]] if is_date else data[x_column].astype(str).tolist()
  return dict(id=identifier, title=title, type=chart_type, labels=labels, values=data[y_column].tolist())


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
      if abs(float(mean) - float(median)) <= max(1e-9, abs(float(mean)) * 1e-9):
        relation = 'equal to'
      else:
        relation = 'above' if median > mean else 'below'
      insights.append(f'The median {measure} is {relation} the average.')
  if measure and dimension:
    grouped = frame.groupby(dimension, dropna=True)[measure].sum().sort_values(ascending=False)
    if len(grouped) >= 2:
      insights.append(f'{grouped.index[0]} has the highest observed total {measure} by {dimension}.')
  if measure and date_column:
    grouped = frame.dropna(subset=[date_column]).groupby(date_column)[measure].sum().sort_index()
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
  return preview.to_dict(orient='records')


def metric(label, value, hint):
  native = clean_json(value)
  return dict(label=label, value=native, display_value=format_number(value), hint=hint)


def format_number(value):
  if isinstance(value, str):
    return value
  if pd.isna(value):
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
  if not isinstance(value, (str, bytes, dict, list)):
    try:
      if pd.isna(value):
        return None
    except (TypeError, ValueError):
      pass
  return value


def safe_source_label(label):
  if not label:
    return None
  if label.startswith('inline'):
    return 'inline CSV'
  return os.path.basename(label)


def first(items):
  return items[0] if items else None

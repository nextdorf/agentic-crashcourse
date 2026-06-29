from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.datastructures import UploadFile


APP_NAME = 'TinyBI'
BASE_DIR = Path(__file__).resolve().parent
PREVIEW_LIMIT = 10
CHART_LIMIT = 50

app = FastAPI(title=APP_NAME)
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')

dashboard_config = dict(
  show_metrics=True,
  show_charts=True,
  show_preview=True,
  show_insights=True,
)


class ConfigUpdate(BaseModel):
  show_metrics: bool | None = None
  show_charts: bool | None = None
  show_preview: bool | None = None
  show_insights: bool | None = None


@app.get('/')
async def index(request: Request):
  return templates.TemplateResponse(
    request,
    'index.html',
    dict(app_name=APP_NAME, config=dashboard_config),
  )


@app.post('/config')
async def update_config(update: ConfigUpdate):
  for key, value in update.model_dump(exclude_none=True).items():
    dashboard_config[key] = value
  return dict(config=dashboard_config)


@app.get('/sample-data')
async def sample_data(request: Request):
  sample_path = BASE_DIR / 'sample_data.csv'
  if request.query_params.get('download') == 'true':
    return FileResponse(sample_path, media_type='text/csv', filename='sample_data.csv')

  content = sample_path.read_bytes()
  params = _request_params(request)
  return _analyze_bytes(content, params)


@app.post('/analyze')
async def analyze(request: Request):
  form = await request.form()
  upload = form.get('file')
  if not isinstance(upload, UploadFile):
    raise HTTPException(status_code=400, detail='Upload a CSV file using form field "file".')
  if upload.filename and not upload.filename.lower().endswith('.csv'):
    raise HTTPException(status_code=400, detail='Please upload a .csv file.')

  content = await upload.read()
  params = _request_params(request, form)
  return _analyze_bytes(content, params)


def _request_params(request: Request, form=None):
  names = [
    'filter_query',
    'chart_type',
    'x_column',
    'y_column',
    'aggregation',
    'sort_by',
    'limit',
  ]
  values = {}
  for name in names:
    form_value = form.get(name) if form is not None else None
    values[name] = form_value or request.query_params.get(name)
  return values


def _analyze_bytes(content: bytes, params: dict):
  if not content:
    raise HTTPException(status_code=400, detail='The uploaded CSV is empty.')

  try:
    df = _read_csv(content)
  except pd.errors.EmptyDataError as exc:
    raise HTTPException(status_code=400, detail='The CSV has no readable rows or columns.') from exc
  except HTTPException:
    raise
  except Exception as exc:
    raise HTTPException(status_code=400, detail=f'Could not parse CSV: {exc}') from exc

  if df.empty or len(df.columns) == 0:
    raise HTTPException(status_code=400, detail='The CSV must contain at least one row and one column.')

  df = df.dropna(how='all')
  if df.empty:
    raise HTTPException(status_code=400, detail='The CSV only contains blank rows.')

  filter_query = params.get('filter_query')
  if filter_query:
    try:
      df = df.query(str(filter_query))
    except Exception as exc:
      raise HTTPException(status_code=400, detail=f'Invalid filter query: {exc}') from exc
    if df.empty:
      raise HTTPException(status_code=400, detail='The filter removed all rows.')

  analysis_df, date_columns, numeric_columns, categorical_columns = _detect_columns(df.copy())
  primary_numeric = params.get('y_column') if params.get('y_column') in numeric_columns else _primary_numeric_column(numeric_columns)
  primary_date = params.get('x_column') if params.get('x_column') in date_columns else _first(date_columns)
  primary_category = params.get('x_column') if params.get('x_column') in categorical_columns else _first(categorical_columns)
  limit = _safe_limit(params.get('limit'))

  metrics = _build_metrics(
    analysis_df,
    date_columns,
    numeric_columns,
    categorical_columns,
    primary_numeric,
    primary_date,
    primary_category,
  )
  charts = _build_charts(
    analysis_df,
    params,
    primary_numeric,
    primary_date,
    primary_category,
    numeric_columns,
    categorical_columns,
    date_columns,
    limit,
  )

  return _clean_json(dict(
    config=dashboard_config,
    columns=dict(
      all=list(df.columns),
      numeric=numeric_columns,
      categorical=categorical_columns,
      date=date_columns,
      primary_numeric=primary_numeric,
      primary_date=primary_date,
      primary_category=primary_category,
    ),
    metrics=metrics,
    insights=_build_insights(analysis_df, metrics, primary_numeric, primary_date, primary_category),
    charts=charts,
    preview=_preview_records(df),
  ))


def _read_csv(content: bytes):
  last_decode_error = None
  for encoding in ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']:
    try:
      return pd.read_csv(BytesIO(content), encoding=encoding)
    except UnicodeDecodeError as exc:
      last_decode_error = exc

  raise HTTPException(status_code=400, detail='Could not decode the CSV as text.') from last_decode_error


def _primary_numeric_column(columns):
  preferred_tokens = ['sales', 'revenue', 'profit', 'amount', 'price', 'cost', 'quantity', 'users', 'count']
  ignored_tokens = ['id', 'postal', 'zip', 'code']

  for token in preferred_tokens:
    for column in columns:
      if token in str(column).lower():
        return column

  for column in columns:
    lower_name = str(column).lower()
    if not any(token in lower_name for token in ignored_tokens):
      return column

  return _first(columns)


def _detect_columns(df: pd.DataFrame):
  date_columns = []
  numeric_columns = []
  categorical_columns = []

  for column in df.columns:
    series = df[column]
    non_empty = series.dropna()
    if non_empty.empty:
      continue

    lower_name = str(column).lower()
    likely_date_name = any(token in lower_name for token in ['date', 'time', 'day', 'month'])
    sample_text = non_empty.astype(str).head(25)
    date_like_values = sample_text.str.contains(
      r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
      regex=True,
    ).mean() >= 0.7
    if likely_date_name or date_like_values:
      parsed = pd.to_datetime(series, errors='coerce', format='mixed')
      valid_ratio = parsed.notna().mean()
      if valid_ratio >= 0.7 and (likely_date_name or non_empty.nunique() > 1):
        df[column] = parsed
        date_columns.append(column)
        continue

    numeric = pd.to_numeric(series, errors='coerce')
    valid_ratio = numeric.notna().sum() / max(len(non_empty), 1)
    if pd.api.types.is_numeric_dtype(series) or valid_ratio >= 0.8:
      df[column] = numeric
      numeric_columns.append(column)

  for column in df.columns:
    if column in date_columns or column in numeric_columns:
      continue
    non_empty = df[column].dropna()
    if non_empty.empty:
      continue
    unique_count = non_empty.nunique()
    if unique_count <= max(20, len(non_empty) * 0.5):
      categorical_columns.append(column)

  return df, date_columns, numeric_columns, categorical_columns


def _build_metrics(df, date_columns, numeric_columns, categorical_columns, metric, date_col, category_col):
  primary = pd.to_numeric(df[metric], errors='coerce').dropna() if metric else pd.Series(dtype='float64')
  metrics = [
    _metric('Total rows', len(df), 'Rows available after filtering'),
    _metric('Total columns', len(df.columns), 'Columns detected in the CSV'),
    _metric('Numeric columns', len(numeric_columns), ', '.join(numeric_columns) or 'None found'),
    _metric('Categorical columns', len(categorical_columns), ', '.join(categorical_columns) or 'None found'),
  ]

  if metric and not primary.empty:
    metrics.extend([
      _metric(f'Total {metric}', primary.sum(), f'Sum of {metric}'),
      _metric(f'Average {metric}', primary.mean(), f'Mean value for {metric}'),
      _metric(f'Min {metric}', primary.min(), f'Lowest {metric} value'),
      _metric(f'Max {metric}', primary.max(), f'Highest {metric} value'),
    ])

  if metric and category_col:
    grouped = df.groupby(category_col, dropna=True)[metric].sum().sort_values(ascending=False)
    if not grouped.empty:
      metrics.append(_metric('Best category', str(grouped.index[0]), f'Highest total {metric}'))

  if metric and date_col:
    daily = df.dropna(subset=[date_col]).groupby(date_col)[metric].sum().sort_values(ascending=False)
    if not daily.empty:
      metrics.append(_metric('Best date', daily.index[0].date().isoformat(), f'Highest total {metric}'))

  return metrics


def _build_charts(df, params, metric, date_col, category_col, numeric_columns, categorical_columns, date_columns, limit):
  charts = []
  aggregation = params.get('aggregation') or 'sum'
  sort_by = params.get('sort_by') or 'value_desc'

  if metric and date_col:
    time_data = df.dropna(subset=[date_col]).groupby(date_col)[metric].agg(_agg_name(aggregation)).reset_index()
    time_data = time_data.sort_values(date_col).tail(limit)
    charts.append(dict(
      id='time',
      title=f'{metric} over time',
      type='line',
      labels=[value.date().isoformat() for value in time_data[date_col]],
      values=time_data[metric].tolist(),
    ))

  if metric and category_col:
    category_data = df.groupby(category_col, dropna=True)[metric].agg(_agg_name(aggregation)).reset_index()
    category_data = _sort_chart_data(category_data, category_col, metric, sort_by).head(limit)
    charts.append(dict(
      id='category',
      title=f'{metric} by {category_col}',
      type='bar',
      labels=category_data[category_col].astype(str).tolist(),
      values=category_data[metric].tolist(),
    ))

  if metric:
    numeric = pd.to_numeric(df[metric], errors='coerce').dropna()
    if not numeric.empty:
      bins = min(10, max(3, numeric.nunique()))
      histogram = pd.cut(numeric, bins=bins, duplicates='drop').value_counts().sort_index()
      charts.append(dict(
        id='distribution',
        title=f'{metric} distribution',
        type='bar',
        labels=[f'{interval.left:.0f} to {interval.right:.0f}' for interval in histogram.index],
        values=histogram.tolist(),
      ))

  custom = _custom_chart(df, params, numeric_columns, categorical_columns, date_columns, limit)
  if custom:
    charts.insert(0, custom)

  return charts


def _custom_chart(df, params, numeric_columns, categorical_columns, date_columns, limit):
  x_column = params.get('x_column')
  y_column = params.get('y_column')
  if not x_column or not y_column or y_column not in numeric_columns or x_column not in df.columns:
    return None

  aggregation = _agg_name(params.get('aggregation') or 'sum')
  chart_type = params.get('chart_type') or 'bar'
  sort_by = params.get('sort_by') or 'value_desc'
  data = df.dropna(subset=[x_column]).groupby(x_column)[y_column].agg(aggregation).reset_index()
  data = _sort_chart_data(data, x_column, y_column, sort_by).head(limit)

  if x_column in date_columns:
    labels = [value.date().isoformat() for value in data[x_column]]
    default_type = 'line'
  else:
    labels = data[x_column].astype(str).tolist()
    default_type = 'bar'

  if chart_type not in ['bar', 'line']:
    chart_type = default_type

  return dict(
    id='custom',
    title=f'{aggregation.title()} of {y_column} by {x_column}',
    type=chart_type,
    labels=labels,
    values=data[y_column].tolist(),
  )


def _build_insights(df, metrics, metric, date_col, category_col):
  insights = []
  rows = len(df)
  insights.append(f'The dataset contains {rows:,} rows across {len(df.columns):,} columns after filtering.')

  if metric:
    numeric = pd.to_numeric(df[metric], errors='coerce').dropna()
    if not numeric.empty:
      insights.append(f'{metric} ranges from {_format_number(numeric.min())} to {_format_number(numeric.max())}.')
      if numeric.mean() != 0:
        skew_hint = 'above' if numeric.median() > numeric.mean() else 'below'
        insights.append(f'The median {metric} is {skew_hint} the average, which hints at the value distribution.')

  if metric and category_col:
    grouped = df.groupby(category_col, dropna=True)[metric].sum().sort_values(ascending=False)
    if len(grouped) >= 2:
      lead = grouped.iloc[0] - grouped.iloc[1]
      insights.append(f'{grouped.index[0]} leads {category_col} by {_format_number(lead)} in total {metric}.')

  if metric and date_col:
    dated = df.dropna(subset=[date_col]).sort_values(date_col)
    if len(dated) >= 2:
      first = dated.iloc[0][metric]
      last = dated.iloc[-1][metric]
      direction = 'up' if last >= first else 'down'
      insights.append(f'From first to latest date, {metric} trends {direction} in this sample.')

  insights.append('Missing values are ignored in metrics and charts so partial CSVs still produce a useful dashboard.')
  return insights[:5]


def _preview_records(df):
  preview = df.head(PREVIEW_LIMIT).copy()
  for column in preview.columns:
    if pd.api.types.is_datetime64_any_dtype(preview[column]):
      preview[column] = preview[column].dt.strftime('%Y-%m-%d')
  return preview.where(pd.notna(preview), None).to_dict(orient='records')


def _sort_chart_data(data, label_col, value_col, sort_by):
  if sort_by == 'label_asc':
    return data.sort_values(label_col)
  if sort_by == 'label_desc':
    return data.sort_values(label_col, ascending=False)
  if sort_by == 'value_asc':
    return data.sort_values(value_col)
  return data.sort_values(value_col, ascending=False)


def _agg_name(value):
  return value if value in ['sum', 'mean', 'median', 'min', 'max', 'count'] else 'sum'


def _safe_limit(value):
  try:
    limit = int(value or CHART_LIMIT)
  except ValueError:
    limit = CHART_LIMIT
  return max(5, min(limit, CHART_LIMIT))


def _metric(label, value, hint):
  return dict(label=label, value=_format_number(value), hint=hint)


def _format_number(value):
  if isinstance(value, str):
    return value
  if pd.isna(value):
    return 'n/a'
  if float(value).is_integer():
    return f'{int(value):,}'
  return f'{float(value):,.2f}'


def _first(items):
  return items[0] if items else None


def _clean_json(value):
  if isinstance(value, dict):
    return {key: _clean_json(item) for key, item in value.items()}
  if isinstance(value, list):
    return [_clean_json(item) for item in value]
  if isinstance(value, pd.Timestamp):
    return value.isoformat()
  if pd.isna(value) if not isinstance(value, (list, dict, str)) else False:
    return None
  return value

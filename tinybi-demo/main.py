from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request


BASE_DIR = Path(__file__).resolve().parent
SUPPORTED_ENCODINGS = ('utf-8', 'utf-8-sig', 'cp1252', 'latin1')
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_CHART_ROWS = 100

app = FastAPI(title='TinyBI', version='1.0.0')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')

dashboard_config = dict(metrics=True, charts=True, insights=True, preview=True)


class DashboardConfig(BaseModel):
  metrics: bool | None = None
  charts: bool | None = None
  insights: bool | None = None
  preview: bool | None = None


def read_csv(content: bytes) -> pd.DataFrame:
  if not content:
    raise HTTPException(status_code=400, detail='The uploaded file is empty.')

  decode_errors = []
  for encoding in SUPPORTED_ENCODINGS:
    try:
      text = content.decode(encoding)
      frame = pd.read_csv(BytesIO(text.encode('utf-8')))
      if frame.empty:
        raise HTTPException(status_code=400, detail='The CSV contains no data rows.')
      if not len(frame.columns):
        raise HTTPException(status_code=400, detail='The CSV contains no columns.')
      return frame
    except UnicodeDecodeError:
      decode_errors.append(encoding)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
      raise HTTPException(status_code=400, detail=f'Could not parse the CSV: {exc}') from exc

  attempted = ', '.join(decode_errors)
  raise HTTPException(
    status_code=400,
    detail=f'Could not decode the CSV. Tried these encodings: {attempted}.',
  )


def detect_columns(frame: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
  numeric = frame.select_dtypes(include='number').columns.tolist()
  date_columns = []

  for column in frame.columns:
    if column in numeric:
      continue
    sample = frame[column].dropna().astype(str).head(100)
    if sample.empty:
      continue
    parsed = pd.to_datetime(sample, errors='coerce', format='mixed')
    likely_name = any(token in column.lower() for token in ('date', 'time', 'day', 'month', 'year'))
    if parsed.notna().mean() >= (0.6 if likely_name else 0.9):
      date_columns.append(column)

  categorical = [
    column for column in frame.columns
    if column not in numeric and column not in date_columns
  ]
  return numeric, date_columns, categorical


def clean_value(value):
  if pd.isna(value):
    return None
  if isinstance(value, pd.Timestamp):
    return value.isoformat()
  if hasattr(value, 'item'):
    return value.item()
  return value


def records(frame: pd.DataFrame) -> list[dict]:
  return [
    {str(key): clean_value(value) for key, value in row.items()}
    for row in frame.to_dict(orient='records')
  ]


def aggregate_series(
  frame: pd.DataFrame,
  x_column: str,
  y_column: str,
  aggregation: str,
  sort: str,
  limit: int,
) -> tuple[list[str], list[float]]:
  functions = dict(sum='sum', mean='mean', count='count', min='min', max='max')
  grouped = frame.dropna(subset=[x_column]).groupby(x_column, observed=True)[y_column]
  result = grouped.agg(functions[aggregation]).dropna()
  if sort == 'value_desc':
    result = result.sort_values(ascending=False)
  elif sort == 'value_asc':
    result = result.sort_values()
  else:
    result = result.sort_index()
  result = result.head(limit)
  return [str(value) for value in result.index], [float(value) for value in result.values]


def analyze_frame(
  frame: pd.DataFrame,
  chart_type: str,
  x_column: str | None,
  y_column: str | None,
  aggregation: str,
  sort: str,
  limit: int,
) -> dict:
  numeric, dates, categorical = detect_columns(frame)
  primary = y_column if y_column in numeric else (numeric[0] if numeric else None)
  date_column = dates[0] if dates else None
  category = x_column if x_column in frame.columns else (categorical[0] if categorical else None)

  metrics = dict(
    rows=len(frame),
    columns=len(frame.columns),
    numeric_columns=len(numeric),
    categorical_columns=len(categorical),
  )
  insights = [
    f'The dataset contains {len(frame):,} rows across {len(frame.columns)} columns.',
    f'{len(numeric)} numeric and {len(categorical)} categorical columns were detected.',
  ]

  if primary:
    series = frame[primary].dropna()
    metrics.update(dict(
      primary_metric=primary,
      total=clean_value(series.sum()) if not series.empty else None,
      average=clean_value(series.mean()) if not series.empty else None,
      minimum=clean_value(series.min()) if not series.empty else None,
      maximum=clean_value(series.max()) if not series.empty else None,
    ))
    if not series.empty:
      insights.append(f'{primary} averages {series.mean():,.2f}, with a total of {series.sum():,.2f}.')

  charts = []
  if primary and date_column:
    plotted = frame[[date_column, primary]].copy()
    plotted[date_column] = pd.to_datetime(plotted[date_column], errors='coerce')
    plotted = plotted.dropna().sort_values(date_column)
    labels, values = aggregate_series(
      plotted, date_column, primary, aggregation, 'index', min(limit, MAX_CHART_ROWS)
    )
    charts.append(dict(
      id='timeline',
      title=f'{primary} over time',
      type='line' if chart_type == 'auto' else chart_type,
      labels=labels,
      values=values,
      x=date_column,
      y=primary,
    ))
    if values:
      best_index = values.index(max(values))
      metrics['best_date'] = labels[best_index]
      insights.append(f'The strongest {date_column} was {labels[best_index]} at {values[best_index]:,.2f}.')

  if primary and category:
    labels, values = aggregate_series(
      frame, category, primary, aggregation, sort, min(limit, MAX_CHART_ROWS)
    )
    charts.append(dict(
      id='categories',
      title=f'{primary} by {category}',
      type='bar' if chart_type == 'auto' else chart_type,
      labels=labels,
      values=values,
      x=category,
      y=primary,
    ))
    if values:
      best_index = values.index(max(values))
      metrics['best_category'] = labels[best_index]
      insights.append(f'{labels[best_index]} leads {category} with {values[best_index]:,.2f} {primary}.')

  if primary:
    distribution = frame[primary].dropna()
    if not distribution.empty:
      bins = min(10, max(1, distribution.nunique()))
      counts = distribution.value_counts(bins=bins, sort=False)
      charts.append(dict(
        id='distribution',
        title=f'{primary} distribution',
        type='bar',
        labels=[str(interval) for interval in counts.index],
        values=[int(value) for value in counts.values],
        x=primary,
        y='Frequency',
      ))

  return dict(
    columns=[str(column) for column in frame.columns],
    detected=dict(numeric=numeric, dates=dates, categorical=categorical),
    metrics=metrics,
    insights=insights[:5],
    charts=charts,
    preview=records(frame.head(10)),
    config=dashboard_config.copy(),
  )


@app.get('/')
async def home(request: Request):
  return templates.TemplateResponse(request=request, name='index.html', context=dict(app_name='TinyBI'))


@app.get('/sample-data')
async def sample_data():
  return FileResponse(BASE_DIR / 'sample_data.csv', media_type='text/csv', filename='sample_data.csv')


@app.post('/analyze')
async def analyze(
  file: Annotated[UploadFile, File(description='A CSV file to analyze')],
  query: Annotated[str | None, Query(description='Optional pandas query expression')] = None,
  chart_type: Literal['auto', 'bar', 'line', 'pie', 'doughnut'] = 'auto',
  x: str | None = None,
  y: str | None = None,
  aggregation: Literal['sum', 'mean', 'count', 'min', 'max'] = 'sum',
  sort: Literal['index', 'value_asc', 'value_desc'] = 'value_desc',
  limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
  if file.filename and not file.filename.lower().endswith('.csv'):
    raise HTTPException(status_code=400, detail='Please upload a CSV file.')
  content = await file.read(MAX_UPLOAD_BYTES + 1)
  if len(content) > MAX_UPLOAD_BYTES:
    raise HTTPException(status_code=413, detail='CSV files must be 15 MB or smaller.')

  frame = read_csv(content)
  if query:
    try:
      frame = frame.query(query)
    except Exception as exc:
      raise HTTPException(status_code=400, detail=f'Invalid filter expression: {exc}') from exc
    if frame.empty:
      raise HTTPException(status_code=400, detail='The filter returned no rows.')

  for name, value in (('x', x), ('y', y)):
    if value and value not in frame.columns:
      raise HTTPException(status_code=400, detail=f'Unknown {name} column: {value}')

  return analyze_frame(frame, chart_type, x, y, aggregation, sort, limit)


@app.post('/config')
async def update_config(config: DashboardConfig):
  updates = config.model_dump(exclude_none=True)
  dashboard_config.update(updates)
  return dict(config=dashboard_config.copy())

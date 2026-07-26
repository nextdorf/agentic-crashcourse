from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict
from starlette.datastructures import UploadFile

from analytics import AnalysisError, DashboardStore, DEFAULT_CONTROLS, MAX_INPUT_BYTES
from mcp_server import create_mcp


APP_NAME = 'TinyBI 2'
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / 'sample_data.csv'

dashboard_store = DashboardStore(SAMPLE_PATH.read_bytes())
mcp = create_mcp(dashboard_store)
mcp_app = mcp.http_app(path='/')
app = FastAPI(title=APP_NAME, lifespan=mcp_app.lifespan)
app.state.dashboard_store = dashboard_store
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
app.mount('/mcp', mcp_app)
templates = Jinja2Templates(directory=BASE_DIR / 'templates')


class ConfigUpdate(BaseModel):
  model_config = ConfigDict(extra='forbid')
  show_metrics: bool | None = None
  show_charts: bool | None = None
  show_preview: bool | None = None
  show_insights: bool | None = None


@app.get('/')
async def index(request: Request):
  return templates.TemplateResponse(
    request,
    'index.html',
    dict(
      app_name=APP_NAME,
      config=dashboard_store.workspace()['visibility'],
      max_input_mb=MAX_INPUT_BYTES / 1024 / 1024,
    ),
  )


@app.post('/config')
async def update_config(update: ConfigUpdate):
  workspace = dashboard_store.update_visibility(update.model_dump(exclude_none=True), 'browser')
  return dict(config=workspace['visibility'], workspace=workspace)


@app.get('/state')
async def state(
  response: Response,
  after_revision: int | None = Query(default=None, ge=0),
):
  snapshot = dashboard_store.snapshot(after_revision)
  if snapshot is None:
    response.status_code = 204
    return None
  return snapshot


@app.get('/sample-data')
async def sample_data(request: Request):
  if request.query_params.get('download') == 'true':
    return FileResponse(SAMPLE_PATH, media_type='text/csv', filename='sample_data.csv')
  return run_analysis(SAMPLE_PATH.read_bytes(), 'sample_data.csv', request_params(request))


@app.post('/analyze')
async def analyze(request: Request):
  form = await request.form()
  upload = form.get('file')
  if not isinstance(upload, UploadFile):
    raise HTTPException(status_code=400, detail='Upload a CSV file using multipart form field "file".')
  if upload.filename and not upload.filename.lower().endswith('.csv'):
    raise HTTPException(status_code=400, detail='Please upload a .csv file.')
  content = await upload.read(MAX_INPUT_BYTES + 1)
  return run_analysis(content, upload.filename or 'uploaded.csv', request_params(request, form))


def request_params(request: Request, form=None):
  names = ['filter_query', 'chart_type', 'x_column', 'y_column', 'aggregation', 'sort_by', 'limit']
  values = {}
  for name in names:
    if form is not None and name in form:
      values[name] = form.get(name)
    elif name in request.query_params:
      values[name] = request.query_params.get(name)
  return values


def run_analysis(content, source_label, controls):
  try:
    return dashboard_store.analyze(content, source_label, {**DEFAULT_CONTROLS, **controls}, updated_by='browser')
  except AnalysisError as exc:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

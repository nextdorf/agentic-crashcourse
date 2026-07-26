from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from analytics import AnalysisError, DashboardStore, MAX_INPUT_BYTES
from mcp_server import create_mcp


APP_NAME = 'TinyBI 2'
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / 'sample_data.csv'


class StrictRequest(BaseModel):
  model_config = ConfigDict(extra='forbid')


class WorkspaceMutation(StrictRequest):
  expected_incarnation: str = Field(min_length=1)
  expected_revision: int = Field(ge=0)


class ConfigUpdate(WorkspaceMutation):
  show_metrics: bool | None = None
  show_charts: bool | None = None
  show_preview: bool | None = None
  show_insights: bool | None = None


class AnalysisUpdate(WorkspaceMutation):
  request_client: str = Field(min_length=1, max_length=100)
  request_sequence: int = Field(ge=1)
  filter_query: str | None = None
  chart_type: str | None = None
  x_column: str | None = None
  y_column: str | None = None
  aggregation: str | None = None
  sort_by: str | None = None
  limit: int | None = None


def create_app(store: DashboardStore | None = None):
  store = store or DashboardStore(SAMPLE_PATH.read_bytes())
  mcp = create_mcp(store)
  mcp_app = mcp.http_app(path='/')
  app = FastAPI(title=APP_NAME, lifespan=mcp_app.lifespan)
  app.state.dashboard_store = store
  app.state.mcp = mcp
  app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
  app.mount('/mcp', mcp_app)
  templates = Jinja2Templates(directory=BASE_DIR / 'templates')

  @app.get('/')
  async def index(request: Request):
    workspace = store.workspace()
    return templates.TemplateResponse(
      request,
      'index.html',
      dict(
        app_name=APP_NAME,
        config=workspace['visibility'],
        workspace=workspace,
        max_input_mb=MAX_INPUT_BYTES / 1024 / 1024,
      ),
    )

  @app.post('/config')
  async def update_config(update: ConfigUpdate):
    changes = update.model_dump(exclude={'expected_incarnation', 'expected_revision'}, exclude_none=True)
    try:
      workspace = await run_in_threadpool(
        store.update_visibility,
        changes,
        update.expected_incarnation,
        update.expected_revision,
        'browser',
      )
      return dict(config=workspace['visibility'], workspace=workspace)
    except AnalysisError as exc:
      raise_http(exc)

  @app.get('/state')
  async def state(
    response: Response,
    after_revision: int | None = Query(default=None, ge=0),
    incarnation: str | None = Query(default=None),
  ):
    snapshot = store.snapshot(after_revision, incarnation)
    if snapshot is None:
      response.status_code = 204
      return None
    return snapshot

  @app.get('/sample-data')
  async def sample_data_download():
    return FileResponse(SAMPLE_PATH, media_type='text/csv', filename='sample_data.csv')

  @app.post('/sample-data')
  async def sample_data(update: AnalysisUpdate):
    return await run_analysis(store, update, SAMPLE_PATH.read_bytes(), 'sample_data.csv')

  @app.post('/analyze-active')
  async def analyze_active(update: AnalysisUpdate):
    return await run_analysis(store, update)

  @app.post('/analyze')
  async def analyze(request: Request):
    form = await request.form()
    upload = form.get('file')
    if not isinstance(upload, UploadFile):
      raise HTTPException(status_code=400, detail='Upload a CSV file using multipart form field "file".')
    if upload.filename and not upload.filename.lower().endswith('.csv'):
      raise HTTPException(status_code=400, detail='Please upload a .csv file.')
    try:
      update = AnalysisUpdate.model_validate(form_values(form))
    except ValueError as exc:
      raise HTTPException(status_code=422, detail=str(exc)) from exc
    content = await upload.read(MAX_INPUT_BYTES + 1)
    return await run_analysis(store, update, content, upload.filename or 'uploaded.csv')

  return app, store, mcp


def form_values(form):
  names = [
    'expected_incarnation', 'expected_revision', 'filter_query', 'chart_type', 'x_column',
    'y_column', 'aggregation', 'sort_by', 'limit', 'request_client', 'request_sequence',
  ]
  return {name: form.get(name) for name in names if name in form}


async def run_analysis(store, update, content=None, source_label=None):
  controls = update.model_dump(
    exclude={'expected_incarnation', 'expected_revision', 'request_client', 'request_sequence'},
    exclude_none=True,
  )
  try:
    return await run_in_threadpool(
      store.analyze,
      update.expected_incarnation,
      update.expected_revision,
      content,
      source_label,
      controls,
      None,
      'browser',
      update.request_client,
      update.request_sequence,
    )
  except AnalysisError as exc:
    raise_http(exc)


def raise_http(exc):
  raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


app, dashboard_store, mcp = create_app()

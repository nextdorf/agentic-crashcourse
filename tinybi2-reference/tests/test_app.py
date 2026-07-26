import pytest
from fastapi.testclient import TestClient

from analytics import DashboardStore
from main import create_app


SAMPLE = b'Group,Zone,Amount,X,Y\nA,North,1,1,5\nB,South,2,2,4\n'


@pytest.fixture
def app_store():
  store = DashboardStore(SAMPLE)
  app, _, mcp = create_app(store)
  return app, store, mcp


def version_payload(store):
  workspace = store.workspace()
  return dict(expected_incarnation=workspace['incarnation'], expected_revision=workspace['revision'])


def analysis_payload(store, sequence=1):
  return {**version_payload(store), 'request_client': 'test-browser', 'request_sequence': sequence}


def test_routes_active_rerun_revisions_state_and_config(app_store):
  app, store, _ = app_store
  with TestClient(app) as client:
    initial = client.get('/state').json()
    sample = client.post('/sample-data', json=analysis_payload(store, 1))
    assert sample.status_code == 200
    sample_revision = sample.json()['workspace']['revision']
    assert client.get('/state', params=dict(
      after_revision=sample_revision,
      incarnation=sample.json()['workspace']['incarnation'],
    )).status_code == 204

    upload = client.post(
      '/analyze',
      files=dict(file=('distinctive.csv', b'Day,Team,Revenue\n2026-01-01,Blue,7\n2026-01-02,Gold,11\n', 'text/csv')),
      data=analysis_payload(store, 2),
    )
    assert upload.status_code == 200
    assert upload.json()['workspace']['active_source'] == 'distinctive.csv'

    active = client.post('/analyze-active', json={**analysis_payload(store, 3), 'filter_query': 'Revenue >= 10'})
    assert active.status_code == 200
    assert active.json()['workspace']['active_source'] == 'distinctive.csv'
    assert active.json()['metadata']['row_count_after_filter'] == 1

    changed = client.post('/config', json={**version_payload(store), 'show_charts': False}).json()
    assert changed['config']['show_charts'] is False
    assert client.get('/sample-data').headers['content-type'].startswith('text/csv')


def test_stale_http_mutations_conflict_without_state_change(app_store):
  app, store, _ = app_store
  stale = analysis_payload(store)
  with TestClient(app) as client:
    first = client.post('/sample-data', json=stale)
    revision = first.json()['workspace']['revision']
    conflict = client.post('/config', json={
      'expected_incarnation': stale['expected_incarnation'],
      'expected_revision': stale['expected_revision'],
      'show_preview': False,
    })

    assert conflict.status_code == 409
    assert store.workspace()['revision'] == revision
    assert store.workspace()['visibility']['show_preview'] is True


def test_polling_recovers_from_new_incarnation_with_lower_revision(app_store):
  app, store, _ = app_store
  old = DashboardStore(SAMPLE)
  old_workspace = old.workspace()
  old.analyze(old_workspace['incarnation'], old_workspace['revision'])
  old_revision = old.workspace()['revision']

  with TestClient(app) as client:
    response = client.get('/state', params=dict(after_revision=old_revision + 20, incarnation=old_workspace['incarnation']))
    assert response.status_code == 200
    assert response.json()['workspace']['incarnation'] == store.workspace()['incarnation']
    assert response.json()['workspace']['revision'] == 0


def test_state_is_bounded_isolated_and_does_not_leak_input(app_store):
  app, store, _ = app_store
  secret = 'DO_NOT_EXPOSE_INLINE_CONTENT'
  with TestClient(app) as client:
    client.post(
      '/analyze',
      files=dict(file=('safe.csv', f'Name,Value\n{secret},1\n'.encode(), 'text/csv')),
      data=analysis_payload(store),
    )
    payload = client.get('/state').json()
    serialized = str(payload)

  assert len(payload['dashboard']['preview']) <= 10
  assert '_content' not in serialized
  assert 'DataFrame' not in serialized
  assert '/home/' not in serialized
  assert f'Name,Value\\n{secret},1' not in serialized


def test_active_controls_can_be_cleared_to_defaults(app_store):
  app, store, _ = app_store
  with TestClient(app) as client:
    first = client.post(
      '/analyze',
      files=dict(file=('controls.csv', SAMPLE, 'text/csv')),
      data={
        **analysis_payload(store, 1),
        'filter_query': 'Amount >= 2',
        'x_column': 'Group',
        'sort_by': 'label_desc',
      },
    )
    assert first.status_code == 200
    cleared = client.post('/analyze-active', json={
      **analysis_payload(store, 2),
      'filter_query': '',
      'x_column': '',
      'sort_by': '',
    })

  assert cleared.status_code == 200
  controls = cleared.json()['workspace']['requested_controls']
  assert controls['filter_query'] is None
  assert controls['x_column'] is None
  assert controls['sort_by'] is None
  assert cleared.json()['metadata']['row_count_after_filter'] == 2


def test_mounted_streamable_http_transport_initializes(app_store):
  app, _, _ = app_store
  request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'initialize',
    'params': {
      'protocolVersion': '2025-06-18',
      'capabilities': {},
      'clientInfo': dict(name='transport-test', version='1'),
    },
  }
  headers = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
  with TestClient(app) as client:
    response = client.post('/mcp', headers=headers, json=request)

  assert response.status_code == 200
  assert response.headers['mcp-session-id']
  assert '"result"' in response.text

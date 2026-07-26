from fastapi.testclient import TestClient

from main import app


def test_routes_upload_revisions_state_and_config():
  with TestClient(app) as client:
    assert client.get('/').status_code == 200
    initial = client.get('/state').json()
    assert 'dashboard' in initial
    start = initial['workspace']['revision']

    sample = client.get('/sample-data')
    assert sample.status_code == 200
    sample_revision = sample.json()['workspace']['revision']
    assert sample_revision == start + 1
    assert client.get(f'/state?after_revision={sample_revision}').status_code == 204

    upload = client.post(
      '/analyze',
      files=dict(file=('distinctive.csv', b'Day,Team,Revenue\n2026-01-01,Blue,7\n2026-01-02,Gold,11\n', 'text/csv')),
    )
    assert upload.status_code == 200
    assert upload.json()['workspace']['revision'] == sample_revision + 1
    assert upload.json()['workspace']['active_source'] == 'distinctive.csv'

    changed = client.post('/config', json=dict(show_charts=False)).json()
    assert changed['config']['show_charts'] is False
    state = client.get('/state').json()
    assert state['workspace']['visibility']['show_charts'] is False
    assert state['dashboard']['config']['show_charts'] is False

    download = client.get('/sample-data?download=true')
    assert download.status_code == 200
    assert download.headers['content-type'].startswith('text/csv')


def test_state_is_bounded_and_does_not_leak_input_or_paths():
  secret = 'DO_NOT_EXPOSE_INLINE_CONTENT'
  with TestClient(app) as client:
    client.post('/analyze', files=dict(file=('safe.csv', f'Name,Value\n{secret},1\n'.encode(), 'text/csv')))
    payload = client.get('/state').json()
    serialized = str(payload)

  assert len(payload['dashboard']['preview']) <= 10
  assert '_content' not in serialized
  assert 'DataFrame' not in serialized
  assert '/home/' not in serialized
  assert f'Name,Value\\n{secret},1' not in serialized


def test_invalid_http_filter_does_not_change_revision():
  with TestClient(app) as client:
    valid = client.post('/analyze', files=dict(file=('ok.csv', b'Group,Amount\nA,1\nB,2\n', 'text/csv')))
    revision = valid.json()['workspace']['revision']
    invalid = client.post(
      '/analyze',
      files=dict(file=('bad.csv', b'Group,Amount\nA,1\n', 'text/csv')),
      data=dict(filter_query='this is not valid pandas query !!!'),
    )

    assert invalid.status_code == 400
    assert client.get('/state').json()['workspace']['revision'] == revision

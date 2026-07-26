import json
import math
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import analytics
from analytics import AnalysisError, DashboardStore, WorkspaceConflict, analyze_bytes, create_chart_bytes, inspect_bytes


def csv(text):
  return text.encode('utf-8')


def version(store):
  workspace = store.workspace()
  return workspace['incarnation'], workspace['revision']


def analyze(store, content=None, label=None, overrides=None):
  incarnation, revision = version(store)
  return store.analyze(incarnation, revision, content, label, overrides)


def test_sample_analysis_is_bounded_and_machine_readable():
  result = analyze_bytes(open('sample_data.csv', 'rb').read())

  assert result['metadata']['encoding'] == 'cp1252'
  assert result['metadata']['row_count_before_filter'] == 9994
  assert result['columns']['primary_numeric'] == 'Sales'
  assert len(result['preview']) == 10
  assert isinstance(result['metrics'][0]['value'], int)
  json.dumps(result, allow_nan=False)


def test_non_utf8_empty_oversized_and_non_finite_inputs(monkeypatch):
  content = 'Region,Amount\nWest,10\nCafé – North,20\n'.encode('cp1252')
  assert inspect_bytes(content)['metadata']['encoding'] == 'cp1252'
  with pytest.raises(AnalysisError, match='empty'):
    analyze_bytes(b'')
  with monkeypatch.context() as context:
    context.setattr(analytics, 'MAX_INPUT_BYTES', 4)
    with pytest.raises(AnalysisError, match='input limit'):
      analyze_bytes(b'a,b\n1,2')

  result = analyze_bytes(csv('Group,Amount\nA,inf\nB,-inf\nC,3\n'))
  assert result['preview'][0]['Amount'] is None
  assert not any(isinstance(value, float) and not math.isfinite(value) for row in result['preview'] for value in row.values())
  json.dumps(result, allow_nan=False)


def test_requested_auto_controls_do_not_become_resolved_controls():
  store = DashboardStore(csv('When,Group,Amount\n2024-01-01,A,1\n2024-01-02,B,2\n'))
  first = analyze(store)
  second = analyze(store)

  assert first['requested_config']['chart_type'] == 'auto'
  assert first['effective_config']['chart_type'] == 'line'
  assert second['workspace']['requested_controls']['chart_type'] == 'auto'
  assert all(chart['scope'] == 'automatic' for chart in second['charts'])


def test_stale_mutation_is_rejected_and_snapshot_is_isolated():
  store = DashboardStore(csv('Group,Amount\nA,1\nB,2\n'))
  incarnation, revision = version(store)
  result = store.analyze(incarnation, revision)

  with pytest.raises(WorkspaceConflict):
    store.update_visibility(dict(show_charts=False), incarnation, revision)

  snapshot = store.snapshot()
  snapshot['dashboard']['preview'][0]['Group'] = 'changed'
  assert store.snapshot()['dashboard']['preview'][0]['Group'] == 'A'
  assert store.workspace()['revision'] == result['workspace']['revision']


def test_managed_chart_batches_are_atomic_ordered_and_ids_are_not_reused():
  content = csv('Group,Zone,X,Y,Amount\nA,North,1,5,10\nB,North,2,4,20\nA,South,3,3,30\nB,South,4,2,40\n')
  store = DashboardStore(content)
  analyze(store)
  definitions = [
    dict(type='bar', x_column='Group', y_column='Amount'),
    dict(type='scatter', x_column='X', y_column='Y', limit=3),
    dict(type='heatmap', x_column='Group', y_column='Zone', value_column='Amount'),
  ]
  incarnation, revision = version(store)
  created = store.create_charts(definitions, incarnation, revision)

  assert [chart['id'] for chart in created['charts']] == [1, 2, 3]
  assert [chart['type'] for chart in store.snapshot()['dashboard']['charts'][-3:]] == ['bar', 'scatter', 'heatmap']

  incarnation, revision = version(store)
  updated = store.update_charts([
    dict(id=1, definition=dict(type='line', x_column='Group', y_column='Amount', sort_by='label_asc')),
  ], incarnation, revision)
  assert updated['charts'][0]['id'] == 1
  assert store.list_charts()['charts'][1]['id'] == 2

  incarnation, revision = version(store)
  reordered = store.reorder_charts([3, 1, 2], incarnation, revision)
  assert reordered['ordered_ids'] == [3, 1, 2]

  before = store.workspace()
  with pytest.raises(AnalysisError):
    store.reorder_charts([3, 1], before['incarnation'], before['revision'])
  assert store.workspace() == before

  with pytest.raises(AnalysisError, match='Unexpected fields'):
    store.create_charts([
      dict(type='bar', x_column='Group', y_column='Amount'),
      dict(type='scatter', x_column='X', y_column='Y', aggregation='sum'),
    ], before['incarnation'], before['revision'])
  assert store.workspace() == before

  incarnation, revision = version(store)
  store.delete_charts([2], incarnation, revision)
  incarnation, revision = version(store)
  new_chart = store.create_charts([dict(type='bar', x_column='Zone', y_column='Amount')], incarnation, revision)
  assert new_chart['charts'][0]['id'] == 4


def test_dataset_replacement_clears_charts_but_same_dataset_analysis_preserves_them():
  store = DashboardStore(csv('Group,Amount\nA,1\nB,2\n'))
  analyze(store)
  incarnation, revision = version(store)
  store.create_charts([dict(type='bar', x_column='Group', y_column='Amount')], incarnation, revision)

  analyze(store, overrides=dict(filter_query='Amount >= 1'))
  assert store.workspace()['managed_chart_ids'] == [1]

  analyze(store, csv('Team,Score\nRed,3\nBlue,5\n'), 'new.csv')
  assert store.workspace()['managed_chart_ids'] == []
  incarnation, revision = version(store)
  created = store.create_charts([dict(type='bar', x_column='Team', y_column='Score')], incarnation, revision)
  assert created['charts'][0]['id'] == 2


def test_scatter_and_heatmap_validation_bounds_and_null_handling():
  content = csv('Group,Zone,X,Y,Amount\nA,North,1,5,10\nA,North,2,,20\nB,South,3,3,30\n')
  scatter = create_chart_bytes(content, dict(chart_type='scatter', x_column='X', y_column='Y', limit=10))
  assert scatter['chart']['points'] == [dict(x=1, y=5), dict(x=3, y=3)]

  store = DashboardStore(content)
  analyze(store)
  incarnation, revision = version(store)
  result = store.create_charts([
    dict(type='heatmap', x_column='Group', y_column='Zone', value_column='Amount', aggregation='sum', x_limit=2, y_limit=2),
  ], incarnation, revision)
  cells = result['charts'][0]['chart']['cells']
  assert cells == [dict(x='A', y='North', value=30), dict(x='B', y='South', value=30)]

  incarnation, revision = version(store)
  with pytest.raises(AnalysisError, match='x_column'):
    store.create_charts([dict(type='scatter', x_column='Group', y_column='Y')], incarnation, revision)


def test_visibility_no_op_does_not_increment_revision():
  store = DashboardStore(csv('Group,Amount\nA,1\n'))
  workspace = store.workspace()
  result = store.update_visibility(dict(show_charts=True), workspace['incarnation'], workspace['revision'])
  assert result['revision'] == workspace['revision']


def test_newer_browser_request_supersedes_in_flight_analysis(monkeypatch):
  store = DashboardStore(csv('Group,Amount\nA,1\nB,2\n'))
  workspace = store.workspace()
  started = Event()
  release = Event()
  original = analytics.analyze_dataset

  def delayed(dataset, controls):
    if controls.get('filter_query') == 'Amount > 0':
      started.set()
      release.wait(timeout=5)
    return original(dataset, controls)

  monkeypatch.setattr(analytics, 'analyze_dataset', delayed)
  with ThreadPoolExecutor(max_workers=2) as executor:
    older = executor.submit(
      store.analyze,
      workspace['incarnation'], workspace['revision'], None, None,
      dict(filter_query='Amount > 0'), None, 'browser', 'browser-a', 1,
    )
    assert started.wait(timeout=5)
    newer = executor.submit(
      store.analyze,
      workspace['incarnation'], workspace['revision'], None, None,
      dict(filter_query='Amount >= 2'), None, 'browser', 'browser-a', 2,
    )
    latest = newer.result(timeout=5)
    release.set()
    with pytest.raises(AnalysisError):
      older.result(timeout=5)

  assert latest['metadata']['row_count_after_filter'] == 1
  assert store.workspace()['requested_controls']['filter_query'] == 'Amount >= 2'


def test_extreme_finite_range_does_not_crash_histogram_or_emit_infinity():
  result = analyze_bytes(csv('Group,Amount\nA,-1e308\nB,1e308\n'))
  json.dumps(result, allow_nan=False)
  assert not any(chart['id'] == 'distribution' for chart in result['charts'])

  constant = analyze_bytes(csv('Group,Amount\nA,1e308\nB,1e308\n'))
  json.dumps(constant, allow_nan=False)
  distribution = next(chart for chart in constant['charts'] if chart['id'] == 'distribution')
  assert len(distribution['labels']) == 1
  assert 'inf' not in distribution['labels'][0].lower()
  assert not any('median' in insight.lower() for insight in constant['insights'])


def test_datetime_chart_labels_preserve_distinct_times():
  content = csv('Timestamp,Zone,Amount\n2024-01-01 01:00:00,North,1\n2024-01-01 02:00:00,North,2\n')
  store = DashboardStore(content)
  analyze(store)
  incarnation, revision = version(store)
  created = store.create_charts([
    dict(type='heatmap', x_column='Timestamp', y_column='Zone', value_column='Amount'),
  ], incarnation, revision)
  labels = created['charts'][0]['chart']['x_labels']
  assert labels == ['2024-01-01T02:00:00', '2024-01-01T01:00:00']
  assert len(labels) == len(set(labels))

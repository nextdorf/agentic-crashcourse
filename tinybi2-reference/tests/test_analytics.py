import json
import math

import pytest

import analytics
from analytics import AnalysisError, DashboardStore, analyze_bytes, create_chart_bytes, inspect_bytes


def csv(text):
  return text.encode('utf-8')


def test_sample_analysis_is_bounded_and_machine_readable():
  result = analyze_bytes(open('sample_data.csv', 'rb').read())

  assert result['metadata']['encoding'] == 'cp1252'
  assert result['metadata']['row_count_before_filter'] == 9994
  assert result['columns']['primary_numeric'] == 'Sales'
  assert len(result['preview']) == 10
  assert isinstance(result['metrics'][0]['value'], int)
  assert result['metrics'][0]['display_value'] == '9,994'


def test_non_utf8_empty_and_oversized_inputs(monkeypatch):
  content = 'Region,Amount\nWest,10\nCafé – North,20\n'.encode('cp1252')
  assert inspect_bytes(content)['metadata']['encoding'] == 'cp1252'
  with pytest.raises(AnalysisError, match='empty'):
    analyze_bytes(b'')
  monkeypatch.setattr(analytics, 'MAX_INPUT_BYTES', 4)
  with pytest.raises(AnalysisError, match='input limit'):
    analyze_bytes(b'a,b\n1,2')


def test_identifiers_are_not_measures_and_filtering_is_typed():
  content = csv('Row ID,Postal Code,Group,Amount\n1,90210,A,"2"\n2,10001,B,"12"\n3,10002,C,"20"\n')
  inspected = inspect_bytes(content)
  result = analyze_bytes(content, dict(filter_query='Amount > 10'))

  assert inspected['metadata']['identifiers'] == ['Row ID', 'Postal Code']
  assert inspected['metadata']['measures'] == ['Amount']
  assert result['metadata']['row_count_after_filter'] == 2
  assert [row['Group'] for row in result['preview']] == ['B', 'C']


def test_date_chart_defaults_to_chronological_order():
  content = csv('When,Revenue\n2024-03-01,30\n2024-01-01,10\n2024-02-01,20\n')
  result = create_chart_bytes(content, dict(x_column='When', y_column='Revenue', limit=10))

  assert result['effective_config']['sort_by'] == 'label_asc'
  assert result['chart']['labels'] == ['2024-01-01', '2024-02-01', '2024-03-01']


def test_equal_median_mean_and_json_safe_preview():
  result = analyze_bytes(csv('When,Amount\n2024-01-01,1\n2024-01-02,2\n2024-01-03,3\n2024-01-04,\n'))

  assert any('equal to the average' in insight for insight in result['insights'])
  assert result['preview'][0]['When'] == '2024-01-01'
  assert result['preview'][3]['Amount'] is None
  assert not any(isinstance(value, float) and math.isnan(value) for row in result['preview'] for value in row.values())
  json.dumps(result)


def test_store_failure_is_atomic():
  content = csv('Group,Amount\nA,1\nB,2\n')
  store = DashboardStore(content)
  first = store.analyze(content, 'ok.csv')
  revision = first['workspace']['revision']

  with pytest.raises(AnalysisError):
    store.create_chart(dict(x_column='missing', y_column='Amount'))

  assert store.workspace()['revision'] == revision
  assert store.workspace()['active_source'] == 'ok.csv'

import asyncio

from fastmcp import Client
from fastapi.testclient import TestClient

from analytics import DashboardStore
from main import create_app
from mcp_server import create_mcp


def run(coroutine):
  return asyncio.run(coroutine)


def data(result):
  value = result.structured_content
  if value is not None:
    return value
  value = result.data
  while hasattr(value, 'root'):
    value = value.root
  return value.model_dump() if hasattr(value, 'model_dump') else value


def expected(workspace):
  return dict(expected_incarnation=workspace['incarnation'], expected_revision=workspace['revision'])


def test_tool_contract_and_managed_chart_lifecycle():
  store = DashboardStore(b'Group,Zone,X,Y,Amount\nA,North,1,5,10\nB,South,2,4,20\n')
  mcp = create_mcp(store)

  async def exercise():
    async with Client(mcp) as client:
      tools = await client.list_tools()
      by_name = {tool.name: tool for tool in tools}
      assert set(by_name) == {
        'inspect_dataset', 'analyze_dataset', 'list_charts', 'create_charts',
        'update_charts', 'delete_charts', 'reorder_charts',
      }
      assert by_name['inspect_dataset'].annotations.readOnlyHint is True
      assert by_name['list_charts'].annotations.readOnlyHint is True
      assert by_name['delete_charts'].annotations.destructiveHint is True
      for name in set(by_name) - {'inspect_dataset', 'list_charts'}:
        required = by_name[name].inputSchema.get('required', [])
        assert 'expected_incarnation' in required
        assert 'expected_revision' in required
      for tool in tools:
        assert tool.description
        assert tool.outputSchema.get('additionalProperties') is False

      inspected = data(await client.call_tool('inspect_dataset', {}))
      analyzed = data(await client.call_tool('analyze_dataset', {
        **expected(inspected['workspace']),
        'dataset': dict(source='inline', inline_csv='Group,Zone,X,Y,Amount\nA,North,1,5,10\nB,South,2,4,20\n'),
      }))
      assert analyzed['workspace']['active_source'] == 'inline CSV'

      created = data(await client.call_tool('create_charts', {
        **expected(analyzed['workspace']),
        'definitions': [
          dict(type='bar', x_column='Group', y_column='Amount'),
          dict(type='scatter', x_column='X', y_column='Y'),
          dict(type='heatmap', x_column='Group', y_column='Zone', value_column='Amount'),
        ],
      }))
      assert [chart['id'] for chart in created['charts']] == [1, 2, 3]

      listed = data(await client.call_tool('list_charts', dict(include_data=True)))
      assert [chart['definition']['type'] for chart in listed['charts']] == ['bar', 'scatter', 'heatmap']

      updated = data(await client.call_tool('update_charts', {
        **expected(listed['workspace']),
        'updates': [dict(id=1, definition=dict(type='line', x_column='Group', y_column='Amount'))],
      }))
      reordered = data(await client.call_tool('reorder_charts', {
        **expected(updated['workspace']), 'ids': [3, 1, 2],
      }))
      deleted = data(await client.call_tool('delete_charts', {
        **expected(reordered['workspace']), 'ids': [2],
      }))
      assert deleted['deleted_ids'] == [2]
      assert data(await client.call_tool('list_charts', {}))['workspace']['managed_chart_ids'] == [3, 1]

  run(exercise())


def test_mcp_conflicts_and_invalid_batches_are_atomic():
  store = DashboardStore(b'Group,Amount\nA,1\nB,2\n')
  mcp = create_mcp(store)

  async def exercise():
    async with Client(mcp) as client:
      inspected = data(await client.call_tool('inspect_dataset', {}))
      analyzed = data(await client.call_tool('analyze_dataset', expected(inspected['workspace'])))
      stale = expected(inspected['workspace'])
      cases = [
        ('create_charts', {**stale, 'definitions': [dict(type='bar', x_column='Group', y_column='Amount')]}),
        ('create_charts', {**expected(analyzed['workspace']), 'definitions': [dict(type='scatter', x_column='Group', y_column='Amount')]}),
        ('delete_charts', {**expected(analyzed['workspace']), 'ids': [99]}),
      ]
      for name, arguments in cases:
        result = await client.call_tool(name, arguments, raise_on_error=False)
        assert result.is_error
        assert 'Traceback' not in result.content[0].text
      assert store.workspace()['revision'] == analyzed['workspace']['revision']
      assert store.workspace()['managed_chart_ids'] == []

  run(exercise())


def test_explicit_replacement_clears_managed_charts_without_reusing_ids():
  store = DashboardStore(b'Group,Amount\nA,1\nB,2\n')
  mcp = create_mcp(store)

  async def exercise():
    async with Client(mcp) as client:
      inspected = data(await client.call_tool('inspect_dataset', {}))
      analyzed = data(await client.call_tool('analyze_dataset', expected(inspected['workspace'])))
      created = data(await client.call_tool('create_charts', {
        **expected(analyzed['workspace']),
        'definitions': [dict(type='bar', x_column='Group', y_column='Amount')],
      }))
      replacement = data(await client.call_tool('analyze_dataset', {
        **expected(created['workspace']),
        'dataset': dict(source='inline', inline_csv='Team,Score\nRed,3\nBlue,5\n'),
      }))
      assert replacement['workspace']['managed_chart_ids'] == []
      next_chart = data(await client.call_tool('create_charts', {
        **expected(replacement['workspace']),
        'definitions': [dict(type='bar', x_column='Team', y_column='Score')],
      }))
      assert next_chart['charts'][0]['id'] == 2

  run(exercise())


def test_browser_reanalyzes_dataset_selected_by_mcp_without_replacing_it():
  store = DashboardStore(b'Group,Amount\nA,1\n')
  app, _, mcp = create_app(store)

  async def select_dataset():
    async with Client(mcp) as client:
      inspected = data(await client.call_tool('inspect_dataset', {}))
      return data(await client.call_tool('analyze_dataset', {
        **expected(inspected['workspace']),
        'dataset': dict(source='inline', inline_csv='Team,Score\nRed,3\nBlue,5\n'),
      }))

  selected = run(select_dataset())
  with TestClient(app) as client:
    response = client.post('/analyze-active', json={
      **expected(selected['workspace']),
      'request_client': 'browser-integration',
      'request_sequence': 1,
      'filter_query': 'Score >= 5',
    })

  assert response.status_code == 200
  assert response.json()['workspace']['active_source'] == 'inline CSV'
  assert response.json()['metadata']['row_count_after_filter'] == 1

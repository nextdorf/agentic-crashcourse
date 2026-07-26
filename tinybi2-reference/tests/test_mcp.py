import asyncio

from fastapi.testclient import TestClient
from fastmcp import Client

from analytics import DashboardStore
from main import app, dashboard_store, mcp
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


def test_tool_contract_and_calls():
  async def exercise():
    async with Client(mcp) as client:
      tools = await client.list_tools()
      by_name = {tool.name: tool for tool in tools}
      assert set(by_name) == {'inspect_dataset', 'analyze_dataset', 'create_chart'}
      assert by_name['inspect_dataset'].annotations.readOnlyHint is True
      assert by_name['analyze_dataset'].annotations.readOnlyHint is False
      assert by_name['create_chart'].annotations.destructiveHint is False
      for tool in tools:
        assert tool.description
        assert tool.outputSchema['type'] == 'object'
        assert tool.outputSchema.get('additionalProperties') is False
        for schema in tool.inputSchema.get('properties', {}).values():
          assert schema.get('description')
      dataset = by_name['inspect_dataset'].inputSchema['properties']['dataset']
      union = next(item for item in dataset['anyOf'] if 'oneOf' in item)
      assert len(union['oneOf']) == 3
      assert {variant['properties']['source']['const'] for variant in union['oneOf']} == {'sample', 'path', 'inline'}
      assert all(variant.get('additionalProperties') is False for variant in union['oneOf'])
      assert by_name['create_chart'].inputSchema['properties']['limit']['minimum'] == 1
      assert by_name['create_chart'].inputSchema['properties']['limit']['maximum'] == 50
      sections = by_name['analyze_dataset'].inputSchema['properties']['sections']
      section_array = next(item for item in sections.get('anyOf', [sections]) if item.get('type') == 'array')
      assert section_array['uniqueItems'] is True

      inspected = await client.call_tool('inspect_dataset', dict(dataset=dict(source='sample')))
      assert not inspected.is_error
      assert data(inspected)['metadata']['row_count'] == 9994

      analyzed = await client.call_tool('analyze_dataset', dict(
        dataset=dict(source='inline', inline_csv='Date,Region,Revenue\n2024-01-01,West,10\n2024-02-01,East,20\n'),
        filter_query="Region == 'West'", sections=['metrics', 'preview'],
      ))
      assert not analyzed.is_error
      assert data(analyzed)['metadata']['row_count_after_filter'] == 1
      assert data(analyzed)['workspace']['last_updated_by'] == 'mcp'

      chart = await client.call_tool('create_chart', dict(
        x_column='Date', y_column='Revenue', filter_query='Revenue >= 10', aggregation='sum',
        chart_type='line', sort_by='label_asc', limit=2,
      ))
      assert not chart.is_error
      assert data(chart)['effective_config']['limit'] == 2
      assert data(chart)['chart']['labels'] == ['2024-01-01', '2024-02-01']

  run(exercise())


def test_browser_to_mcp_and_mcp_to_browser_sharing():
  async def inspect_active():
    async with Client(mcp) as client:
      await client.list_tools()
      inspected = await client.call_tool('inspect_dataset', {})
      analyzed = await client.call_tool('analyze_dataset', {})
      return data(inspected), data(analyzed)

  async def chart_active():
    async with Client(mcp) as client:
      return await client.call_tool('create_chart', dict(
        x_column='Squad', y_column='Points', aggregation='max', chart_type='bar',
        sort_by='value_asc', limit=1,
      ))

  with TestClient(app) as client:
    uploaded = client.post(
      '/analyze',
      files=dict(file=('shared.csv', b'Squad,Points\nComet,41\nNova,17\n', 'text/csv')),
      data=dict(filter_query='', x_column='', y_column='', aggregation='sum', chart_type='auto', sort_by='', limit='20'),
    ).json()
    inspected, analyzed = run(inspect_active())
    assert inspected['inspected_source'] == 'shared.csv'
    assert inspected['metadata']['row_count'] == 2
    assert analyzed['workspace']['active_source'] == 'shared.csv'

    chart = run(chart_active())
    state = client.get('/state').json()
    assert state['workspace']['revision'] == data(chart)['workspace']['revision']
    assert state['workspace']['last_updated_by'] == 'mcp'
    assert state['workspace']['controls']['aggregation'] == 'max'
    assert state['dashboard']['charts'][0] == data(chart)['chart']
    assert state['dashboard']['metrics'] and state['dashboard']['preview']

    client.post('/config', json=dict(show_preview=False))

  async def visibility():
    async with Client(mcp) as client:
      await client.list_tools()
      result = await client.call_tool('inspect_dataset', {})
      return data(result)['workspace']['visibility']

  assert run(visibility())['show_preview'] is False


def test_repairable_mcp_errors_are_atomic():
  isolated_store = DashboardStore(b'Group,Amount\nA,1\nB,2\n')
  isolated_mcp = create_mcp(isolated_store)

  async def exercise():
    async with Client(isolated_mcp) as client:
      await client.list_tools()
      good = await client.call_tool('analyze_dataset', {})
      revision = data(good)['workspace']['revision']
      cases = [
        ('create_chart', dict(x_column='missing', y_column='Amount')),
        ('create_chart', dict(x_column='Group', y_column='missing')),
        ('create_chart', dict(x_column='Group', y_column='Amount', filter_query='not valid !!!')),
        ('create_chart', dict(x_column='Group', y_column='Amount', limit=99)),
        ('inspect_dataset', dict(dataset=dict(source='path', inline_csv='a,b\n1,2'))),
      ]
      for name, arguments in cases:
        result = await client.call_tool(name, arguments, raise_on_error=False)
        assert result.is_error
        message = result.content[0].text
        assert 'Traceback' not in message and '/home/' not in message
      assert isolated_store.workspace()['revision'] == revision

  run(exercise())

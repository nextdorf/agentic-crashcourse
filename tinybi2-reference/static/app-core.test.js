const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('./app-core.js');

test('workspace disposition detects restarts and stale responses', () => {
  const current = { incarnation: 'a', revision: 5 };
  assert.equal(core.workspaceDisposition(current, { incarnation: 'a', revision: 4 }), 'older');
  assert.equal(core.workspaceDisposition(current, { incarnation: 'a', revision: 5 }), 'same');
  assert.equal(core.workspaceDisposition(current, { incarnation: 'b', revision: 0 }), 'reset');
});

test('chart IDs separate automatic and managed namespaces', () => {
  assert.equal(core.chartDomId({ scope: 'automatic', id: 'time' }), 'chart-auto-time');
  assert.equal(core.chartDomId({ scope: 'managed', id: 1 }), 'chart-managed-1');
});

test('builds grouped scatter and heatmap Chart.js configurations', () => {
  const grouped = core.chartConfig({ type: 'bar', title: 'Grouped', labels: ['A'], values: [1] });
  const scatter = core.chartConfig({ type: 'scatter', title: 'Scatter', x_column: 'X', y_column: 'Y', points: [{ x: 1, y: 2 }] });
  const heatmap = core.chartConfig({
    type: 'heatmap', title: 'Heat', x_column: 'Group', y_column: 'Zone',
    x_labels: ['A'], y_labels: ['North'], cells: [{ x: 'A', y: 'North', value: 3 }],
  });

  assert.equal(grouped.type, 'bar');
  assert.deepEqual(scatter.data.datasets[0].data, [{ x: 1, y: 2 }]);
  assert.equal(heatmap.type, 'matrix');
  assert.deepEqual(heatmap.data.datasets[0].data, [{ x: 'A', y: 'North', v: 3 }]);
});

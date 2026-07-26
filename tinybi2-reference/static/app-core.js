(function initCore(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.TinyBICore = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, () => {
  function workspaceDisposition(current, incoming) {
    if (!incoming) return 'missing';
    if (!current || incoming.incarnation !== current.incarnation) return 'reset';
    if (incoming.revision < current.revision) return 'older';
    return incoming.revision === current.revision ? 'same' : 'newer';
  }

  function chartDomId(chart) {
    const scope = chart.scope === 'managed' ? 'managed' : 'auto';
    return `chart-${scope}-${chart.id}`;
  }

  function chartContext(chart) {
    if (chart.type === 'scatter') return `${chart.points.length} numeric pairs.`;
    if (chart.type === 'heatmap') return `${chart.cells.length} aggregated cells.`;
    return `${chart.labels.length} grouped values. ${chart.labels[0] ?? 'No groups'} through ${chart.labels.at(-1) ?? 'no groups'}.`;
  }

  function chartConfig(chart) {
    if (chart.type === 'scatter') {
      return {
        type: 'scatter',
        data: { datasets: [{ label: chart.title, data: chart.points, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.55)', pointRadius: 5 }] },
        options: baseOptions({
          x: { title: { display: true, text: chart.x_column }, grid: { color: 'rgba(15,23,42,.08)' } },
          y: { title: { display: true, text: chart.y_column }, grid: { color: 'rgba(15,23,42,.08)' } },
        }),
      };
    }
    if (chart.type === 'heatmap') {
      const values = chart.cells.map((cell) => cell.value).filter((value) => Number.isFinite(value));
      const maximum = Math.max(...values.map(Math.abs), 1);
      return {
        type: 'matrix',
        data: { datasets: [{
          label: chart.title,
          data: chart.cells.map((cell) => ({ x: cell.x, y: cell.y, v: cell.value })),
          backgroundColor: (context) => heatColor(context.raw?.v, maximum),
          borderColor: 'rgba(255,255,255,.9)', borderWidth: 1,
          width: ({ chart: instance }) => ((instance.chartArea || {}).width || 0) / Math.max(chart.x_labels.length, 1) - 1,
          height: ({ chart: instance }) => ((instance.chartArea || {}).height || 0) / Math.max(chart.y_labels.length, 1) - 1,
        }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (context) => `${context.raw.x} × ${context.raw.y}: ${context.raw.v ?? 'n/a'}` } },
          },
          scales: {
            x: { type: 'category', labels: chart.x_labels, offset: true, grid: { display: false }, title: { display: true, text: chart.x_column } },
            y: { type: 'category', labels: [...chart.y_labels].reverse(), offset: true, grid: { display: false }, title: { display: true, text: chart.y_column } },
          },
        },
      };
    }
    return {
      type: chart.type,
      data: { labels: chart.labels, datasets: [{ label: chart.title, data: chart.values, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.18)', borderWidth: 2, borderRadius: 8, tension: .3, fill: chart.type === 'line' }] },
      options: baseOptions({ x: { grid: { display: false } }, y: { beginAtZero: true } }),
    };
  }

  function baseOptions(scales) {
    return { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales };
  }

  function heatColor(value, maximum) {
    if (!Number.isFinite(value)) return 'rgba(148,163,184,.2)';
    const alpha = .15 + .8 * Math.min(Math.abs(value) / maximum, 1);
    return value < 0 ? `rgba(225,29,72,${alpha})` : `rgba(79,70,229,${alpha})`;
  }

  return { chartConfig, chartContext, chartDomId, heatColor, workspaceDisposition };
}));

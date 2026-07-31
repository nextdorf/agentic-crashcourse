const fileInput = document.querySelector('#fileInput');
const dropzone = document.querySelector('#dropzone');
const sampleButton = document.querySelector('#sampleButton');
const newFileButton = document.querySelector('#newFileButton');
const uploadShell = document.querySelector('#uploadShell');
const loader = document.querySelector('#loader');
const dashboard = document.querySelector('#dashboard');
const errorMessage = document.querySelector('#errorMessage');
const charts = [];

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') fileInput.click();
});
fileInput.addEventListener('change', () => fileInput.files[0] && analyze(fileInput.files[0]));
['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  dropzone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  dropzone.classList.remove('dragging');
}));
dropzone.addEventListener('drop', (event) => {
  const file = event.dataTransfer.files[0];
  if (file) analyze(file);
});
sampleButton.addEventListener('click', async () => {
  setLoading(true);
  try {
    const response = await fetch('/sample-data');
    if (!response.ok) throw new Error('Could not load the sample dataset.');
    analyze(new File([await response.blob()], 'sample_data.csv', { type: 'text/csv' }));
  } catch (error) {
    showError(error.message);
    setLoading(false);
  }
});
newFileButton.addEventListener('click', () => {
  dashboard.hidden = true;
  uploadShell.hidden = false;
  fileInput.value = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

async function analyze(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    showError('Please choose a CSV file.');
    return;
  }
  setLoading(true);
  const body = new FormData();
  body.append('file', file);
  try {
    const response = await fetch('/analyze', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'The file could not be analyzed.');
    renderDashboard(data, file.name);
  } catch (error) {
    showError(error.message);
    uploadShell.hidden = false;
  } finally {
    setLoading(false);
  }
}

function setLoading(active) {
  loader.hidden = !active;
  errorMessage.hidden = true;
  if (active) {
    uploadShell.hidden = true;
    dashboard.hidden = true;
  }
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function renderDashboard(data, filename) {
  document.querySelector('#datasetName').textContent = filename.replace(/\.csv$/i, '');
  renderMetrics(data.metrics);
  renderInsights(data.insights);
  renderCharts(data.charts);
  renderTable(data.columns, data.preview);
  document.querySelector('#metricsSection').hidden = !data.config.metrics;
  document.querySelector('#insightsSection').hidden = !data.config.insights;
  document.querySelector('#chartsSection').hidden = !data.config.charts;
  document.querySelector('#previewSection').hidden = !data.config.preview;
  dashboard.hidden = false;
  dashboard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderMetrics(metrics) {
  const labels = {
    rows: 'Total rows', columns: 'Total columns', numeric_columns: 'Numeric columns',
    categorical_columns: 'Categorical columns', total: 'Total', average: 'Average',
    minimum: 'Minimum', maximum: 'Maximum', best_category: 'Best category', best_date: 'Best date'
  };
  const excluded = new Set(['primary_metric']);
  document.querySelector('#metricsSection').innerHTML = Object.entries(metrics)
    .filter(([key, value]) => !excluded.has(key) && value !== null)
    .map(([key, value]) => `<article class="metric-card"><small>${labels[key] || key}</small><strong>${formatValue(value)}</strong></article>`)
    .join('');
}

function formatValue(value) {
  if (typeof value === 'number') {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  }
  return escapeHtml(String(value));
}

function renderInsights(insights) {
  document.querySelector('#insightsGrid').innerHTML = insights
    .map((insight) => `<div class="insight">${escapeHtml(insight)}</div>`).join('');
}

function renderCharts(chartData) {
  charts.splice(0).forEach((chart) => chart.destroy());
  const section = document.querySelector('#chartsSection');
  section.innerHTML = chartData.map((chart, index) => `
    <section class="panel chart-panel">
      <div class="panel-heading"><span>${escapeHtml(chart.title)}</span><small>${escapeHtml(chart.x)} / ${escapeHtml(chart.y)}</small></div>
      <div class="chart-wrap"><canvas id="chart-${index}"></canvas></div>
    </section>`).join('');

  chartData.forEach((chart, index) => {
    const isRadial = chart.type === 'pie' || chart.type === 'doughnut';
    const radialColors = ['#174f3c', '#286b54', '#43846c', '#6a9f89', '#94b9a9', '#bfd2c9'];
    charts.push(new Chart(document.querySelector(`#chart-${index}`), {
      type: chart.type,
      data: { labels: chart.labels, datasets: [{ label: chart.y, data: chart.values, backgroundColor: isRadial ? chart.labels.map((_, colorIndex) => radialColors[colorIndex % radialColors.length]) : 'rgba(23, 93, 70, .78)', borderColor: isRadial ? '#ffffff' : '#175d46', borderWidth: isRadial ? 2 : 1.5, borderRadius: isRadial ? 0 : 6, tension: .28, fill: false }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: isRadial } }, scales: isRadial ? {} : { x: { grid: { display: false }, ticks: { maxRotation: 40 } }, y: { beginAtZero: true, grid: { color: '#e9ece6' } } } }
    }));
  });
}

function renderTable(columns, rows) {
  const head = `<thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead>`;
  const body = `<tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody>`;
  document.querySelector('#previewTable').innerHTML = head + body;
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = value;
  return element.innerHTML;
}

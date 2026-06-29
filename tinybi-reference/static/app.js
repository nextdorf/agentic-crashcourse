const state = {
  currentFile: null,
  charts: [],
  config: window.initialConfig || {
    show_metrics: true,
    show_charts: true,
    show_preview: true,
    show_insights: true,
  },
};

const elements = {
  dropZone: document.querySelector('#dropZone'),
  fileInput: document.querySelector('#fileInput'),
  sampleBtn: document.querySelector('#sampleBtn'),
  controls: document.querySelector('#controls'),
  status: document.querySelector('#status'),
  metricsSection: document.querySelector('#metricsSection'),
  metrics: document.querySelector('#metrics'),
  chartsSection: document.querySelector('#chartsSection'),
  charts: document.querySelector('#charts'),
  insightsSection: document.querySelector('#insightsSection'),
  insights: document.querySelector('#insights'),
  previewSection: document.querySelector('#previewSection'),
  previewTable: document.querySelector('#previewTable'),
};

function init() {
  syncConfigInputs();

  elements.fileInput.addEventListener('change', () => {
    const [file] = elements.fileInput.files;
    if (file) {
      state.currentFile = file;
      analyzeFile(file);
    }
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove('dragover');
    });
  });

  elements.dropZone.addEventListener('drop', (event) => {
    const [file] = event.dataTransfer.files;
    if (file) {
      state.currentFile = file;
      analyzeFile(file);
    }
  });

  elements.sampleBtn.addEventListener('click', loadSample);
  elements.controls.addEventListener('change', rerunCurrentAnalysis);
  elements.controls.addEventListener('submit', (event) => event.preventDefault());

  document.querySelectorAll('[data-config]').forEach((input) => {
    input.addEventListener('change', updateConfig);
  });
}

function formParams() {
  const data = new FormData(elements.controls);
  for (const [key, value] of [...data.entries()]) {
    if (!value) {
      data.delete(key);
    }
  }
  return data;
}

async function analyzeFile(file) {
  setStatus(`Analyzing ${file.name}...`);
  const data = formParams();
  data.set('file', file);

  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      body: data,
    });
    const result = await parseResponse(response);
    renderDashboard(result);
    setStatus(`Analyzed ${file.name}.`, 'success');
  } catch (error) {
    showError(error);
  }
}

async function loadSample() {
  setStatus('Loading sample data...');
  const query = new URLSearchParams(formParams());
  try {
    const response = await fetch(`/sample-data?${query.toString()}`);
    const result = await parseResponse(response);
    state.currentFile = null;
    renderDashboard(result);
    setStatus('Sample data loaded.', 'success');
  } catch (error) {
    showError(error);
  }
}

function rerunCurrentAnalysis() {
  if (state.currentFile) {
    analyzeFile(state.currentFile);
    return;
  }
  loadSample();
}

async function updateConfig(event) {
  const key = event.target.dataset.config;
  const payload = { [key]: event.target.checked };
  try {
    const response = await fetch('/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await parseResponse(response);
    state.config = result.config;
    applyVisibility();
  } catch (error) {
    showError(error);
  }
}

async function parseResponse(response) {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || 'Request failed.');
  }
  return payload;
}

function renderDashboard(result) {
  state.config = result.config || state.config;
  syncConfigInputs();
  renderMetrics(result.metrics || []);
  renderCharts(result.charts || []);
  renderInsights(result.insights || []);
  renderPreview(result.preview || []);
  applyVisibility();
}

function renderMetrics(metrics) {
  elements.metrics.innerHTML = metrics.map((metric) => `
    <article class="metric-card">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
      <p>${escapeHtml(metric.hint)}</p>
    </article>
  `).join('');
}

function renderCharts(charts) {
  state.charts.forEach((chart) => chart.destroy());
  state.charts = [];
  elements.charts.innerHTML = charts.map((chart) => `
    <article class="chart-card">
      <h3>${escapeHtml(chart.title)}</h3>
      <canvas id="chart-${escapeHtml(chart.id)}"></canvas>
    </article>
  `).join('');

  charts.forEach((chart) => {
    const canvas = document.querySelector(`#chart-${CSS.escape(chart.id)}`);
    const instance = new Chart(canvas, {
      type: chart.type,
      data: {
        labels: chart.labels,
        datasets: [{
          label: chart.title,
          data: chart.values,
          borderColor: '#4f46e5',
          backgroundColor: 'rgba(79, 70, 229, 0.18)',
          borderWidth: 2,
          borderRadius: 10,
          tension: 0.35,
          fill: chart.type === 'line',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true },
        },
      },
    });
    state.charts.push(instance);
  });
}

function renderInsights(insights) {
  elements.insights.innerHTML = insights.map((insight, index) => `
    <article class="insight-card">
      <strong>Insight ${index + 1}</strong>
      <p>${escapeHtml(insight)}</p>
    </article>
  `).join('');
}

function renderPreview(rows) {
  if (!rows.length) {
    elements.previewTable.innerHTML = '';
    return;
  }
  const columns = Object.keys(rows[0]);
  const head = `<thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead>`;
  const body = rows.map((row) => `
    <tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')}</tr>
  `).join('');
  elements.previewTable.innerHTML = `${head}<tbody>${body}</tbody>`;
}

function applyVisibility() {
  toggle(elements.metricsSection, state.config.show_metrics && elements.metrics.children.length);
  toggle(elements.chartsSection, state.config.show_charts && elements.charts.children.length);
  toggle(elements.insightsSection, state.config.show_insights && elements.insights.children.length);
  toggle(elements.previewSection, state.config.show_preview && elements.previewTable.innerHTML);
}

function toggle(element, visible) {
  element.classList.toggle('hidden', !visible);
}

function syncConfigInputs() {
  document.querySelectorAll('[data-config]').forEach((input) => {
    input.checked = Boolean(state.config[input.dataset.config]);
  });
}

function setStatus(message, type = '') {
  elements.status.textContent = message;
  elements.status.className = `status ${type || 'muted'}`;
}

function showError(error) {
  setStatus(error.message, 'error');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

init();

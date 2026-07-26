const state = {
  currentFile: null, charts: [], config: window.initialConfig, revision: 0,
  requestController: null, applyingRemote: false,
};
const elements = Object.fromEntries([
  'dropZone', 'fileInput', 'sampleBtn', 'controls', 'status', 'revision', 'columnRoles',
  'metricsSection', 'metrics', 'chartsSection', 'charts', 'insightsSection', 'insights',
  'previewSection', 'previewTable',
].map((id) => [id, document.querySelector(`#${id}`)]));

function init() {
  syncConfigInputs();
  elements.fileInput.addEventListener('change', () => {
    const [file] = elements.fileInput.files;
    if (file) { state.currentFile = file; analyzeFile(file); }
  });
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((name) => elements.dropZone.addEventListener(name, dragEvent));
  elements.dropZone.addEventListener('drop', (event) => {
    const [file] = event.dataTransfer.files;
    if (file) { state.currentFile = file; analyzeFile(file); }
  });
  elements.sampleBtn.addEventListener('click', loadSample);
  elements.controls.addEventListener('change', () => {
    if (!state.applyingRemote && state.revision) rerunCurrentAnalysis();
  });
  elements.controls.addEventListener('submit', (event) => event.preventDefault());
  document.querySelectorAll('[data-config]').forEach((input) => input.addEventListener('change', updateConfig));
  window.setInterval(pollState, 2500);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollState(); });
}

function dragEvent(event) {
  event.preventDefault();
  elements.dropZone.classList.toggle('dragover', ['dragenter', 'dragover'].includes(event.type));
}

function formParams() { return new FormData(elements.controls); }

async function analyzeFile(file) {
  const data = formParams();
  data.set('file', file);
  await runAnalysis('/analyze', { method: 'POST', body: data }, `Analyzing ${file.name}...`, `Analyzed ${file.name}.`);
}

async function loadSample() {
  const result = await runAnalysis(`/sample-data?${new URLSearchParams(formParams())}`, {}, 'Loading sample data...', 'Sample data loaded.');
  if (result) state.currentFile = null;
}

function rerunCurrentAnalysis() { state.currentFile ? analyzeFile(state.currentFile) : loadSample(); }

async function runAnalysis(url, options, pending, complete) {
  if (state.requestController) state.requestController.abort();
  state.requestController = new AbortController();
  const controller = state.requestController;
  setBusy(true);
  setStatus(pending);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const result = await parseResponse(response);
    if (controller !== state.requestController) return null;
    renderDashboard(result, result.workspace);
    setStatus(complete, 'success');
    return result;
  } catch (error) {
    if (error.name !== 'AbortError') showError(error);
    return null;
  } finally {
    if (controller === state.requestController) { state.requestController = null; setBusy(false); }
  }
}

async function updateConfig(event) {
  const input = event.target;
  const previous = !input.checked;
  try {
    const response = await fetch('/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [input.dataset.config]: input.checked }),
    });
    const result = await parseResponse(response);
    state.config = result.config;
    applyWorkspace(result.workspace);
    applyVisibility();
  } catch (error) { input.checked = previous; showError(error); }
}

async function pollState() {
  if (document.hidden || state.requestController) return;
  try {
    const response = await fetch(`/state?after_revision=${state.revision}`);
    if (response.status === 204) return;
    const payload = await parseResponse(response);
    if (payload.workspace.revision <= state.revision) return;
    state.applyingRemote = true;
    if (payload.dashboard) {
      renderDashboard(payload.dashboard, payload.workspace);
    } else {
      applyWorkspace(payload.workspace);
      syncConfigInputs();
      applyVisibility();
    }
    setStatus(`Workspace synchronized from ${payload.workspace.last_updated_by}.`, 'success');
  } catch (error) { setStatus(`Synchronization paused: ${error.message}`, 'error'); }
  finally { state.applyingRemote = false; }
}

async function parseResponse(response) {
  const text = await response.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || text || `Request failed (${response.status}).`);
  return payload;
}

function renderDashboard(result, workspace) {
  if (workspace && workspace.revision < state.revision) return;
  if (workspace) applyWorkspace(workspace);
  state.config = result.config || workspace?.visibility || state.config;
  syncConfigInputs();
  populateControls(result.columns || {}, workspace?.controls || result.effective_config || result.defaults || {});
  renderRoles(result.columns || {}, result.filter_examples || []);
  renderMetrics(result.metrics || []); renderCharts(result.charts || []);
  renderInsights(result.insights || []); renderPreview(result.preview || []);
  applyVisibility();
}

function applyWorkspace(workspace) {
  if (!workspace || workspace.revision < state.revision) return;
  state.revision = workspace.revision;
  state.config = workspace.visibility || state.config;
  elements.revision.textContent = `Revision ${workspace.revision} · ${workspace.last_updated_by || 'waiting'}${workspace.active_source ? ` · ${workspace.active_source}` : ''}`;
}

function populateControls(columns, controls) {
  state.applyingRemote = true;
  fillSelect(elements.controls.elements.x_column, columns.all || [], controls.x_column, 'Select X column');
  fillSelect(elements.controls.elements.y_column, columns.measures || columns.numeric || [], controls.y_column, 'Select Y measure');
  ['filter_query', 'aggregation', 'chart_type', 'sort_by', 'limit'].forEach((name) => {
    if (controls[name] !== undefined && controls[name] !== null) elements.controls.elements[name].value = controls[name];
    if (name === 'filter_query' && controls[name] === null) elements.controls.elements[name].value = '';
  });
  state.applyingRemote = false;
}

function fillSelect(select, options, selected, placeholder) {
  select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${options.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('')}`;
  select.disabled = !options.length;
  if (selected && options.includes(selected)) select.value = selected;
}

function renderRoles(columns, examples) {
  const role = (label, values) => values?.length ? `<span><strong>${label}:</strong> ${values.map(escapeHtml).join(', ')}</span>` : '';
  elements.columnRoles.innerHTML = [
    role('Dates', columns.dates || columns.date), role('Measures', columns.measures || columns.numeric),
    role('Dimensions', columns.dimensions || columns.categorical), role('Identifiers', columns.identifiers),
    examples[0] ? `<span><strong>Try:</strong> <code>${escapeHtml(examples[0])}</code></span>` : '',
  ].filter(Boolean).join('');
}

function renderMetrics(metrics) {
  elements.metrics.innerHTML = metrics.map((item) => `<article class="metric-card"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.display_value ?? item.value)}</strong><p>${escapeHtml(item.hint)}</p></article>`).join('');
}

function renderCharts(charts) {
  state.charts.forEach((chart) => chart.destroy());
  state.charts = [];
  elements.charts.innerHTML = charts.map((chart) => `<article class="chart-card"><h3>${escapeHtml(chart.title)}</h3><p class="chart-context">${chart.labels.length} grouped values. ${escapeHtml(chart.labels[0] ?? 'No groups')} through ${escapeHtml(chart.labels.at(-1) ?? 'no groups')}.</p><canvas id="chart-${escapeHtml(chart.id)}" role="img" aria-label="${escapeHtml(chart.title)}"></canvas></article>`).join('');
  charts.forEach((chart) => {
    const canvas = document.querySelector(`#chart-${CSS.escape(chart.id)}`);
    state.charts.push(new Chart(canvas, {
      type: chart.type,
      data: { labels: chart.labels, datasets: [{ label: chart.title, data: chart.values, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.18)', borderWidth: 2, borderRadius: 8, tension: .3, fill: chart.type === 'line' }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true } } },
    }));
  });
}

function renderInsights(insights) { elements.insights.innerHTML = insights.map((value, index) => `<article class="insight-card"><strong>Observation ${index + 1}</strong><p>${escapeHtml(value)}</p></article>`).join(''); }
function renderPreview(rows) {
  if (!rows.length) { elements.previewTable.innerHTML = ''; return; }
  const columns = Object.keys(rows[0]);
  elements.previewTable.innerHTML = `<thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody>`;
}
function setBusy(busy) { [...elements.controls.elements, elements.fileInput, elements.sampleBtn].forEach((control) => { control.disabled = busy; }); elements.controls.setAttribute('aria-busy', String(busy)); }
function applyVisibility() {
  toggle(elements.metricsSection, state.config.show_metrics && elements.metrics.children.length);
  toggle(elements.chartsSection, state.config.show_charts && elements.charts.children.length);
  toggle(elements.insightsSection, state.config.show_insights && elements.insights.children.length);
  toggle(elements.previewSection, state.config.show_preview && elements.previewTable.innerHTML);
}
function toggle(element, visible) { element.classList.toggle('hidden', !visible); }
function syncConfigInputs() { document.querySelectorAll('[data-config]').forEach((input) => { input.checked = Boolean(state.config[input.dataset.config]); }); }
function setStatus(message, type = '') { elements.status.textContent = message; elements.status.className = `status ${type || 'muted'}`; }
function showError(error) { setStatus(error.message, 'error'); }
function escapeHtml(value) { return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;'); }

init();

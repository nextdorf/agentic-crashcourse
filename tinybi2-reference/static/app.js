const state = {
  charts: [], config: window.initialConfig, workspace: window.initialWorkspace,
  requestController: null, applyingRemote: false,
  requestClient: globalThis.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random()}`,
  requestSequence: 0,
};
const elements = Object.fromEntries([
  'dropZone', 'fileInput', 'sampleBtn', 'controls', 'status', 'revision', 'columnRoles',
  'metricsSection', 'metrics', 'chartsSection', 'charts', 'insightsSection', 'insights',
  'previewSection', 'previewTable',
].map((id) => [id, document.querySelector(`#${id}`)]));

function init() {
  syncConfigInputs();
  applyWorkspace(state.workspace);
  elements.fileInput.addEventListener('change', () => {
    const [file] = elements.fileInput.files;
    if (file) analyzeFile(file);
  });
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((name) => elements.dropZone.addEventListener(name, dragEvent));
  elements.dropZone.addEventListener('drop', (event) => {
    const [file] = event.dataTransfer.files;
    if (file) analyzeFile(file);
  });
  elements.sampleBtn.addEventListener('click', loadSample);
  elements.controls.addEventListener('change', () => {
    if (!state.applyingRemote && state.workspace.active_source) rerunCurrentAnalysis();
  });
  elements.controls.addEventListener('submit', (event) => event.preventDefault());
  document.querySelectorAll('[data-config]').forEach((input) => input.addEventListener('change', updateConfig));
  window.setInterval(pollState, 2500);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollState(); });
  pollState();
}

function dragEvent(event) {
  event.preventDefault();
  elements.dropZone.classList.toggle('dragover', ['dragenter', 'dragover'].includes(event.type));
}

function versionPayload() {
  return { expected_incarnation: state.workspace.incarnation, expected_revision: state.workspace.revision };
}

function analysisVersionPayload() {
  state.requestSequence += 1;
  return { ...versionPayload(), request_client: state.requestClient, request_sequence: state.requestSequence };
}

function controlsPayload() {
  return Object.fromEntries(new FormData(elements.controls));
}

async function analyzeFile(file) {
  const data = new FormData(elements.controls);
  data.set('file', file);
  Object.entries(analysisVersionPayload()).forEach(([key, value]) => data.set(key, value));
  await runAnalysis('/analyze', { method: 'POST', body: data }, `Analyzing ${file.name}...`, `Analyzed ${file.name}.`);
}

async function loadSample() {
  await runAnalysis('/sample-data', jsonRequest({ ...analysisVersionPayload(), ...controlsPayload() }), 'Loading sample data...', 'Sample data loaded.');
}

async function rerunCurrentAnalysis() {
  await runAnalysis('/analyze-active', jsonRequest({ ...analysisVersionPayload(), ...controlsPayload() }), 'Updating active analysis...', 'Active analysis updated.');
}

function jsonRequest(body) {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

async function runAnalysis(url, options, pending, complete) {
  if (state.requestController) state.requestController.abort();
  state.requestController = new AbortController();
  const controller = state.requestController;
  setBusy(true);
  setStatus(pending);
  try {
    let currentOptions = options;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetch(url, { ...currentOptions, signal: controller.signal });
        const result = await parseResponse(response);
        if (controller !== state.requestController) return null;
        renderDashboard(result, result.workspace);
        setStatus(complete, 'success');
        return result;
      } catch (error) {
        if (error.status !== 409 || attempt || controller !== state.requestController) throw error;
        await refreshAfterConflict();
        currentOptions = refreshRequestVersion(currentOptions);
      }
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      showError(error);
    }
    return null;
  } finally {
    if (controller === state.requestController) { state.requestController = null; setBusy(false); }
  }
}

function refreshRequestVersion(options) {
  if (options.body instanceof FormData) {
    options.body.set('expected_incarnation', state.workspace.incarnation);
    options.body.set('expected_revision', state.workspace.revision);
    return options;
  }
  const body = JSON.parse(options.body);
  return { ...options, body: JSON.stringify({ ...body, ...versionPayload() }) };
}

async function updateConfig(event) {
  const input = event.target;
  const previous = !input.checked;
  try {
    const response = await fetch('/config', jsonRequest({ ...versionPayload(), [input.dataset.config]: input.checked }));
    const result = await parseResponse(response);
    if (!applyWorkspace(result.workspace)) return;
    state.config = result.config;
    syncConfigInputs();
    applyVisibility();
  } catch (error) {
    input.checked = previous;
    if (error.status === 409) await refreshAfterConflict();
    showError(error);
  }
}

async function pollState() {
  if (document.hidden || state.requestController) return;
  try {
    const query = new URLSearchParams({ after_revision: state.workspace.revision, incarnation: state.workspace.incarnation });
    const response = await fetch(`/state?${query}`);
    if (response.status === 204) return;
    const payload = await parseResponse(response);
    applyStatePayload(payload, true);
  } catch (error) { setStatus(`Synchronization paused: ${error.message}`, 'error'); }
}

async function refreshAfterConflict() {
  try {
    const response = await fetch('/state');
    applyStatePayload(await parseResponse(response), true);
  } catch (error) { setStatus(`Could not refresh workspace: ${error.message}`, 'error'); }
}

function applyStatePayload(payload, remote) {
  const disposition = TinyBICore.workspaceDisposition(state.workspace, payload.workspace);
  if (disposition === 'older') return;
  state.applyingRemote = true;
  if (disposition === 'reset' && !payload.dashboard) clearDashboard();
  if (payload.dashboard) renderDashboard(payload.dashboard, payload.workspace);
  else applyWorkspace(payload.workspace);
  syncConfigInputs();
  applyVisibility();
  state.applyingRemote = false;
  if (remote) setStatus(`Workspace synchronized from ${payload.workspace.last_updated_by || 'server'}.`, 'success');
}

function clearDashboard() {
  state.charts.forEach((chart) => chart.destroy());
  state.charts = [];
  elements.metrics.innerHTML = '';
  elements.charts.innerHTML = '';
  elements.insights.innerHTML = '';
  elements.previewTable.innerHTML = '';
  elements.columnRoles.textContent = 'Detected column roles appear after analysis.';
  elements.controls.reset();
  fillSelect(elements.controls.elements.x_column, [], null, 'Analyze data first');
  fillSelect(elements.controls.elements.y_column, [], null, 'Analyze data first');
}

async function parseResponse(response) {
  const text = await response.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = {}; }
  if (!response.ok) {
    const error = new Error(payload.detail || text || `Request failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function renderDashboard(result, workspace) {
  const disposition = TinyBICore.workspaceDisposition(state.workspace, workspace);
  if (disposition === 'older') return;
  if (workspace) applyWorkspace(workspace);
  state.config = result.config || workspace?.visibility || state.config;
  syncConfigInputs();
  populateControls(result.columns || {}, workspace?.requested_controls || result.requested_config || {});
  renderRoles(result.columns || {}, result.filter_examples || []);
  renderMetrics(result.metrics || []); renderCharts(result.charts || []);
  renderInsights(result.insights || []); renderPreview(result.preview || []);
  applyVisibility();
}

function applyWorkspace(workspace) {
  const disposition = TinyBICore.workspaceDisposition(state.workspace, workspace);
  if (disposition === 'older' || disposition === 'missing') return false;
  state.workspace = workspace;
  state.config = workspace.visibility || state.config;
  elements.revision.textContent = `Revision ${workspace.revision} · ${workspace.last_updated_by || 'waiting'}${workspace.active_source ? ` · ${workspace.active_source}` : ''}`;
  return true;
}

function populateControls(columns, controls) {
  state.applyingRemote = true;
  fillSelect(elements.controls.elements.x_column, columns.all || [], controls.x_column, 'Select X column');
  fillSelect(elements.controls.elements.y_column, columns.measures || columns.numeric || [], controls.y_column, 'Select Y measure');
  ['filter_query', 'aggregation', 'chart_type', 'sort_by', 'limit'].forEach((name) => {
    if (controls[name] !== undefined && controls[name] !== null) elements.controls.elements[name].value = controls[name];
    if (['filter_query', 'sort_by'].includes(name) && controls[name] === null) elements.controls.elements[name].value = '';
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
  elements.charts.innerHTML = charts.map((chart) => `<article class="chart-card"><h3>${escapeHtml(chart.title)}</h3><p class="chart-context">${escapeHtml(TinyBICore.chartContext(chart))}</p><canvas id="${escapeHtml(TinyBICore.chartDomId(chart))}" role="img" aria-label="${escapeHtml(chart.title)}"></canvas></article>`).join('');
  charts.forEach((chart) => {
    const canvas = document.querySelector(`#${CSS.escape(TinyBICore.chartDomId(chart))}`);
    if (canvas) state.charts.push(new Chart(canvas, TinyBICore.chartConfig(chart)));
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

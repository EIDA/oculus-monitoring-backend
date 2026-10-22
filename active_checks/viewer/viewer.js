// viewer/viewer.js
import { renderSummary, renderResultsTable, renderDetail, renderIndex, runRequest, sortRecords } from './viewer.core.js';

const $ = sel => document.querySelector(sel);
const state = { report: null, filter: { onlyInconsistent: true, direction: 'both', psd: 'all', search: '' }, sort: { key: 'gap', dir: 'desc' } };

function paint() {
  $('#summary').innerHTML = renderSummary(state.report.summary, state.report.results);
  $('#results').innerHTML = renderResultsTable(sortRecords(state.report.results, state.sort.key, state.sort.dir), state.filter, state.sort);
}

function setSort(key) {
  if (state.sort.key === key) state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
  else state.sort = { key, dir: key === 'gap' ? 'desc' : 'asc' };
  paint();
}

function wire() {
  $('#onlyInc').addEventListener('change', e => { state.filter.onlyInconsistent = e.target.checked; paint(); });
  $('#dir').addEventListener('change', e => { state.filter.direction = e.target.value; paint(); });
  $('#psd').addEventListener('change', e => { state.filter.psd = e.target.value; paint(); });
  $('#search').addEventListener('input', e => { state.filter.search = e.target.value; paint(); });
  $('#results').addEventListener('click', e => {
    const th = e.target.closest('th[data-sort]');
    if (th) { setSort(th.dataset.sort); return; }
    const tr = e.target.closest('tr[data-index]'); if (!tr) return;
    const rec = state.report.results.find(r => String(r.index) === tr.dataset.index);
    const detail = $('#detail');
    detail.innerHTML = renderDetail(rec);
    tr.classList.add('sel');
    $('#results').querySelectorAll('tr.sel').forEach(o => { if (o !== tr) o.classList.remove('sel'); });
    detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  $('#detail').addEventListener('click', async e => {
    const copy = e.target.closest('button[data-copy]');
    if (copy) {
      try { await navigator.clipboard.writeText(copy.dataset.copy); copy.textContent = 'copied'; setTimeout(() => copy.textContent = 'copy', 1200); }
      catch { copy.textContent = 'copy failed'; }
      return;
    }
    const b = e.target.closest('button[data-kind]'); if (!b) return;
    // clear any previous result for this button so re-runs don't stack
    let sib = b.nextElementSibling;
    while (sib && sib.classList && (sib.classList.contains('badge-data') || sib.classList.contains('result'))) {
      const next = sib.nextElementSibling; sib.remove(); sib = next;
    }
    b.textContent = '…';
    const r = await runRequest(b.dataset.kind, b.dataset.url, fetch);
    const label = !r.ok ? 'FAILED' : r.hasData ? 'HAS DATA' : 'NO DATA';
    const cls = !r.ok ? 'err' : r.hasData ? 'yes' : 'no';
    b.insertAdjacentHTML('afterend', `<span class="badge-data ${cls}">${label}</span><span class="result"> ${r.summary}</span>`);
    b.textContent = `Run ${b.dataset.kind}`;
  });
}

function loaderHTML(msg) {
  return `<section class="loader">
    <h1>EIDA consistency viewer</h1>
    <p>${msg}</p>
    <form id="loadForm" class="loadrow">
      <input id="loadUrl" type="url" placeholder="paste a report .json URL (e.g. an Oculus report)">
      <button type="submit">Load URL</button>
    </form>
    <div id="drop" class="drop">Drop a report <code>.json</code> here, or
      <label class="filebtn">choose a file<input id="loadFile" type="file" accept=".json,application/json" hidden></label></div>
  </section>`;
}

function readFile(file) {
  const r = new FileReader();
  r.onload = () => {
    let obj; try { obj = JSON.parse(r.result); } catch { showError(`“${file.name}” is not valid JSON.`); return; }
    if (!obj || !obj.summary || !Array.isArray(obj.results)) { showError(`“${file.name}” is not an EIDA consistency report.`); return; }
    showReport(obj);
  };
  r.onerror = () => showError(`Could not read “${file.name}”.`);
  r.readAsText(file);
}

function showError(msg) {
  $('#toolbar').style.display = 'none';
  $('#summary').innerHTML = '';
  $('#detail').innerHTML = '';
  $('#results').innerHTML = loaderHTML(msg);
  wireLoader();
}

function showReport(report) {
  state.report = report;
  $('#detail').innerHTML = '';
  $('#toolbar').style.display = '';
  // The PSD filter stays in place for pre-PSD reports — same toolbar either way —
  // but there is nothing to select, so it is disabled rather than hidden.
  const hasPsd = report.results.some(r => r.psd_status != null);
  const psd = $('#psd');
  psd.disabled = !hasPsd;
  psd.title = hasPsd ? '' : 'This report was produced before the PSD check existed';
  if (!hasPsd) psd.value = 'all';
  // Take the filter state from the controls rather than assuming the defaults:
  // browsers restore form state across a reload, which would otherwise leave the
  // toolbar showing one thing and the table filtered by another.
  state.filter = {
    onlyInconsistent: $('#onlyInc').checked,
    direction: $('#dir').value,
    psd: psd.value,
    search: $('#search').value,
  };
  wire();
  paint();
}

function wireLoader() {
  const form = $('#loadForm');
  if (form) form.addEventListener('submit', e => {
    e.preventDefault();
    const u = $('#loadUrl').value.trim();
    if (u) location.search = '?report=' + encodeURIComponent(u);
  });
  const file = $('#loadFile');
  if (file) file.addEventListener('change', e => { const f = e.target.files[0]; if (f) readFile(f); });
}

function wireDragAndDrop() {
  const stop = e => { e.preventDefault(); };
  window.addEventListener('dragover', e => { stop(e); const d = $('#drop'); if (d) d.classList.add('over'); });
  window.addEventListener('dragleave', () => { const d = $('#drop'); if (d) d.classList.remove('over'); });
  window.addEventListener('drop', e => {
    stop(e);
    const d = $('#drop'); if (d) d.classList.remove('over');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) readFile(f);
  });
}

async function showLanding() {
  $('#toolbar').style.display = 'none';
  $('#summary').innerHTML = '';
  let list = '';
  try {
    const idx = await (await fetch('index.json')).json();
    const entries = Array.isArray(idx) ? idx : (idx.reports || []);
    if (entries.length) list = renderIndex(entries);
  } catch { /* no manifest yet — Oculus may publish one later */ }
  $('#results').innerHTML = list + loaderHTML(list ? 'Or load another report:' : 'No reports listed yet. Load one by URL or file, or open one from Oculus.');
  wireLoader();
}

async function main() {
  wireDragAndDrop();
  const url = new URLSearchParams(location.search).get('report');
  if (!url) { await showLanding(); return; }
  let report;
  try { report = await (await fetch(url)).json(); }
  catch { showError('Could not load that report. Check the URL (and CORS if it is on another host).'); return; }
  showReport(report);
}
main();

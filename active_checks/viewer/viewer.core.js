export function queryTime(iso) {
  return String(iso ?? '').replace('+00:00', '').replace('Z', '');
}

export function swapQueryTime(url, key, value) {
  const re = new RegExp(`([?&]${key}=)[^&]*`);
  return url.replace(re, (_, p1) => p1 + value);
}

// The dataselect URL for a record: the stored one, or — for older reports that
// only kept the availability `url` — derived from it (swap the service path and
// the start/end param names, narrow location/channel to this stream).
export function buildDataselectUrl(record) {
  if (record.dataselect_url) return record.dataselect_url;
  if (!record.url) return null;
  let u; try { u = new URL(record.url); } catch { return null; }
  if (!u.pathname.includes('/availability/')) return null;
  const host = u.origin + u.pathname.replace('/availability/', '/dataselect/');
  const p = u.searchParams;
  const net = record.network ?? p.get('network') ?? '';
  const sta = record.station ?? p.get('station') ?? '';
  let loc = record.location ?? p.get('location') ?? '';
  if (loc === '*') loc = '';
  const cha = record.channel ?? p.get('channel') ?? '';
  const start = p.get('start') ?? queryTime(record.starttime);
  const end = p.get('end') ?? queryTime(record.endtime);
  return `${host}?network=${net}&station=${sta}&location=${loc}&channel=${cha}&starttime=${start}&endtime=${end}&nodata=204`;
}

export function gapQueries(record, gap) {
  const gs = queryTime(gap.start), ge = queryTime(gap.end);
  const av = record.url
    ? swapQueryTime(swapQueryTime(record.url, 'start', gs), 'end', ge) : null;
  const dsBase = buildDataselectUrl(record);
  const ds = dsBase
    ? swapQueryTime(swapQueryTime(dsBase, 'starttime', gs), 'endtime', ge) : null;
  return { availability: av, dataselect: ds };
}

export function recordDirections(record) {
  const s = new Set();
  for (const m of record.mismatch || []) if (m.who) s.add(m.who);
  return s;
}

export function matchesFilter(record, filter) {
  // The PSD selector narrows the rows already on screen rather than overriding
  // "only inconsistent", so the checkbox always means the same thing. PSD
  // findings on availability/dataselect-consistent rows appear once it is off.
  const psdSel = filter.psd && filter.psd !== 'all' ? filter.psd : null;
  if (filter.onlyInconsistent && record.consistent !== false) return false;
  if (psdSel && psdBucket(record) !== psdSel) return false;
  if (filter.direction && filter.direction !== 'both') {
    if (!recordDirections(record).has(filter.direction)) return false;
  }
  if (filter.search) {
    const nslc = `${record.network}.${record.station}.${record.location}.${record.channel}`.toLowerCase();
    if (!nslc.includes(filter.search.toLowerCase())) return false;
  }
  return true;
}

function _parseUTC(iso) { return Date.parse(/[Z+]/.test(iso) ? iso : iso + 'Z'); }

function _sec(iso, t0) { return (_parseUTC(iso) - t0) / 1000; }

function _fmtTime(iso) { return queryTime(iso).replace('T', ' ').replace(/\.\d+$/, ''); }

// Map [start,end] pairs to clamped {x0,x1} fractions of the window, keeping the
// original ISO strings for tooltips.
function _segs(windowStart, windowEnd, pairs) {
  const t0 = _parseUTC(windowStart), t1 = _parseUTC(windowEnd);
  if (!(t1 > t0)) return [];
  const total = t1 - t0;
  return (pairs || []).map(([a, b]) => ({
    x0: Math.max(0, Math.min(1, (_parseUTC(a) - t0) / total)),
    x1: Math.max(0, Math.min(1, (_parseUTC(b) - t0) / total)),
    a, b,
  })).filter(s => s.x1 > s.x0);
}

export function fmtDuration(sec) {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  if (sec < 60) return `${sec}s`;
  const units = [['d', 86400], ['h', 3600], ['m', 60], ['s', 1]];
  const parts = [];
  let r = sec;
  for (const [label, size] of units) {
    const v = Math.floor(r / size);
    if (v) { parts.push(`${v}${label}`); r -= v * size; }
    if (parts.length === 2) break;
  }
  return parts.join(' ') || '0s';
}

export function gapStats(record) {
  const ms = record.mismatch || [];
  let max = 0;
  for (const m of ms) {
    const d = (_parseUTC(m.end) - _parseUTC(m.start)) / 1000;
    if (d > max) max = d;
  }
  return { count: ms.length, maxGap: max };
}

export function timelineModel(windowStart, windowEnd, avail, ds, mismatch) {
  const t0 = _parseUTC(windowStart), t1 = _parseUTC(windowEnd);
  if (!(t1 > t0)) return { segments: [], boundaries: [] };
  const total = (t1 - t0) / 1000;
  const toIv = arr => (arr || []).map(([a, b]) => [_sec(a, t0), _sec(b, t0)]).filter(([a, b]) => b > a);
  const A = toIv(avail), D = toIv(ds);
  const cov = (iv, x) => iv.some(([a, b]) => a <= x && x < b);
  const pts = new Set([0, total]);
  for (const [a, b] of [...A, ...D]) { if (a > 0 && a < total) pts.add(a); if (b > 0 && b < total) pts.add(b); }
  const sorted = [...pts].sort((p, q) => p - q);
  const segments = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i], b = sorted[i + 1], mid = (a + b) / 2;
    const inA = cov(A, mid), inD = cov(D, mid);
    const kind = inA && inD ? 'both' : inA ? 'availability' : inD ? 'dataselect' : 'none';
    segments.push({ x0: a / total, x1: b / total, kind });
  }
  const gaps = [...(mismatch || [])].sort((m, n) => _parseUTC(m.start) - _parseUTC(n.start));
  const boundaries = [];
  for (let i = 0; i < gaps.length - 1; i++) {
    const e = _sec(gaps[i].end, t0), s = _sec(gaps[i + 1].start, t0);
    const b = ((e + s) / 2) / total;
    if (b >= 0 && b <= 1) boundaries.push(b);
  }
  return { segments, boundaries };
}

export function timelineAscii(windowStart, windowEnd, avail, ds, mismatch, width = 58) {
  const t0 = _parseUTC(windowStart), t1 = _parseUTC(windowEnd);
  if (!(t1 > t0)) return '';
  const total = (t1 - t0) / 1000;
  const toIv = arr => (arr || []).map(([a, b]) => [_sec(a, t0), _sec(b, t0)]).filter(([a, b]) => b > a);
  const A = toIv(avail), D = toIv(ds);
  const cov = (iv, i) => { const cs = i * total / width, ce = (i + 1) * total / width; return iv.some(([a, b]) => Math.max(cs, a) < Math.min(ce, b) - 1e-9); };
  const out = [];
  for (let i = 0; i < width; i++) { const a = cov(A, i), d = cov(D, i); out.push(a && d ? '█' : a ? '▼' : d ? '▲' : '·'); }
  const gaps = [...(mismatch || [])].sort((m, n) => _parseUTC(m.start) - _parseUTC(n.start));
  for (let i = 0; i < gaps.length - 1; i++) {
    const e = _sec(gaps[i].end, t0), s = _sec(gaps[i + 1].start, t0);
    const cell = Math.min(width - 1, Math.max(0, Math.floor(((e + s) / 2) / total * width)));
    out[cell] = '|';
  }
  return out.join('');
}

// Fallback timeline for reports without `coverage`: one "request window" track
// with the mismatch gaps marked. Returns an SVG string (empty if no usable
// window or no gaps).
export function timelineGapsSVG(windowStart, windowEnd, mismatch) {
  const X0 = 80, X1 = 988, W = X1 - X0, Y = 18, LH = 22;
  if (!(_parseUTC(windowEnd) > _parseUTC(windowStart))) return '';
  const gaps = _segs(windowStart, windowEnd, (mismatch || []).map(m => [m.start, m.end]));
  if (!gaps.length) return '';
  const xf = f => (X0 + f * W).toFixed(1);
  const wd = (a, b) => Math.max(1, (b - a) * W).toFixed(1);
  const bands = gaps.map(s =>
    `<rect class="tl-gap-solid" x="${xf(s.x0)}" y="${Y}" width="${wd(s.x0, s.x1)}" height="${LH}" rx="2"><title>gap: ${esc(_fmtTime(s.a))} → ${esc(_fmtTime(s.b))}</title></rect>`).join('');
  // No hatch here: this band is solid --bad, already far darker than the track,
  // so it survives red-green CVD on lightness alone. Hatching red-on-red would
  // be invisible. The coverage timeline's translucent overlay does need it.
  return `<svg class="tlsvg" viewBox="0 0 1000 64" role="img" aria-label="gap timeline">
    <text class="tl-lane" x="8" y="${Y + 15}">Window</text>
    <rect class="tl-track" x="${X0}" y="${Y}" width="${W}" height="${LH}" rx="2"></rect>
    ${bands}
    <line class="tl-axis" x1="${X0}" y1="48" x2="${X1}" y2="48"></line>
    <text class="tl-lab" x="${X0}" y="60">${esc(_fmtTime(windowStart))}</text>
    <text class="tl-lab" x="${X1}" y="60" text-anchor="end">${esc(_fmtTime(windowEnd))}</text>
  </svg>`;
}

// PSD coverage answers as CSV with a header row; count the data rows.
const _psdRows = text => Math.max(0, (text || '').trim().split('\n')
  .filter(l => l && !l.startsWith('#')).length - 1);

export function summariseRequest(kind, status, bodyText, byteLength) {
  if (kind === 'availability') {
    const n = (bodyText || '').split('\n').filter(l => l && !l.startsWith('#')).length;
    return `HTTP ${status} — ${n} span${n === 1 ? '' : 's'}`;
  }
  if (kind === 'psd') {
    if (status === 204 || !(bodyText || '').trim()) return `HTTP ${status} — no data`;
    const n = _psdRows(bodyText);
    return `HTTP ${status} — ${n} PSD record${n === 1 ? '' : 's'}`;
  }
  if (status === 204) return `HTTP 204 — no data`;
  return `HTTP ${status} — ${byteLength} bytes`;
}

export async function runRequest(kind, url, fetchImpl) {
  try {
    const res = await fetchImpl(url);
    if (kind === 'availability') {
      const text = await res.text();
      const n = (text || '').split('\n').filter(l => l && !l.startsWith('#')).length;
      return { ok: true, status: res.status, hasData: res.status === 200 && n > 0, summary: summariseRequest(kind, res.status, text, 0) };
    }
    if (kind === 'psd') {
      const text = await res.text();
      return { ok: true, status: res.status, hasData: res.status === 200 && _psdRows(text) > 0, summary: summariseRequest(kind, res.status, text, 0) };
    }
    const buf = await res.arrayBuffer();
    return { ok: true, status: res.status, hasData: res.status === 200 && buf.byteLength > 0, summary: summariseRequest(kind, res.status, '', buf.byteLength) };
  } catch {
    return { ok: false, status: 0, hasData: false, summary: 'request failed' };
  }
}

const DIR_LABEL = {
  availability: '▼ Availability: data · Dataselect: NO DATA',
  dataselect: '▲ Availability: NO DATA · Dataselect: data',
};
// Short word tags for the results table (which service actually has the data).
const DIR_TAG = {
  availability: '▼ Avail only',
  dataselect: '▲ Data only',
};
// Plain-language phrasing for the detail lead sentence.
const DIR_PHRASE = {
  availability: 'availability reported data but dataselect returned none',
  dataselect: 'dataselect returned data but availability reported none',
};

// The row verdict, in words, so the table never shows a bare glyph or a
// misleading "OK" for an inconsistent row.
export function recordVerdict(record) {
  if (record.consistent === false) return { cls: 'bad', text: 'Inconsistent' };
  if (record.consistent === true) return { cls: 'ok', text: 'Consistent' };
  return { cls: 'mut', text: 'Skipped' };
}

// One plain sentence describing what a record's finding is.
export function explainRecord(record) {
  if (record.consistent === true)
    return { cls: 'ok', text: '✔ Consistent — availability and dataselect agree across the requested window.' };
  if (record.consistent !== false)
    return { cls: 'mut', text: `— Skipped${record.consistency_reason ? ': ' + record.consistency_reason : ''}.` };
  const gaps = record.mismatch || [];
  const phrase = [...recordDirections(record)].map(w => DIR_PHRASE[w] || w).join('; ')
    || 'availability and dataselect disagree on whether data exists';
  if (gaps.length === 1) {
    const m = gaps[0], dur = fmtDuration((_parseUTC(m.end) - _parseUTC(m.start)) / 1000);
    return { cls: 'bad', text: `⚠ Inconsistency: for ${dur} (${_fmtTime(m.start)} → ${_fmtTime(m.end)}), ${phrase}.` };
  }
  const total = gaps.reduce((s, m) => s + (_parseUTC(m.end) - _parseUTC(m.start)) / 1000, 0);
  return { cls: 'bad', text: `⚠ Inconsistency: across ${gaps.length} intervals (${fmtDuration(total)} total), ${phrase}.` };
}
// ── PSD (Availability / Dataselect / PSD triangle) ────────────────────────
// A record has PSD info only when the run checked it (psd_status set).
export function psdChecked(record) {
  return record && record.psd_status != null;
}

// The PSD verdict, in words, gated by the 2024-01-01 obligation: a missing PSD
// on/after 2024 is a violation; before 2024 it's an informational gap.
export function psdVerdict(record) {
  if (!psdChecked(record)) return null;
  const st = record.psd_status;
  if (st === 'Unsupported') return { kind: 'unsupported', cls: 'mut', short: 'n/a', text: 'PSD n/a — this node runs no PSD service' };
  if (st === 'Skipped') return { kind: 'skipped', cls: 'mut', short: 'skipped', text: 'PSD skipped — the check did not complete (transient)' };
  // PSD published for a day the archive has no data for — the reverse finding.
  if (st === 'Orphan') return { kind: 'orphan', cls: 'info', short: 'PSD without data', text: 'PSD without data — a PSD exists for a day the archive holds nothing for' };
  // Missing PSD is the same fact either side of 2024-01-01; only the obligation
  // differs, and the glyph is what says which: ✖ must fix, ⚠ informational.
  if (record.psd_consistent === false)
    return record.psd_required
      ? { kind: 'violation', cls: 'bad', short: '✖ must fix ≥2024', text: 'PSD violation — data on/after 2024-01-01 with no PSD published' }
      : { kind: 'pregap', cls: 'warn', short: '⚠ pre-2024 gap', text: 'pre-2024 PSD gap — the same finding, but PSD was not yet required' };
  return { kind: 'ok', cls: 'ok', short: 'consistent', text: 'PSD consistent' };
}

// The two filter buckets. n/a (unsupported/skipped) is neither: nothing was
// owed and nothing was learned, so those rows show only under "PSD: all".
const _PSD_INCONSISTENT = new Set(['violation', 'pregap', 'orphan']);
export function psdBucket(record) {
  const v = psdVerdict(record);
  if (!v) return null;
  if (v.kind === 'ok') return 'consistent';
  return _PSD_INCONSISTENT.has(v.kind) ? 'inconsistent' : null;
}

// "open" or "closed <date>", straight from the channel epoch metadata. A fact,
// not an interpretation -- whether a closed epoch's missing PSD matters is for
// the reader to weigh against the 2024-01-01 requirement, shown separately.
export function channelEpochState(record) {
  const end = record && record.channel_epoch_end;
  return end ? `closed ${String(end).slice(0, 10)}` : 'open';
}

const _TRI = { av: ['▼', '▽'], ds: ['▲', '△'], psd: ['▶', '▷'] };
// Filled/hollow triangle triad string: filled=present, hollow=absent, '?'=unknown.
export function psdTriad(record) {
  const g = (pair, present) => present == null ? '?' : (present ? pair[0] : pair[1]);
  return `${g(_TRI.av, !!record.available)} ${g(_TRI.ds, !!record.dataselect_success)} `
    + `${g(_TRI.psd, psdChecked(record) ? !!record.psd_present : null)}`;
}

// Roll up the PSD dimension across the records for the summary header.
const _PSD_BUCKET = { violation: 'violations', pregap: 'pregaps', orphan: 'orphans', unsupported: 'unsupported', skipped: 'skipped', ok: 'consistent' };
export function psdCounts(results) {
  const c = { checked: 0, consistent: 0, violations: 0, pregaps: 0, orphans: 0, unsupported: 0, skipped: 0 };
  for (const r of results || []) {
    if (!psdChecked(r)) continue;
    c.checked++;
    c[_PSD_BUCKET[psdVerdict(r).kind]]++;
  }
  return c;
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = u => (/^https?:\/\//i.test(String(u ?? '')) ? String(u) : '');

// Graphical two-lane coverage timeline: an Availability lane and a Dataselect
// lane over the request window, with mismatch regions highlighted. Returns an
// SVG string (empty on a degenerate window). Scales to its container width.
export function timelineSVG(windowStart, windowEnd, avail, ds, mismatch) {
  const X0 = 80, X1 = 988, W = X1 - X0, AVY = 16, DSY = 46, LH = 20;
  if (!(_parseUTC(windowEnd) > _parseUTC(windowStart))) return '';
  const xf = f => (X0 + f * W).toFixed(1);
  const wd = (a, b) => Math.max(1, (b - a) * W).toFixed(1);
  const av = _segs(windowStart, windowEnd, avail);
  const dsg = _segs(windowStart, windowEnd, ds);
  const gaps = _segs(windowStart, windowEnd, (mismatch || []).map(m => [m.start, m.end]));
  const lane = (segs, y, cls, label) => segs.map(s =>
    `<rect class="${cls}" x="${xf(s.x0)}" y="${y}" width="${wd(s.x0, s.x1)}" height="${LH}" rx="2"><title>${esc(label)}: ${esc(_fmtTime(s.a))} → ${esc(_fmtTime(s.b))}</title></rect>`).join('');
  const bands = gaps.map(s =>
    `<rect class="tl-gap" x="${xf(s.x0)}" y="${AVY - 2}" width="${wd(s.x0, s.x1)}" height="${DSY + LH - AVY + 4}"></rect>`
    + `<rect class="tl-gap-hatch" x="${xf(s.x0)}" y="${AVY - 2}" width="${wd(s.x0, s.x1)}" height="${DSY + LH - AVY + 4}"><title>gap: ${esc(_fmtTime(s.a))} → ${esc(_fmtTime(s.b))}</title></rect>`).join('');
  return `<svg class="tlsvg" viewBox="0 0 1000 92" role="img" aria-label="coverage timeline">
    <defs><pattern id="tl-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" class="tl-hatch-bg"></rect><line x1="0" y1="0" x2="0" y2="6" class="tl-hatch-line"></line></pattern></defs>
    <text class="tl-lane" x="8" y="${AVY + 14}">Avail</text>
    <text class="tl-lane" x="8" y="${DSY + 14}">Data</text>
    <rect class="tl-track" x="${X0}" y="${AVY}" width="${W}" height="${LH}" rx="2"></rect>
    <rect class="tl-track" x="${X0}" y="${DSY}" width="${W}" height="${LH}" rx="2"></rect>
    ${lane(av, AVY, 'tl-av', 'Availability')}${lane(dsg, DSY, 'tl-ds', 'Dataselect')}${bands}
    <line class="tl-axis" x1="${X0}" y1="74" x2="${X1}" y2="74"></line>
    <text class="tl-lab" x="${X0}" y="88">${esc(_fmtTime(windowStart))}</text>
    <text class="tl-lab" x="${X1}" y="88" text-anchor="end">${esc(_fmtTime(windowEnd))}</text>
  </svg>`;
}

export function renderSummary(s, results) {
  s = s || {};
  const score = Math.max(0, Math.min(100, Number(s.score ?? 0)));
  const r = 26, C = 2 * Math.PI * r;
  const off = C * (1 - score / 100);
  const col = score >= 95 ? 'var(--ok)' : score >= 80 ? 'var(--warn)' : 'var(--bad)';
  const inc = Number(s.total_inconsistent ?? 0), con = Number(s.total_consistent ?? 0), skp = Number(s.total_skipped ?? 0);
  const av = Number(s.availability_yes_dataselect_no ?? 0), ds = Number(s.availability_no_dataselect_yes ?? 0);
  const dmax = Math.max(1, av, ds);
  const bar = (label, n, cls) => `<div class="dbar"><span class="dlab">${label}</span><span class="dtrack"><span class="dfill ${cls}" style="width:${(n / dmax * 100).toFixed(0)}%"></span></span></div>`;
  return `<header class="summary">
    <div class="gauge"><svg viewBox="0 0 64 64" width="68" height="68" role="img" aria-label="score ${esc(s.score)}%">
      <circle cx="32" cy="32" r="${r}" class="gtrack"></circle>
      <circle cx="32" cy="32" r="${r}" class="gval" transform="rotate(-90 32 32)" style="stroke:${col};stroke-dasharray:${C.toFixed(1)};stroke-dashoffset:${off.toFixed(1)}"></circle>
      <text x="32" y="37" text-anchor="middle" class="gtext">${esc(s.score)}%</text></svg></div>
    <div class="smeta">
      <h1>${esc(s.node)}</h1>
      <div class="chips"><span class="chip bad">${esc(inc)} inconsistent</span><span class="chip ok">${esc(con)} consistent</span><span class="chip mut">${esc(skp)} skipped</span></div>
      <div class="ts">${esc(s.timestamp ?? '')}</div>
    </div>
    <div class="dirs">${bar(`▲ ${esc(ds)} data-only`, ds, 'up')}${bar(`▼ ${esc(av)} avail-only`, av, 'down')}</div>${psdChips(results)}
  </header>`;
}

// PSD chip row for the summary header. Reports predating the PSD check keep the
// row — saying so explicitly — so that they render the same UI as newer ones.
function psdChips(results) {
  const c = psdCounts(results);
  if (!c.checked) {
    return `<div class="chips psd" title="This report was produced before the PSD check existed">
    <span class="chip lbl">PSD</span><span class="chip mut">not checked</span></div>`;
  }
  const extra = (c.unsupported || c.skipped)
    ? `<span class="chip mut">${esc(c.unsupported + c.skipped)} PSD n/a</span>` : '';
  // The reverse finding is rare; show it only when it happened.
  const orphan = c.orphans
    ? `<span class="chip info">${esc(c.orphans)} PSD without data</span>` : '';
  return `<div class="chips psd" title="Availability/Dataselect/PSD triangle — PSD required only for data on/after 2024-01-01">
    <span class="chip lbl">PSD</span>
    <span class="chip bad">✖ ${esc(c.violations)} must fix (≥2024)</span>
    <span class="chip warn">⚠ ${esc(c.pregaps)} pre-2024 gaps</span>
    <span class="chip ok">${esc(c.consistent)} consistent</span>${orphan}${extra}</div>`;
}

const COLUMNS = [
  { label: 'Channel', sort: 'channel' },
  { label: 'Window', sort: 'time' },
  // Direction tags label themselves ("▼ Avail only"), so the heading is blank on
  // screen — but a column with no accessible name is a hole for a screen reader,
  // hence the visually-hidden text.
  { label: '<span class="sr-only">Disagreement</span>', sort: null },
  { label: 'Gaps', sort: 'gap' },
  { label: 'Result', sort: 'status' },
];

export function renderResultsTable(results, filter, sort) {
  const key = sort && sort.key, dir = sort && sort.dir;
  const hasPsd = (results || []).some(psdChecked);
  // The PSD column is always present, so a pre-PSD report renders the same UI as
  // a current one; its cells read "▼ ▲ ?" instead of carrying a verdict.
  const cols = [...COLUMNS.slice(0, 3), { label: '▼▲▶', sort: null }, { label: 'PSD', sort: 'psd' },
    { label: 'Channel epoch', sort: 'epoch' }, ...COLUMNS.slice(3)];
  const head = cols.map(c => {
    if (!c.sort) return `<th>${c.label}</th>`;
    const active = c.sort === key;
    const arrow = active ? (dir === 'asc' ? ' ▲' : ' ▼') : '';
    return `<th class="sortable${active ? ' active' : ''}" data-sort="${c.sort}">${c.label}${arrow}</th>`;
  }).join('');
  const rows = (results || []).filter(r => matchesFilter(r, filter)).map(r => {
    const nslc = `${r.network}.${r.station}.${r.location}.${r.channel}`;
    const tags = r.consistent === false
      ? [...recordDirections(r)].map(w =>
          `<span class="tag ${w === 'availability' ? 'avail' : 'data'}" title="${esc(DIR_LABEL[w] || '')}">${esc(DIR_TAG[w] || w)}</span>`).join(' ')
      : '';
    const { count } = gapStats(r);
    const badge = count ? `<span class="badge">${esc(count)}</span>` : '';
    const v = recordVerdict(r);
    const pv = psdVerdict(r);
    const pTitle = pv ? pv.text : 'PSD not checked in this report';
    const psdCells = `<td><span class="psd ${pv ? pv.cls : 'mut'}" title="${esc(pTitle)}">${esc(psdTriad(r))}</span></td>`
      + `<td><span class="psd-word ${pv ? pv.cls : 'mut'}" title="${esc(pTitle)}">${esc(pv ? pv.short : 'not checked')}</span></td>`;
    const epoch = channelEpochState(r);
    const epochCell = `<td><span class="epoch ${epoch === 'open' ? 'live' : 'ended'}">${esc(epoch)}</span></td>`;
    return `<tr data-index="${esc(r.index)}"><td>${esc(nslc)}</td>
      <td class="win">${esc(r.starttime)} → ${esc(r.endtime)}</td><td>${tags}</td>${psdCells}${epochCell}
      <td>${badge}</td>
      <td><span class="verdict ${v.cls}">${esc(v.text)}</span></td></tr>`;
  }).join('');
  return `${psdLegend(hasPsd)}<table class="results"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
}

// Legend for the triangle column: a glyph key, then one entry per verdict type.
// Reports without PSD get the same box, saying why the third triangle is blank
// rather than explaining colours that never appear.
export function psdLegend(hasPsd = true) {
  const key = `<div class="psd-key"><b>▼</b> Availability · <b>▲</b> Dataselect (ground truth) · <b>▶</b> PSD`;
  if (!hasPsd) {
    return `<div class="psd-legend">${key} — PSD was <b>not checked</b> in this report, so every row shows `
      + `<span class="psd mut">▼ ▲ ?</span>. Re-run the check to include it.</div></div>`;
  }
  return `<div class="psd-legend">${key} · `
    + `<em>filled = has data, hollow = missing</em> (e.g. <b>▼ ▲ ▷</b> = data present but PSD missing).</div>`
    + `<div class="psd-types">`
    + `<span class="psd bad">✖ must fix</span> data ≥ 2024 without PSD · `
    + `<span class="psd warn">⚠ pre-2024 gap</span> same thing, not yet required · `
    + `<span class="psd info">▽ △ ▶ PSD without data</span> no data that whole day · `
    + `<span class="psd ok">▶ consistent</span></div></div>`;
}

// PSD sorts by how much it wants attention, not alphabetically: what must be
// fixed first, what says nothing at all last.
const _PSD_RANK = { violation: 0, pregap: 1, orphan: 2, ok: 3, unsupported: 4, skipped: 5 };
const _psdRank = r => {
  const v = psdVerdict(r);
  // ?? keeps an unrecognised kind from yielding NaN, which would scramble the sort.
  return v ? (_PSD_RANK[v.kind] ?? 6) : 6;   // never checked — after everything checked
};

export function sortRecords(results, key, dir) {
  const arr = [...(results || [])];
  const nslc = r => `${r.network}.${r.station}.${r.location}.${r.channel}`;
  let cmp;
  if (key === 'channel') cmp = (a, b) => nslc(a).localeCompare(nslc(b));
  else if (key === 'gap') cmp = (a, b) => gapStats(a).count - gapStats(b).count;
  else if (key === 'status') cmp = (a, b) => recordVerdict(a).text.localeCompare(recordVerdict(b).text);
  else if (key === 'psd') cmp = (a, b) => _psdRank(a) - _psdRank(b);
  // Open epochs first, then closed ones newest-first: a channel that stopped
  // recording last month is likelier to matter than one that stopped in 2011.
  else if (key === 'epoch') cmp = (a, b) =>
    String(a.channel_epoch_end || '9999').localeCompare(String(b.channel_epoch_end || '9999')) * -1;
  else cmp = (a, b) => String(a.starttime).localeCompare(String(b.starttime)); // 'time'
  arr.sort(cmp);
  const desc = dir === undefined ? key === 'gap' : dir === 'desc'; // gap defaults largest-first
  // _psdRank already counts up from most urgent, so ascending is the useful default.
  if (desc) arr.reverse();
  return arr;
}

function reqLinks(kind, url) {
  const safe = safeUrl(url);
  const open = safe ? ` <a href="${esc(safe)}" target="_blank" rel="noopener noreferrer">open</a>` : '';
  const copy = ` <button class="copy" data-copy="${esc(url)}">copy</button>`;
  // Keep the button, its links and its result badge together when the row wraps.
  return `<span class="reqitem"><button data-kind="${kind}" data-url="${esc(url)}">Run ${kind}</button>${open}${copy}</span>`;
}

export function renderDetail(record) {
  const ex = explainRecord(record);
  const parts = [`<p class="explain ${ex.cls}">${esc(ex.text)}</p>`];
  if (psdChecked(record)) {
    const pv = psdVerdict(record);
    // The 2024 obligation only decides the verdict when PSD is missing; on an
    // orphan (or an unsupported/skipped check) it is noise.
    const meta = [];
    if (pv.kind === 'violation' || pv.kind === 'pregap') {
      meta.push(record.psd_required ? 'required (data on/after 2024-01-01)' : 'not required (pre-2024)');
    }
    const covPsd = (record.coverage && record.coverage.psd) || [];
    if (covPsd.length) meta.push(`day record ${esc(_fmtTime(covPsd[0][0]))} → ${esc(_fmtTime(covPsd[0][1]))}`);
    // An orphan is only a finding because the whole day is empty — link the
    // availability query that established it so the claim can be re-checked.
    const dayUrl = safeUrl(record.psd_day_url);
    if (dayUrl) meta.push(`<a href="${esc(dayUrl)}" target="_blank" rel="noopener noreferrer">check the day's availability</a>`);
    parts.push(`<p class="psd-line ${pv.cls}"><span class="psd-tri">${esc(psdTriad(record))}</span> ${esc(pv.text)}</p>`
      + (meta.length ? `<p class="psd-meta">${meta.join(' · ')}</p>` : ''));
  }
  const cov = record.coverage;
  if (cov && (cov.availability || cov.dataselect)) {
    const segs = (cov.availability || []).length + (cov.dataselect || []).length;
    const svg = timelineSVG(record.starttime, record.endtime, cov.availability || [], cov.dataselect || [], record.mismatch || []);
    // With nothing on either lane the ASCII strip is a row of dots — say what
    // happened instead of drawing an empty picture twice.
    const tl = segs
      ? `<pre class="tl">${esc(timelineAscii(record.starttime, record.endtime, cov.availability || [], cov.dataselect || [], record.mismatch || []))}</pre>` : '';
    const legend = segs
      ? `<span class="lg av">█</span> availability has data &nbsp; <span class="lg ds">█</span> dataselect has data &nbsp; <span class="lg gap">█</span> mismatch &nbsp;·&nbsp; ASCII: ▲ data-only ▼ avail-only █ both · none | boundary`
      : `Neither service returned data in this window.`;
    parts.push(`${svg}${tl}<div class="legend">${legend}</div>`);
  } else {
    const svg = timelineGapsSVG(record.starttime, record.endtime, record.mismatch || []);
    if (svg) parts.push(`${svg}<div class="legend"><span class="lg gap">█</span> mismatch (gap) within the requested window — older report without full coverage data</div>`);
  }
  const full = [['availability', record.url], ['dataselect', buildDataselectUrl(record)],
                ['psd', record.psd_url]]
    .filter(([, u]) => u).map(([k, u]) => reqLinks(k, u)).join(' ');
  if (full) parts.push(`<div class="req full">Requests: ${full}</div>`);
  const gaps = record.mismatch || [];
  if (gaps.length) {
    const items = gaps.map(m => {
      const q = gapQueries(record, m);
      const dur = fmtDuration((_parseUTC(m.end) - _parseUTC(m.start)) / 1000);
      const btns = ['availability', 'dataselect'].filter(k => q[k]).map(k => reqLinks(k, q[k])).join(' ');
      return `<div class="gap"><div class="ghead">${esc(_fmtTime(m.start))} → ${esc(_fmtTime(m.end))} <span class="gdur">${esc(dur)}</span> ${esc(DIR_LABEL[m.who] || '')}</div><div class="req">${btns}</div></div>`;
    }).join('');
    parts.push(`<div class="gaps"><h2>${esc(gaps.length)} gap${gaps.length === 1 ? '' : 's'}</h2>${items}</div>`);
  }
  return `<section class="detail">${parts.join('')}</section>`;
}

export function renderIndex(entries) {
  const items = (entries || []).map(e => {
    const u = String(e.url ?? e.report ?? '');
    const href = `?report=${encodeURIComponent(u)}`;
    const cls = e.score == null ? '' : e.score >= 95 ? ' ok' : e.score >= 80 ? ' warn' : ' bad';
    const score = e.score == null ? '' : `<span class="iscore${cls}">${esc(e.score)}%</span>`;
    const meta = [e.node, e.timestamp, e.inconsistent != null ? `${esc(e.inconsistent)} inconsistent` : '']
      .filter(Boolean).map(x => esc(x)).join(' · ');
    return `<li><a href="${esc(href)}">${esc(e.name || u)}</a> ${score}<span class="imeta">${meta}</span></li>`;
  }).join('');
  return `<section class="index"><h1>Latest consistency reports</h1><ul class="ilist">${items}</ul></section>`;
}

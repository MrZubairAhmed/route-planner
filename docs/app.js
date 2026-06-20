const OSRM = 'https://router.project-osrm.org';
const MAX_WAYPOINTS = 23;

let parsed = null;
let lastResults = null;

const $ = id => document.getElementById(id);
const dropzone = $('dropzone');
const fileInput = $('fileInput');
const preview = $('preview');
const submitBtn = $('submitBtn');
const statusEl = $('status');

dropzone.onclick = () => fileInput.click();
dropzone.ondragover = e => e.preventDefault();
dropzone.ondrop = e => { e.preventDefault(); if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]); };
fileInput.onchange = () => { if (fileInput.files[0]) loadFile(fileInput.files[0]); };
$('templateBtn').onclick = downloadTemplate;
submitBtn.onclick = generateRoutes;

function findCol(headers, names) {
  const lower = headers.map(h => String(h ?? '').trim().toLowerCase());
  for (const n of names) {
    const i = lower.indexOf(n.toLowerCase());
    if (i >= 0) return i;
  }
  return -1;
}

function num(v) {
  const n = parseFloat(String(v ?? '').replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

function coordsMatch(a, b, eps = 1e-5) {
  return Math.abs(a.lat - b.lat) < eps && Math.abs(a.lng - b.lng) < eps;
}

async function loadFile(file) {
  $('fileName').textContent = file.name;
  submitBtn.disabled = true;
  parsed = null;
  lastResults = null;
  preview.className = 'preview visible';
  preview.textContent = 'Analyzing...';
  statusEl.textContent = '';
  try {
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: 'array' });
    const sheetName = wb.SheetNames[0];
    const sheet = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
    if (rows.length < 2) throw new Error('Excel file has no data rows.');
    parsed = analyzeRows(rows);
    parsed.fileName = file.name.replace(/\.(xlsx|xls)$/i, '') + '_with_routes.xlsx';
    parsed.sheetName = sheetName;
    preview.innerHTML = `<strong>Ready:</strong> ${parsed.summary}`;
    preview.classList.remove('error');
    submitBtn.disabled = false;
  } catch (err) {
    preview.className = 'preview visible error';
    preview.textContent = err.message;
  }
}

function analyzeRows(rows) {
  const headers = rows[0].map(h => String(h ?? '').trim());
  const cols = {
    latCol: findCol(headers, ['Latitude', 'Lat', 'LAT']),
    lngCol: findCol(headers, ['Longitude', 'Lng', 'Long', 'LNG', 'Lon']),
    nameCol: findCol(headers, ['Name', 'School Name', 'Location Name', 'Destination Name']),
    startLatCol: findCol(headers, ['Start LAT', 'Start Lat', 'Start Latitude', 'Origin Lat']),
    startLngCol: findCol(headers, ['Start LNG', 'Start Lng', 'Start Longitude', 'Origin Lng']),
    districtCol: findCol(headers, ['District', 'Region']),
    tehsilCol: findCol(headers, ['Tehsil', 'Tehsil Name', 'Sub District']),
    routeCol: findCol(headers, ['Route', 'Routes', 'GoogleMapsURL', 'Google Maps URL', 'Google Maps Link']),
    routeNoCol: findCol(headers, ['RouteNo', 'Route No', 'Route Number']),
  };
  if (cols.latCol < 0 || cols.lngCol < 0) throw new Error('Required columns not found: Latitude and Longitude');

  const destinations = [];
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    const lat = num(row[cols.latCol]);
    const lng = num(row[cols.lngCol]);
    if (lat == null || lng == null) continue;
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) continue;
    destinations.push({
      lat, lng, rowIndex: r,
      name: cols.nameCol >= 0 ? String(row[cols.nameCol] || `Stop ${destinations.length + 1}`) : `Stop ${destinations.length + 1}`,
      district: cols.districtCol >= 0 ? String(row[cols.districtCol] || '').trim() : '',
      tehsil: cols.tehsilCol >= 0 ? String(row[cols.tehsilCol] || '').trim() : '',
    });
  }
  if (!destinations.length) throw new Error('No valid locations found in Excel.');

  let startLat = cols.startLatCol >= 0 ? num(rows[1][cols.startLatCol]) : null;
  let startLng = cols.startLngCol >= 0 ? num(rows[1][cols.startLngCol]) : null;
  if (startLat == null || startLng == null) {
    startLat = destinations[0].lat;
    startLng = destinations[0].lng;
  }

  const districts = [...new Set(destinations.map(d => d.district).filter(Boolean))];
  const tehsils = [...new Set(destinations.map(d => d.tehsil).filter(Boolean))];
  let batchBy = 'none';
  if (districts.length > 1) batchBy = 'district';
  else if (tehsils.length > 1) batchBy = 'tehsil';

  const summary = `${destinations.length} locations` +
    (batchBy !== 'none' ? ` · batch by ${batchBy}` : ' · single route');

  return {
    headers, rows, cols, destinations,
    start: { lat: startLat, lng: startLng, name: 'Start' },
    batchBy, districts, tehsils, summary,
  };
}

function groupDestinations(destinations, batchBy) {
  if (batchBy === 'none') return [{ name: 'All locations', stops: destinations }];
  const key = batchBy === 'district' ? 'district' : 'tehsil';
  const map = new Map();
  for (const d of destinations) {
    const g = d[key] || '(No group)';
    if (!map.has(g)) map.set(g, []);
    map.get(g).push(d);
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([name, stops]) => ({ name, stops }));
}

function haversine(a, b) {
  const R = 6371000;
  const toR = x => x * Math.PI / 180;
  const dLat = toR(b.lat - a.lat);
  const dLng = toR(b.lng - a.lng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toR(a.lat)) * Math.cos(toR(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

async function distanceMatrix(stops) {
  const n = stops.length;
  const matrix = Array.from({ length: n }, () => Array(n).fill(0));
  if (n <= 100) {
    try {
      const coords = stops.map(s => `${s.lng},${s.lat}`).join(';');
      const res = await fetch(`${OSRM}/table/v1/driving/${coords}?annotations=distance`);
      const data = await res.json();
      if (data.code === 'Ok' && data.distances) {
        for (let i = 0; i < n; i++)
          for (let j = 0; j < n; j++)
            matrix[i][j] = data.distances[i][j] ?? haversine(stops[i], stops[j]);
        return matrix;
      }
    } catch { /* fallback */ }
  }
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++)
      matrix[i][j] = i === j ? 0 : haversine(stops[i], stops[j]);
  return matrix;
}

function nearestNeighbor(matrix) {
  const n = matrix.length;
  const visited = new Set([0]);
  const order = [];
  let cur = 0;
  while (order.length < n - 1) {
    let best = -1, bestD = Infinity;
    for (let i = 1; i < n; i++) {
      if (visited.has(i)) continue;
      if (matrix[cur][i] < bestD) { bestD = matrix[cur][i]; best = i; }
    }
    order.push(best);
    visited.add(best);
    cur = best;
  }
  return order;
}

function googleUrl(stops) {
  const fmt = s => encodeURIComponent(`${s.lat},${s.lng}`);
  const origin = fmt(stops[0]);
  const dest = fmt(stops[stops.length - 1]);
  const wps = stops.slice(1, -1).map(fmt).join('|');
  let url = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dest}&travelmode=driving`;
  if (wps) url += `&waypoints=${wps}`;
  return url;
}

function splitChunks(start, ordered, maxWp) {
  const maxDest = maxWp + 1;
  const chunks = [];
  let cursor = 0;
  let routeNo = 1;
  let currentStart = { ...start, name: start.name || 'Start' };
  while (cursor < ordered.length) {
    const batch = ordered.slice(cursor, cursor + maxDest);
    const chunkStops = [currentStart, ...batch];
    chunks.push({ routeNo, url: googleUrl(chunkStops), stops: chunkStops });
    currentStart = { ...batch[batch.length - 1] };
    cursor += batch.length;
    routeNo++;
  }
  return chunks;
}

async function planGroup(group, start) {
  const stops = group.stops;
  if (!stops.length) throw new Error('No stops in group');
  const all = [{ lat: start.lat, lng: start.lng, name: 'Start', rowIndex: null }, ...stops];
  statusEl.textContent = `Optimizing ${group.name} (${stops.length} locations)...`;
  const matrix = await distanceMatrix(all);
  const orderIdx = nearestNeighbor(matrix);
  const ordered = orderIdx.map(i => all[i]);
  const destOrdered = ordered.slice(1);
  const chunks = splitChunks(start, destOrdered, MAX_WAYPOINTS);
  return { name: group.name, stopCount: stops.length, stops, chunks, start };
}

function ensureCol(headers, rows, colIndex, name) {
  if (colIndex >= 0) return colIndex;
  const idx = headers.length;
  headers.push(name);
  for (let r = 0; r < rows.length; r++) {
    while (rows[r].length < idx) rows[r].push('');
    if (r === 0) rows[r][idx] = name;
    else if (rows[r].length <= idx) rows[r].push('');
  }
  return idx;
}

function setCell(row, col, value) {
  while (row.length <= col) row.push('');
  row[col] = value;
}

/** Assign the same Google Maps URL to every row in the chunk (start + destinations). */
function applyRoutesToExcel(items) {
  const headers = [...parsed.headers];
  const rows = parsed.rows.map(r => [...r]);
  let routeCol = parsed.cols.routeCol;
  let routeNoCol = parsed.cols.routeNoCol;

  routeCol = ensureCol(headers, rows, routeCol, 'Route');
  routeNoCol = ensureCol(headers, rows, routeNoCol, 'RouteNo');
  rows[0] = headers;

  for (const item of items) {
    if (item.error) continue;
    for (const chunk of item.chunks) {
      for (const stop of chunk.stops) {
        for (const s of item.stops) {
          if (coordsMatch(s, stop)) {
            setCell(rows[s.rowIndex], routeCol, chunk.url);
            setCell(rows[s.rowIndex], routeNoCol, chunk.routeNo);
          }
        }
      }
    }
  }

  return { headers, rows, routeCol, routeNoCol };
}

function downloadRoutedExcel(items) {
  const { rows } = applyRoutesToExcel(items);
  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, parsed.sheetName || 'Sheet1');
  XLSX.writeFile(wb, parsed.fileName || 'routes_output.xlsx');
}

async function generateRoutes() {
  if (!parsed) return;
  submitBtn.disabled = true;
  submitBtn.textContent = 'Generating routes...';
  statusEl.textContent = 'Starting...';
  const groups = groupDestinations(parsed.destinations, parsed.batchBy);
  const items = [];
  for (const g of groups) {
    try {
      items.push({ ...(await planGroup(g, parsed.start)), error: null });
    } catch (err) {
      items.push({ name: g.name, stopCount: g.stops.length, chunks: [], error: err.message });
    }
  }
  lastResults = items;
  showResults(items);
  submitBtn.textContent = 'Generate Routes';
  submitBtn.disabled = false;
  statusEl.textContent = '';
}

function showResults(items) {
  const ok = items.filter(i => !i.error);
  const failed = items.filter(i => i.error);
  const totalLoc = ok.reduce((s, i) => s + i.stopCount, 0);
  const cards = items.map(item => {
    if (item.error) {
      return `<div class="card error"><h3>${esc(item.name)}</h3><p class="status-err">Failed: ${esc(item.error)}</p></div>`;
    }
    const links = item.chunks.map(c => {
      const label = item.chunks.length === 1 ? 'Open Routes' : `Open Routes ${c.routeNo}`;
      return `<a class="btn" href="${esc(c.url)}" target="_blank" rel="noopener">${label}</a>`;
    }).join('');
    return `<div class="card"><h3>${esc(item.name)}</h3><p>${item.stopCount} locations</p>${links}</div>`;
  }).join('');

  $('app').classList.add('hidden');
  const el = $('results');
  el.classList.remove('hidden');
  el.innerHTML = `
    <a class="back" id="backBtn">&larr; Plan another route</a>
    <div class="header">
      <h1>Excel Routes</h1>
      <p>${ok.length} batches · ${failed.length} failed · ${totalLoc} locations</p>
      <div class="header-actions">
        <button type="button" class="btn" id="downloadExcelBtn">Download Excel with Routes</button>
      </div>
    </div>
    <div class="grid">${cards}</div>`;
  $('backBtn').onclick = () => {
    el.classList.add('hidden');
    el.innerHTML = '';
    $('app').classList.remove('hidden');
  };
  $('downloadExcelBtn').onclick = () => {
    if (lastResults) downloadRoutedExcel(lastResults);
  };
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function downloadTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['Name', 'Latitude', 'Longitude', 'Start LAT', 'Start LNG', 'District', 'Tehsil', 'SchoolCode', 'Route', 'RouteNo'],
    ['Example School', 30.45, 70.90, 31.53, 74.34, 'Sample District', 'Sample Tehsil', 'SCH001', '', ''],
  ]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Locations');
  XLSX.writeFile(wb, 'route_planner_template.xlsx');
}

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

function buildPlaceQuery(name, district) {
  return [name, district, 'Pakistan'].filter(Boolean).join(', ');
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
    startingPointCol: findCol(headers, ['Starting Point', 'Start Point', 'Start Location', 'Start Name', 'Origin']),
    districtCol: findCol(headers, ['District', 'Region']),
    tehsilCol: findCol(headers, ['Tehsil', 'Tehsil Name', 'Sub District']),
    routeCol: findCol(headers, ['Route', 'Routes', 'GoogleMapsURL', 'Google Maps URL', 'Google Maps Link']),
    routeNoCol: findCol(headers, ['RouteNo', 'Route No', 'Route Number']),
  };
  if (cols.latCol < 0 || cols.lngCol < 0) throw new Error('Required columns not found: Latitude and Longitude');

  const hasStartingPoint = cols.startingPointCol >= 0;
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
      startingPoint: hasStartingPoint ? String(row[cols.startingPointCol] || '').trim() : '',
    });
  }
  if (!destinations.length) throw new Error('No valid locations found in Excel.');

  let startLat = cols.startLatCol >= 0 ? num(rows[1][cols.startLatCol]) : null;
  let startLng = cols.startLngCol >= 0 ? num(rows[1][cols.startLngCol]) : null;
  if (!hasStartingPoint && (startLat == null || startLng == null)) {
    startLat = destinations[0].lat;
    startLng = destinations[0].lng;
  }

  const batchBy = determineBatchMode(destinations, hasStartingPoint);
  const groupCount = groupDestinations(destinations, batchBy).length;
  const summary = `${destinations.length} locations · ${groupCount} route batch${groupCount === 1 ? '' : 'es'}` +
    (hasStartingPoint ? ' · batch by district and starting point' : batchBy !== 'none' ? ` · batch by ${batchBy}` : ' · single route');

  return {
    headers, rows, cols, destinations, hasStartingPoint,
    start: hasStartingPoint ? null : { lat: startLat, lng: startLng, name: 'Start' },
    batchBy, summary,
  };
}

function determineBatchMode(destinations, hasStartingPoint) {
  if (hasStartingPoint) return 'startingPoint';
  const districts = [...new Set(destinations.map(d => d.district).filter(Boolean))];
  const tehsils = [...new Set(destinations.map(d => d.tehsil).filter(Boolean))];
  if (districts.length > 1) return 'district';
  if (tehsils.length > 1) return 'tehsil';
  return 'none';
}

function groupDestinations(destinations, batchBy) {
  if (batchBy === 'startingPoint') {
    const map = new Map();
    for (const d of destinations) {
      const sp = d.startingPoint || '(No starting point)';
      const key = `${d.district}\0${sp}`;
      if (!map.has(key)) {
        map.set(key, { district: d.district, startingPoint: sp, stops: [] });
      }
      map.get(key).stops.push(d);
    }
    return [...map.values()]
      .sort((a, b) => `${a.district}${a.startingPoint}`.localeCompare(`${b.district}${b.startingPoint}`))
      .map(g => ({
        name: [g.district, g.startingPoint !== '(No starting point)' ? g.startingPoint : ''].filter(Boolean).join(' · ') || 'All locations',
        ...g,
      }));
  }
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

function resolveGroupStart(group) {
  if (group.startingPoint && group.startingPoint !== '(No starting point)') {
    return {
      name: group.startingPoint,
      district: group.district,
      placeQuery: buildPlaceQuery(group.startingPoint, group.district),
      lat: null,
      lng: null,
    };
  }
  if (parsed?.start) return { ...parsed.start };
  const first = group.stops[0];
  return { lat: first.lat, lng: first.lng, name: 'Start' };
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

function nearestNeighbor(matrix, startIdx = 0) {
  const n = matrix.length;
  const visited = new Set([startIdx]);
  const order = [];
  let cur = startIdx;
  while (order.length < n - 1) {
    let best = -1, bestD = Infinity;
    for (let i = 0; i < n; i++) {
      if (visited.has(i)) continue;
      if (matrix[cur][i] < bestD) { bestD = matrix[cur][i]; best = i; }
    }
    if (best < 0) break;
    order.push(best);
    visited.add(best);
    cur = best;
  }
  return order;
}

function googleUrl(start, destinations) {
  const fmtCoord = s => encodeURIComponent(`${s.lat},${s.lng}`);
  const origin = start.placeQuery
    ? encodeURIComponent(start.placeQuery)
    : fmtCoord(start);
  if (!destinations.length) {
    return `https://www.google.com/maps/dir/?api=1&origin=${origin}&travelmode=driving`;
  }
  const dest = fmtCoord(destinations[destinations.length - 1]);
  const wps = destinations.slice(0, -1).map(fmtCoord).join('|');
  let url = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dest}&travelmode=driving`;
  if (wps) url += `&waypoints=${wps}`;
  return url;
}

/** Merge key: same starting point + same ending destination in the Maps URL. */
function routeLegKey(url) {
  try {
    const params = new URL(String(url)).searchParams;
    return [
      params.get('origin') || '',
      params.get('destination') || '',
    ].join('\0');
  } catch {
    return String(url);
  }
}

function splitChunks(start, ordered, maxWp) {
  const maxDest = maxWp + 1;
  const chunks = [];
  let cursor = 0;
  let routeNo = 1;
  let currentStart = { ...start };
  while (cursor < ordered.length) {
    const batch = ordered.slice(cursor, cursor + maxDest);
    chunks.push({
      routeNo,
      url: googleUrl(currentStart, batch),
      stops: batch,
      startLabel: currentStart.placeQuery || currentStart.name || 'Start',
    });
    if (batch.length) {
      currentStart = start.placeQuery
        ? { ...batch[batch.length - 1] }
        : { ...batch[batch.length - 1] };
    }
    cursor += batch.length;
    routeNo++;
  }
  return chunks;
}

async function planGroup(group, start) {
  const stops = group.stops;
  if (!stops.length) throw new Error('No stops in group');

  statusEl.textContent = `Optimizing ${group.name} (${stops.length} locations)...`;

  let destOrdered;
  if (start.lat != null && start.lng != null) {
    const all = [{ lat: start.lat, lng: start.lng, name: start.name || 'Start', rowIndex: null }, ...stops];
    const matrix = await distanceMatrix(all);
    const orderIdx = nearestNeighbor(matrix, 0);
    destOrdered = orderIdx.map(i => all[i]).slice(1);
  } else {
    const matrix = await distanceMatrix(stops);
    const orderIdx = nearestNeighbor(matrix, 0);
    destOrdered = orderIdx.map(i => stops[i]);
  }

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

/** Map each destination row to its route URL and route number. */
function applyRoutesToExcel(items) {
  const headers = [...parsed.headers];
  const rows = parsed.rows.map(r => [...r]);
  let routeCol = parsed.cols.routeCol;
  let routeNoCol = parsed.cols.routeNoCol;
  const rowLegKeys = new Map();

  routeCol = ensureCol(headers, rows, routeCol, 'Routes');
  routeNoCol = ensureCol(headers, rows, routeNoCol, 'RouteNo');
  rows[0] = headers;

  for (const item of items) {
    if (item.error) continue;
    for (const chunk of item.chunks) {
      const legKey = routeLegKey(chunk.url);
      for (const stop of chunk.stops) {
        if (stop.rowIndex == null) continue;
        setCell(rows[stop.rowIndex], routeCol, chunk.url);
        setCell(rows[stop.rowIndex], routeNoCol, chunk.routeNo);
        rowLegKeys.set(stop.rowIndex, legKey);
      }
    }
  }

  return { headers, rows, routeCol, routeNoCol, rowLegKeys };
}

/**
 * Group rows by route leg (starting point + ending destination in Maps URL),
 * keep URL only on the first row of each block, and merge the Routes column.
 */
function formatRoutesColumnLikeReference(rows, routeCol, rowLegKeys) {
  const header = rows[0];
  const entries = rows.slice(1).map((row, i) => ({
    row,
    i,
    legKey: rowLegKeys.get(i + 1) || '',
  }));

  entries.sort((a, b) => {
    const urlA = String(a.row[routeCol] || '');
    const urlB = String(b.row[routeCol] || '');
    const hasA = urlA.startsWith('http');
    const hasB = urlB.startsWith('http');
    if (!hasA && !hasB) return a.i - b.i;
    if (!hasA) return 1;
    if (!hasB) return -1;
    if (a.legKey !== b.legKey) return a.legKey.localeCompare(b.legKey);
    return a.i - b.i;
  });

  const sorted = [header, ...entries.map(entry => entry.row)];
  const merges = [];
  let i = 1;

  while (i < sorted.length) {
    const legKey = entries[i - 1].legKey;
    const url = String(entries[i - 1].row[routeCol] || '');
    if (!url.startsWith('http') || !legKey) {
      i++;
      continue;
    }
    let j = i + 1;
    while (j < sorted.length && entries[j - 1].legKey === legKey) j++;
    if (j - i > 1) {
      merges.push({ s: { r: i, c: routeCol }, e: { r: j - 1, c: routeCol } });
      for (let k = i + 1; k < j; k++) sorted[k][routeCol] = '';
    }
    i = j;
  }

  return { rows: sorted, merges };
}

function addRouteHyperlinks(ws, rows, routeCol) {
  for (let r = 1; r < rows.length; r++) {
    const url = rows[r][routeCol];
    if (!url || !String(url).startsWith('http')) continue;
    const addr = XLSX.utils.encode_cell({ r, c: routeCol });
    if (!ws[addr]) continue;
    ws[addr].l = { Target: String(url), Tooltip: 'Open route in Google Maps' };
  }
}

function downloadRoutedExcel(items) {
  const { rows: routedRows, routeCol, rowLegKeys } = applyRoutesToExcel(items);
  const { rows, merges } = formatRoutesColumnLikeReference(routedRows, routeCol, rowLegKeys);
  const ws = XLSX.utils.aoa_to_sheet(rows);
  if (merges.length) ws['!merges'] = merges;
  addRouteHyperlinks(ws, rows, routeCol);
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
      const start = parsed.hasStartingPoint ? resolveGroupStart(g) : parsed.start;
      items.push({ ...(await planGroup(g, start)), error: null });
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
    const startInfo = item.start?.placeQuery
      ? `<p class="hint">Start: ${esc(item.start.placeQuery)}</p>`
      : '';
    const links = item.chunks.map(c => {
      const label = item.chunks.length === 1 ? 'Open Routes' : `Open Routes ${c.routeNo}`;
      return `<a class="btn" href="${esc(c.url)}" target="_blank" rel="noopener">${label}</a>`;
    }).join('');
    return `<div class="card"><h3>${esc(item.name)}</h3><p>${item.stopCount} locations</p>${startInfo}${links}</div>`;
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
    ['SchoolCode', 'Name', 'Address', 'District', 'Tehsil', 'Latitude', 'Longitude', 'Starting Point', 'Routes', 'RouteNo'],
    ['SCH001', 'Example School', 'Sample Address', 'Sample District', 'Sample Tehsil', 30.45, 70.90, 'DC Office', '', ''],
  ]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Locations');
  XLSX.writeFile(wb, 'route_planner_template.xlsx');
}

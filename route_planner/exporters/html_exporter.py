import html
import json
from pathlib import Path

from ..models import PlannedRoute

ROUTE_COLORS = [
    "#4285F4",
    "#EA4335",
    "#FBBC04",
    "#34A853",
    "#FF6D01",
    "#46BDC6",
    "#7B1FA2",
    "#C2185B",
]


def write_html_map(planned: PlannedRoute, output_path: Path) -> Path:
    """Write standalone Leaflet HTML map with numbered markers and road routes."""
    markers = [
        {
            "lat": planned.start.lat,
            "lng": planned.start.lng,
            "name": planned.start.name,
            "order": 0,
            "type": "start",
        }
    ]
    for i, stop in enumerate(planned.ordered_stops, start=1):
        markers.append(
            {
                "lat": stop.lat,
                "lng": stop.lng,
                "name": stop.name,
                "order": i,
                "type": "destination",
                "segment_km": round(planned.segments[i - 1].distance_km, 2),
            }
        )

    route_layers = []
    for chunk in planned.chunks:
        chunk_destinations = {id(s) for s in chunk.stops[1:]}
        coords: list[list[float]] = []
        for segment in planned.segments:
            if id(segment.to_stop) not in chunk_destinations:
                continue
            for lat, lng in segment.geometry:
                coords.append([lat, lng])
        route_layers.append(
            {
                "route_no": chunk.route_no,
                "color": ROUTE_COLORS[(chunk.route_no - 1) % len(ROUTE_COLORS)],
                "coords": coords,
                "url": chunk.google_maps_url,
                "distance_km": round(chunk.total_distance_km, 2),
                "stops": [s.name for s in chunk.stops],
            }
        )

    data = {
        "markers": markers,
        "routes": route_layers,
        "summary": {
            "total_destinations": len(planned.ordered_stops),
            "total_distance_km": round(planned.total_distance_km, 2),
            "total_duration_hours": round(planned.total_duration_sec / 3600, 2),
            "route_chunks": len(planned.chunks),
        },
    }

    page = _HTML_TEMPLATE.replace("__ROUTE_DATA__", json.dumps(data))
    output_path.write_text(page, encoding="utf-8")
    return output_path


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Optimized Route Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; display: flex; height: 100vh; }
    #sidebar {
      width: 380px; min-width: 320px; overflow-y: auto;
      background: #f8f9fa; border-right: 1px solid #ddd; padding: 20px;
    }
    #map { flex: 1; }
    h1 { font-size: 1.3rem; margin-bottom: 8px; color: #1a1a1a; }
    .stats { background: #fff; border-radius: 8px; padding: 12px; margin: 12px 0; border: 1px solid #e0e0e0; }
    .stats p { margin: 4px 0; font-size: 0.9rem; color: #444; }
    .route-card {
      background: #fff; border-radius: 8px; padding: 14px; margin: 10px 0;
      border-left: 4px solid #4285F4; border: 1px solid #e0e0e0;
    }
    .route-card h3 { font-size: 1rem; margin-bottom: 6px; }
    .route-card p { font-size: 0.85rem; color: #555; margin: 3px 0; }
    .btn {
      display: inline-block; margin-top: 8px; padding: 8px 14px;
      background: #4285F4; color: #fff; text-decoration: none;
      border-radius: 6px; font-size: 0.85rem; font-weight: 600;
    }
    .btn:hover { background: #3367d6; }
    .stop-list { max-height: 120px; overflow-y: auto; font-size: 0.8rem; color: #666; margin-top: 6px; }
    .legend { font-size: 0.8rem; color: #666; margin-top: 16px; }
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>Optimized Route</h1>
    <div class="stats" id="summary"></div>
    <div id="route-links"></div>
    <div class="legend">
      <p><strong>Legend:</strong></p>
      <p>🟢 Start &nbsp; 🔵 Destinations (numbered by visit order)</p>
      <p>Colored lines = road routes from OSRM</p>
    </div>
  </div>
  <div id="map"></div>
  <script>
    const DATA = __ROUTE_DATA__;

    const map = L.map('map').setView([DATA.markers[0].lat, DATA.markers[0].lng], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const bounds = L.latLngBounds();

    DATA.markers.forEach(m => {
      bounds.extend([m.lat, m.lng]);
      const isStart = m.type === 'start';
      const color = isStart ? '#0F9D58' : '#4285F4';
      const label = isStart ? 'S' : String(m.order);
      const icon = L.divIcon({
        className: 'marker-label',
        html: `<div style="background:${color};color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">${label}</div>`,
        iconSize: [28, 28], iconAnchor: [14, 14]
      });
      const popup = isStart
        ? `<b>${m.name}</b><br>Starting point`
        : `<b>${m.order}. ${m.name}</b><br>Segment: ${m.segment_km} km`;
      L.marker([m.lat, m.lng], { icon }).addTo(map).bindPopup(popup);
    });

    DATA.routes.forEach(r => {
      if (r.coords.length > 1) {
        L.polyline(r.coords, { color: r.color, weight: 4, opacity: 0.8 }).addTo(map);
      }
    });

    map.fitBounds(bounds, { padding: [40, 40] });

    const s = DATA.summary;
    document.getElementById('summary').innerHTML = `
      <p><strong>Destinations:</strong> ${s.total_destinations}</p>
      <p><strong>Total road distance:</strong> ${s.total_distance_km} km</p>
      <p><strong>Est. drive time:</strong> ${s.total_duration_hours} hours</p>
      <p><strong>Google Maps chunks:</strong> ${s.route_chunks}</p>
    `;

    const linksDiv = document.getElementById('route-links');
    DATA.routes.forEach(r => {
      const stops = r.stops.map((n,i) => `${i===0?'Start':i}. ${n}`).join('<br>');
      linksDiv.innerHTML += `
        <div class="route-card" style="border-left-color:${r.color}">
          <h3>Route ${r.route_no} — ${r.distance_km} km</h3>
          <p>${r.stops.length} stops in this chunk</p>
          <a class="btn" href="${r.url}" target="_blank">Open in Google Maps</a>
          <div class="stop-list">${stops}</div>
        </div>`;
    });
  </script>
</body>
</html>
"""

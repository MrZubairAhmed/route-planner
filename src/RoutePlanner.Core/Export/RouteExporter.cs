using System.Text;
using System.Text.Json;
using ClosedXML.Excel;
using RoutePlanner.Core.Models;

namespace RoutePlanner.Core.Export;

public static class RouteExporter
{
    public static void WriteSingleExcel(PlannedRoute planned, string path) =>
        WriteExcelWorkbook(planned, path, includeBatchColumns: false);

    public static void WriteBatchMasterExcel(IReadOnlyList<BatchItemResult> items, string path)
    {
        using var wb = new XLWorkbook();
        var allRows = new List<Dictionary<string, object>>();
        var summary = new List<Dictionary<string, object>>();

        foreach (var item in items.Where(i => i.Planned is not null))
        {
            var planned = item.Planned!;
            allRows.AddRange(BuildRows(planned, item.Name, item.District, item.Tehsil, includeBatch: true));
            summary.Add(new Dictionary<string, object>
            {
                ["BatchName"] = item.Name,
                ["District"] = item.District,
                ["Tehsil"] = item.Tehsil,
                ["Locations"] = item.StopCount,
                ["TotalDistance_km"] = Math.Round(planned.TotalDistanceKm, 2),
                ["Duration_hours"] = Math.Round(planned.TotalDurationSec / 3600, 2),
                ["GoogleMapsChunks"] = planned.Chunks.Count,
                ["MapFile"] = item.MapHtml
            });
        }

        WriteSheet(wb, "AllVisitOrders", allRows);
        WriteSheet(wb, "BatchSummary", summary);
        wb.SaveAs(path);
    }

    private static void WriteExcelWorkbook(PlannedRoute planned, string path, bool includeBatchColumns)
    {
        using var wb = new XLWorkbook();
        var rows = BuildRows(planned, planned.BatchName, planned.District, planned.Tehsil, includeBatchColumns);
        WriteSheet(wb, "VisitOrder", rows);
        WriteSheet(wb, "GoogleMapsURLs", planned.Chunks.Select(c => new Dictionary<string, object>
        {
            ["RouteNo"] = c.RouteNo,
            ["StopsInChunk"] = c.Stops.Count,
            ["Distance_km"] = Math.Round(c.TotalDistanceKm, 2),
            ["GoogleMapsURL"] = c.GoogleMapsUrl
        }).ToList());
        WriteSheet(wb, "Summary", [
            new() { ["Metric"] = "Total Destinations", ["Value"] = planned.OrderedStops.Count },
            new() { ["Metric"] = "Total Distance (km)", ["Value"] = Math.Round(planned.TotalDistanceKm, 2) },
            new() { ["Metric"] = "Total Duration (hours)", ["Value"] = Math.Round(planned.TotalDurationSec / 3600, 2) },
            new() { ["Metric"] = "Route Chunks", ["Value"] = planned.Chunks.Count }
        ]);
        wb.SaveAs(path);
    }

    private static List<Dictionary<string, object>> BuildRows(
        PlannedRoute planned, string batchName, string district, string tehsil, bool includeBatch)
    {
        var rows = new List<Dictionary<string, object>>();
        var stopToRoute = new Dictionary<Stop, int>();
        var stopToUrl = new Dictionary<Stop, string>();
        foreach (var chunk in planned.Chunks)
        {
            foreach (var stop in chunk.Stops.Skip(1))
            {
                stopToRoute[stop] = chunk.RouteNo;
                stopToUrl[stop] = chunk.GoogleMapsUrl;
            }
        }

        var startRow = new Dictionary<string, object>
        {
            ["VisitOrder"] = 0,
            ["Name"] = planned.Start.Name,
            ["Code"] = "",
            ["Latitude"] = planned.Start.Lat,
            ["Longitude"] = planned.Start.Lng,
            ["RouteNo"] = 1,
            ["SegmentDistance_km"] = 0.0,
            ["CumulativeDistance_km"] = 0.0,
            ["GoogleMapsURL"] = planned.Chunks.FirstOrDefault()?.GoogleMapsUrl ?? "",
            ["StopType"] = "Start"
        };
        if (includeBatch)
        {
            startRow["BatchName"] = batchName;
            startRow["District"] = district;
            startRow["Tehsil"] = tehsil;
        }
        rows.Add(startRow);

        var cumulative = 0.0;
        for (var i = 0; i < planned.OrderedStops.Count; i++)
        {
            var stop = planned.OrderedStops[i];
            var seg = planned.Segments[i];
            cumulative += seg.DistanceKm;
            var row = new Dictionary<string, object>
            {
                ["VisitOrder"] = i + 1,
                ["Name"] = stop.Name,
                ["Code"] = stop.LocationCode,
                ["Latitude"] = stop.Lat,
                ["Longitude"] = stop.Lng,
                ["RouteNo"] = stopToRoute.GetValueOrDefault(stop, 1),
                ["SegmentDistance_km"] = Math.Round(seg.DistanceKm, 2),
                ["CumulativeDistance_km"] = Math.Round(cumulative, 2),
                ["GoogleMapsURL"] = stopToUrl.GetValueOrDefault(stop, ""),
                ["StopType"] = "Destination"
            };
            if (includeBatch)
            {
                row["BatchName"] = batchName;
                row["District"] = string.IsNullOrEmpty(stop.District) ? district : stop.District;
                row["Tehsil"] = string.IsNullOrEmpty(stop.Tehsil) ? tehsil : stop.Tehsil;
            }
            rows.Add(row);
        }

        return rows;
    }

    private static void WriteSheet(XLWorkbook wb, string name, List<Dictionary<string, object>> rows)
    {
        var ws = wb.AddWorksheet(name);
        if (rows.Count == 0) return;
        var headers = rows[0].Keys.ToList();
        for (var c = 0; c < headers.Count; c++)
            ws.Cell(1, c + 1).Value = headers[c];
        for (var r = 0; r < rows.Count; r++)
        for (var c = 0; c < headers.Count; c++)
            ws.Cell(r + 2, c + 1).Value = rows[r][headers[c]]?.ToString() ?? "";
    }

    public static void WriteKml(PlannedRoute planned, string path)
    {
        var sb = new StringBuilder();
        sb.Append("""<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Optimized Route</name>""");
        sb.Append("<Folder><name>Stops</name>");
        sb.Append(KmlPoint(planned.Start.Name, planned.Start.Lng, planned.Start.Lat));
        for (var i = 0; i < planned.OrderedStops.Count; i++)
        {
            var s = planned.OrderedStops[i];
            sb.Append(KmlPoint($"{i + 1}. {Escape(s.Name)}", s.Lng, s.Lat));
        }
        sb.Append("</Folder><Folder><name>Road Routes</name>");
        foreach (var chunk in planned.Chunks)
        {
            var destIds = chunk.Stops.Skip(1).ToHashSet();
            var coords = planned.Segments.Where(s => destIds.Contains(s.ToStop))
                .SelectMany(s => s.Geometry)
                .Select(p => $"{p.Lng},{p.Lat},0");
            sb.Append($"<Placemark><name>Route {chunk.RouteNo}</name><LineString><tessellate>1</tessellate><coordinates>{string.Join(" ", coords)}</coordinates></LineString></Placemark>");
        }
        sb.Append("</Folder></Document></kml>");
        File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
    }

    public static void WriteGpx(PlannedRoute planned, string path)
    {
        var sb = new StringBuilder();
        sb.Append("""<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="route-planner" xmlns="http://www.topografix.com/GPX/1/1">""");
        sb.Append(GpxWpt(planned.Start.Name, planned.Start.Lat, planned.Start.Lng));
        for (var i = 0; i < planned.OrderedStops.Count; i++)
        {
            var s = planned.OrderedStops[i];
            sb.Append(GpxWpt($"{i + 1}. {Escape(s.Name)}", s.Lat, s.Lng));
        }
        foreach (var chunk in planned.Chunks)
        {
            var destIds = chunk.Stops.Skip(1).ToHashSet();
            sb.Append($"<trk><name>Route {chunk.RouteNo}</name><trkseg>");
            foreach (var seg in planned.Segments.Where(s => destIds.Contains(s.ToStop)))
            foreach (var p in seg.Geometry)
                sb.Append($"<trkpt lat=\"{p.Lat}\" lon=\"{p.Lng}\"/>");
            sb.Append("</trkseg></trk>");
        }
        sb.Append("</gpx>");
        File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
    }

    public static void WriteHtmlMap(PlannedRoute planned, string path)
    {
        var markers = new List<object>
        {
            new { lat = planned.Start.Lat, lng = planned.Start.Lng, name = planned.Start.Name, order = 0, type = "start" }
        };
        for (var i = 0; i < planned.OrderedStops.Count; i++)
        {
            var s = planned.OrderedStops[i];
            markers.Add(new
            {
                lat = s.Lat, lng = s.Lng, name = s.Name, order = i + 1, type = "destination",
                segment_km = Math.Round(planned.Segments[i].DistanceKm, 2)
            });
        }

        var colors = new[] { "#4285F4", "#EA4335", "#FBBC04", "#34A853", "#FF6D01" };
        var routes = planned.Chunks.Select((c, idx) =>
        {
            var destIds = c.Stops.Skip(1).ToHashSet();
            var coords = planned.Segments.Where(s => destIds.Contains(s.ToStop))
                .SelectMany(s => s.Geometry).Select(p => new[] { p.Lat, p.Lng }).ToList();
            return new
            {
                route_no = c.RouteNo,
                color = colors[idx % colors.Length],
                coords,
                url = c.GoogleMapsUrl,
                distance_km = Math.Round(c.TotalDistanceKm, 2),
                stops = c.Stops.Select(s => s.Name).ToList()
            };
        }).ToList();

        var data = new
        {
            markers,
            routes,
            summary = new
            {
                total_destinations = planned.OrderedStops.Count,
                total_distance_km = Math.Round(planned.TotalDistanceKm, 2),
                total_duration_hours = Math.Round(planned.TotalDurationSec / 3600, 2),
                route_chunks = planned.Chunks.Count
            }
        };

        var json = JsonSerializer.Serialize(data);
        var html = HtmlMapTemplate.Replace("__ROUTE_DATA__", json);
        File.WriteAllText(path, html, Encoding.UTF8);
    }

    public static void WriteBatchIndex(IReadOnlyList<BatchItemResult> items, string path)
    {
        var succeeded = items.Where(i => i.Planned is not null).ToList();
        var failed = items.Count(i => i.Error is not null);
        var totalLoc = succeeded.Sum(i => i.StopCount);

        var cards = new StringBuilder();
        foreach (var item in items)
        {
            if (item.Error is not null)
            {
                cards.Append($"""<div class="card error"><h3>{Escape(item.Name)}</h3><p class="status">Failed: {Escape(item.Error)}</p></div>""");
                continue;
            }
            var planned = item.Planned!;
            var links = string.Join("", planned.Chunks.Select(c =>
            {
                var label = planned.Chunks.Count == 1 ? "Open Routes" : $"Open Routes {c.RouteNo}";
                return $"""<a class="btn" href="{EscapeAttr(c.GoogleMapsUrl)}" target="_blank">{label}</a>""";
            }));
            cards.Append("<div class=\"card\"><h3>").Append(Escape(item.Name)).Append("</h3><p>")
                .Append(item.StopCount).Append(" locations</p><div class=\"actions\">")
                .Append(links).Append("</div></div>");
        }

        var html = "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Excel Routes</title>" +
                   "<style>body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;margin:0;padding:24px}" +
                   ".header{background:#fff;padding:24px;border-radius:12px;margin-bottom:24px}" +
                   ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}" +
                   ".card{background:#fff;border-radius:10px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.06)}" +
                   ".card.error{border-left:4px solid #ea4335}.btn{display:inline-block;padding:8px 14px;background:#4285F4;color:#fff;text-decoration:none;border-radius:6px;font-size:.85rem;margin:2px}" +
                   ".btn.small{background:#34A853}.status{color:#c5221f}</style></head><body>" +
                   "<div class=\"header\"><h1>Excel Routes</h1><p>" +
                   succeeded.Count + " batches · " + failed + " failed · " + totalLoc + " locations</p></div>" +
                   "<div class=\"grid\">" + cards + "</div></body></html>";
        File.WriteAllText(path, html, Encoding.UTF8);
    }

    public static Dictionary<string, string> WriteBatchOutputs(PlannedRoute planned, string outputDir, string prefix)
    {
        Directory.CreateDirectory(outputDir);
        var excel = Path.Combine(outputDir, $"{prefix}.xlsx");
        var kml = Path.Combine(outputDir, $"{prefix}.kml");
        var gpx = Path.Combine(outputDir, $"{prefix}.gpx");
        var html = Path.Combine(outputDir, $"{prefix}_map.html");
        WriteSingleExcel(planned, excel);
        WriteKml(planned, kml);
        WriteGpx(planned, gpx);
        WriteHtmlMap(planned, html);
        return new Dictionary<string, string> { ["excel"] = excel, ["kml"] = kml, ["gpx"] = gpx, ["html"] = html };
    }

    public static Dictionary<string, string> WriteSingleOutputs(PlannedRoute planned, string outputDir)
    {
        Directory.CreateDirectory(outputDir);
        var paths = WriteBatchOutputs(planned, outputDir, "optimized_route");
        var mapPath = Path.Combine(outputDir, "route_map.html");
        File.Copy(paths["html"], mapPath, overwrite: true);
        paths["html"] = mapPath;
        return paths;
    }

    private static string KmlPoint(string name, double lng, double lat) =>
        $"<Placemark><name>{Escape(name)}</name><Point><coordinates>{lng},{lat},0</coordinates></Point></Placemark>";

    private static string GpxWpt(string name, double lat, double lng) =>
        $"<wpt lat=\"{lat}\" lon=\"{lng}\"><name>{Escape(name)}</name></wpt>";

    private static string Escape(string s) =>
        s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");

    private static string EscapeAttr(string s) =>
        Escape(s).Replace("\"", "&quot;");

    private const string HtmlMapTemplate = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Optimized Route Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body{font-family:'Segoe UI',Arial,sans-serif;display:flex;height:100vh;margin:0}
#sidebar{width:380px;overflow-y:auto;background:#f8f9fa;border-right:1px solid #ddd;padding:20px}
#map{flex:1}.stats{background:#fff;border-radius:8px;padding:12px;margin:12px 0;border:1px solid #e0e0e0}
.route-card{background:#fff;border-radius:8px;padding:14px;margin:10px 0;border:1px solid #e0e0e0}
.btn{display:inline-block;margin-top:8px;padding:8px 14px;background:#4285F4;color:#fff;text-decoration:none;border-radius:6px;font-size:.85rem}
</style></head><body>
<div id="sidebar"><h1>Optimized Route</h1><div class="stats" id="summary"></div><div id="route-links"></div></div>
<div id="map"></div><script>
const DATA=__ROUTE_DATA__;
const map=L.map('map').setView([DATA.markers[0].lat,DATA.markers[0].lng],7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap'}).addTo(map);
const bounds=L.latLngBounds();
DATA.markers.forEach(m=>{bounds.extend([m.lat,m.lng]);
const isStart=m.type==='start';const color=isStart?'#0F9D58':'#4285F4';const label=isStart?'S':String(m.order);
const icon=L.divIcon({html:`<div style="background:${color};color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #fff">${label}</div>`,iconSize:[28,28],iconAnchor:[14,14]});
L.marker([m.lat,m.lng],{icon}).addTo(map).bindPopup(`<b>${m.name}</b>`);});
DATA.routes.forEach(r=>{if(r.coords.length>1)L.polyline(r.coords,{color:r.color,weight:4,opacity:.8}).addTo(map);});
map.fitBounds(bounds,{padding:[40,40]});
const s=DATA.summary;
document.getElementById('summary').innerHTML=`<p><b>Destinations:</b> ${s.total_destinations}</p><p><b>Distance:</b> ${s.total_distance_km} km</p><p><b>Drive time:</b> ${s.total_duration_hours} h</p>`;
const links=document.getElementById('route-links');
DATA.routes.forEach(r=>{links.innerHTML+=`<div class="route-card"><h3>Route ${r.route_no} — ${r.distance_km} km</h3><a class="btn" href="${r.url}" target="_blank">Open in Google Maps</a></div>`;});
</script></body></html>
""";
}

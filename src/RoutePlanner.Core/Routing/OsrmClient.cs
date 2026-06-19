using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using RoutePlanner.Core.Configuration;

namespace RoutePlanner.Core.Routing;

public sealed class OsrmClient(HttpClient http, PlannerOptions options, ILogger<OsrmClient>? logger = null)
{
    public async Task<double[,]> BuildDistanceMatrixAsync(
        IReadOnlyList<(double Lat, double Lng)> coords,
        CancellationToken ct = default)
    {
        var n = coords.Count;
        var matrix = new double[n, n];
        var batch = options.OsrmBatchSize;

        for (var srcStart = 0; srcStart < n; srcStart += batch)
        {
            var srcEnd = Math.Min(srcStart + batch, n);
            var srcIndices = Enumerable.Range(srcStart, srcEnd - srcStart).ToList();

            for (var dstStart = 0; dstStart < n; dstStart += batch)
            {
                var dstEnd = Math.Min(dstStart + batch, n);
                var dstIndices = Enumerable.Range(dstStart, dstEnd - dstStart).ToList();
                var combined = srcIndices.Concat(dstIndices.Where(i => !srcIndices.Contains(i))).ToList();
                var indexMap = combined.Select((v, i) => (v, i)).ToDictionary(x => x.v, x => x.i);

                var coordStr = string.Join(";", combined.Select(i => $"{coords[i].Lng:F8},{coords[i].Lat:F8}"));
                var sources = string.Join(";", srcIndices.Select(i => indexMap[i]));
                var destinations = string.Join(";", dstIndices.Select(i => indexMap[i]));

                try
                {
                    var url = $"{options.OsrmBaseUrl.TrimEnd('/')}/table/v1/driving/{coordStr}?annotations=distance&sources={sources}&destinations={destinations}";
                    var response = await http.GetFromJsonAsync<JsonElement>(url, ct);
                    var distances = response.GetProperty("distances");

                    for (var si = 0; si < srcIndices.Count; si++)
                    {
                        for (var di = 0; di < dstIndices.Count; di++)
                        {
                            var val = distances[si][di];
                            matrix[srcIndices[si], dstIndices[di]] = val.ValueKind == JsonValueKind.Null
                                ? GeoUtils.HaversineKm(coords[srcIndices[si]], coords[dstIndices[di]]) * 1000
                                : val.GetDouble();
                        }
                    }
                }
                catch (Exception ex)
                {
                    logger?.LogWarning(ex, "OSRM table batch failed; using Haversine fallback.");
                    foreach (var srcI in srcIndices)
                    foreach (var dstI in dstIndices)
                        matrix[srcI, dstI] = GeoUtils.HaversineKm(coords[srcI], coords[dstI]) * 1000;
                }
            }
        }

        return matrix;
    }

    public async Task<(double DistanceKm, double DurationSec, List<(double Lat, double Lng)> Geometry)> RouteSegmentAsync(
        (double Lat, double Lng) from,
        (double Lat, double Lng) to,
        CancellationToken ct = default)
    {
        try
        {
            var coordStr = $"{from.Lng:F8},{from.Lat:F8};{to.Lng:F8},{to.Lat:F8}";
            var url = $"{options.OsrmBaseUrl.TrimEnd('/')}/route/v1/driving/{coordStr}?overview=full&geometries=geojson&steps=false";
            var response = await http.GetFromJsonAsync<JsonElement>(url, ct);
            var route = response.GetProperty("routes")[0];
            var geometry = route.GetProperty("geometry").GetProperty("coordinates");
            var points = new List<(double Lat, double Lng)>();
            foreach (var pt in geometry.EnumerateArray())
            {
                points.Add((pt[1].GetDouble(), pt[0].GetDouble()));
            }

            return (route.GetProperty("distance").GetDouble() / 1000.0,
                route.GetProperty("duration").GetDouble(),
                points);
        }
        catch (Exception ex)
        {
            logger?.LogWarning(ex, "OSRM route failed; using straight line.");
            return (GeoUtils.HaversineKm(from, to), 0,
                [from, to]);
        }
    }
}

public static class GeoUtils
{
    public static double HaversineKm((double Lat, double Lng) a, (double Lat, double Lng) b)
    {
        const double r = 6371.0;
        var dLat = DegreesToRadians(b.Lat - a.Lat);
        var dLng = DegreesToRadians(b.Lng - a.Lng);
        var x = Math.Sin(dLat / 2) * Math.Sin(dLat / 2) +
                Math.Cos(DegreesToRadians(a.Lat)) * Math.Cos(DegreesToRadians(b.Lat)) *
                Math.Sin(dLng / 2) * Math.Sin(dLng / 2);
        return 2 * r * Math.Asin(Math.Sqrt(x));
    }

    private static double DegreesToRadians(double d) => d * Math.PI / 180.0;
}

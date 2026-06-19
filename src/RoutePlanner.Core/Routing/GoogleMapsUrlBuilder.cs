using RoutePlanner.Core.Models;

namespace RoutePlanner.Core.Routing;

public static class GoogleMapsUrlBuilder
{
    public static string BuildUrl(IReadOnlyList<Stop> stops)
    {
        if (stops.Count < 2)
            throw new ArgumentException("At least origin and destination are required.");

        var origin = Format(stops[0]);
        var destination = Format(stops[^1]);
        var waypoints = stops.Skip(1).Take(stops.Count - 2).Select(Format);

        var url = $"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}";
        var wp = string.Join("|", waypoints);
        if (!string.IsNullOrEmpty(wp)) url += $"&waypoints={wp}";
        return url + "&travelmode=driving";
    }

    public static List<(int RouteNo, List<Stop> Stops, string Url)> SplitIntoChunks(
        Stop start,
        IReadOnlyList<Stop> orderedStops,
        int maxWaypoints)
    {
        if (orderedStops.Count == 0) return [];

        var chunks = new List<(int, List<Stop>, string)>();
        var maxDest = maxWaypoints + 1;
        var routeNo = 1;
        var cursor = 0;
        var currentStart = start;

        while (cursor < orderedStops.Count)
        {
            var batch = orderedStops.Skip(cursor).Take(maxDest).ToList();
            var chunkStops = new List<Stop> { currentStart };
            chunkStops.AddRange(batch);
            chunks.Add((routeNo, chunkStops, BuildUrl(chunkStops)));
            currentStart = batch[^1];
            cursor += batch.Count;
            routeNo++;
        }

        return chunks;
    }

    private static string Format(Stop stop) =>
        Uri.EscapeDataString($"{stop.Lat},{stop.Lng}");
}

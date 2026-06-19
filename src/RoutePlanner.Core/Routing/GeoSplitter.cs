using RoutePlanner.Core.Models;

namespace RoutePlanner.Core.Routing;

public static class GeoSplitter
{
    public static List<List<Stop>> SplitGeographically(IReadOnlyList<Stop> stops, int maxPerBatch)
    {
        if (stops.Count <= maxPerBatch) return [stops.ToList()];

        var nBatches = (int)Math.Ceiling(stops.Count / (double)maxPerBatch);
        var coords = stops.Select(s => (s.Lat, s.Lng)).ToArray();

        var order = coords.Select((c, i) => i).OrderBy(i => coords[i].Lat).ToArray();
        var step = Math.Max(1, order.Length / nBatches);
        var centroids = Enumerable.Range(0, nBatches)
            .Select(i => coords[order[Math.Min(i * step, order.Length - 1)]])
            .Select(c => (Lat: c.Lat, Lng: c.Lng))
            .ToArray();

        var assignments = new int[stops.Count];
        for (var iter = 0; iter < 20; iter++)
        {
            for (var i = 0; i < stops.Count; i++)
            {
                var best = 0;
                var bestDist = double.MaxValue;
                for (var k = 0; k < nBatches; k++)
                {
                    var d = Math.Pow(coords[i].Lat - centroids[k].Lat, 2) + Math.Pow(coords[i].Lng - centroids[k].Lng, 2);
                    if (d < bestDist) { bestDist = d; best = k; }
                }
                assignments[i] = best;
            }

            var changed = false;
            for (var k = 0; k < nBatches; k++)
            {
                var members = Enumerable.Range(0, stops.Count).Where(i => assignments[i] == k).ToList();
                if (members.Count == 0) continue;
                var newLat = members.Average(i => coords[i].Lat);
                var newLng = members.Average(i => coords[i].Lng);
                if (Math.Abs(newLat - centroids[k].Lat) > 1e-6 || Math.Abs(newLng - centroids[k].Lng) > 1e-6)
                    changed = true;
                centroids[k] = (newLat, newLng);
            }
            if (!changed) break;
        }

        var batches = Enumerable.Range(0, nBatches).Select(_ => new List<Stop>()).ToList();
        for (var i = 0; i < stops.Count; i++)
            batches[assignments[i]].Add(stops[i]);

        var result = new List<List<Stop>>();
        var overflow = new List<Stop>();
        foreach (var batch in batches)
        {
            if (batch.Count > maxPerBatch) overflow.AddRange(batch);
            else if (batch.Count > 0) result.Add(batch);
        }

        while (overflow.Count > 0)
        {
            result.Add(overflow.Take(maxPerBatch).ToList());
            overflow = overflow.Skip(maxPerBatch).ToList();
        }

        return result.Count > 0 ? result : [stops.ToList()];
    }
}

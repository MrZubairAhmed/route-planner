using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;
using RoutePlanner.Core.Configuration;
using RoutePlanner.Core.Excel;
using RoutePlanner.Core.Export;
using RoutePlanner.Core.Models;
using RoutePlanner.Core.Routing;

namespace RoutePlanner.Core.Services;

public sealed class RoutePlannerService(OsrmClient osrm, PlannerOptions options, ILogger<RoutePlannerService>? logger = null)
{
    public async Task<PlannedRoute> PlanRouteFromStopsAsync(
        Stop start,
        IReadOnlyList<Stop> destinations,
        string batchName = "",
        string district = "",
        string tehsil = "",
        CancellationToken ct = default)
    {
        var allStops = new List<Stop> { start };
        allStops.AddRange(destinations);
        var coords = allStops.Select(s => (s.Lat, s.Lng)).ToList();

        logger?.LogInformation("Building road distance matrix for {Count} stops...", destinations.Count);
        var matrix = await osrm.BuildDistanceMatrixAsync(coords, ct);

        var orderIndices = RouteOptimizer.OptimizeVisitOrder(matrix, options);
        var orderedStops = orderIndices.Select(i => allStops[i]).ToList();

        var segments = new List<RouteSegment>();
        var totalDistance = 0.0;
        var totalDuration = 0.0;
        var prev = start;

        foreach (var stop in orderedStops)
        {
            double distKm;
            double durSec;
            List<(double Lat, double Lng)> geometry;

            if (options.SkipGeometry)
            {
                distKm = GeoUtils.HaversineKm((prev.Lat, prev.Lng), (stop.Lat, stop.Lng));
                durSec = 0;
                geometry = [(prev.Lat, prev.Lng), (stop.Lat, stop.Lng)];
            }
            else
            {
                (distKm, durSec, geometry) = await osrm.RouteSegmentAsync((prev.Lat, prev.Lng), (stop.Lat, stop.Lng), ct);
            }

            segments.Add(new RouteSegment
            {
                FromStop = prev,
                ToStop = stop,
                DistanceKm = distKm,
                DurationSec = durSec,
                Geometry = geometry
            });
            totalDistance += distKm;
            totalDuration += durSec;
            prev = stop;
        }

        var chunkData = GoogleMapsUrlBuilder.SplitIntoChunks(start, orderedStops, options.MaxWaypointsPerUrl);
        var segmentMap = segments.ToDictionary(s => s.ToStop);
        var chunks = chunkData.Select(c => new RouteChunk
        {
            RouteNo = c.RouteNo,
            Stops = c.Stops,
            GoogleMapsUrl = c.Url,
            TotalDistanceKm = c.Stops.Skip(1).Where(segmentMap.ContainsKey).Sum(s => segmentMap[s].DistanceKm)
        }).ToList();

        return new PlannedRoute
        {
            Start = start,
            OrderedStops = orderedStops,
            Segments = segments,
            Chunks = chunks,
            TotalDistanceKm = totalDistance,
            TotalDurationSec = totalDuration,
            BatchName = batchName,
            District = district,
            Tehsil = tehsil
        };
    }

    public async Task<BatchPlanResult> PlanBatchAsync(
        string inputPath,
        string outputDir,
        BatchMode batchBy = BatchMode.Auto,
        double? startLat = null,
        double? startLng = null,
        string startName = "Start",
        IReadOnlyList<string>? groupFilter = null,
        CancellationToken ct = default)
    {
        Directory.CreateDirectory(outputDir);
        using var data = ExcelReader.Open(inputPath);
        var profile = ExcelFormatAnalyzer.Analyze(data);
        var resolvedBatch = ExcelFormatAnalyzer.ResolveBatchMode(profile, batchBy);

        var (lat, lng) = ExcelReader.ReadStartCoordinates(data, startLat, startLng);
        var start = new Stop { Name = startName, Lat = lat, Lng = lng };

        var groups = resolvedBatch == "none"
            ? ["All Locations"]
            : ExcelReader.ListGroups(data, resolvedBatch);

        if (groupFilter is { Count: > 0 })
        {
            var allowed = groupFilter.Select(g => g.Trim().ToUpperInvariant()).ToHashSet();
            groups = groups.Where(g => allowed.Contains(g.Trim().ToUpperInvariant())).ToList();
        }

        var groupCol = ExcelReader.GroupColumn(data.Mapping, resolvedBatch);
        var items = new List<BatchItemResult>();

        foreach (var groupName in groups)
        {
            var stops = ExcelReader.ToStops(data, groupCol, resolvedBatch == "none" ? null : groupName);
            if (stops.Count == 0) continue;

            var district = resolvedBatch == "district" ? groupName : stops[0].District;
            var tehsil = resolvedBatch == "tehsil" ? groupName : stops[0].Tehsil;
            var subBatches = GeoSplitter.SplitGeographically(stops, options.MaxStopsPerBatch);

            for (var subIdx = 0; subIdx < subBatches.Count; subIdx++)
            {
                var subStops = subBatches[subIdx];
                var batchLabel = subBatches.Count <= 1 ? groupName : $"{groupName} (Part {subIdx + 1})";
                var safeName = SafeDirName(batchLabel);
                var batchDir = Path.Combine(outputDir, safeName);
                Directory.CreateDirectory(batchDir);

                var item = new BatchItemResult
                {
                    Name = batchLabel,
                    District = district,
                    Tehsil = tehsil,
                    StopCount = subStops.Count,
                    OutputDir = batchDir
                };

                try
                {
                    var planned = await PlanRouteFromStopsAsync(
                        start, subStops, batchLabel, district, tehsil, ct);
                    var paths = RouteExporter.WriteBatchOutputs(planned, batchDir, safeName);
                    item.Planned = planned;
                    item.MapHtml = Path.GetFileName(paths["html"]);
                }
                catch (Exception ex)
                {
                    logger?.LogError(ex, "Batch {Name} failed", batchLabel);
                    item.Error = ex.Message;
                }

                items.Add(item);
            }
        }

        var indexHtml = Path.Combine(outputDir, "batch_index.html");
        var masterExcel = Path.Combine(outputDir, "all_routes_master.xlsx");
        RouteExporter.WriteBatchIndex(items, indexHtml);
        RouteExporter.WriteBatchMasterExcel(items, masterExcel);

        return new BatchPlanResult
        {
            Items = items,
            OutputDir = outputDir,
            IndexHtml = indexHtml,
            MasterExcel = masterExcel,
            Succeeded = items.Count(i => i.Planned is not null),
            Failed = items.Count(i => i.Error is not null),
            TotalLocations = items.Where(i => i.Planned is not null).Sum(i => i.StopCount),
            TotalDistanceKm = items.Where(i => i.Planned is not null).Sum(i => i.Planned!.TotalDistanceKm)
        };
    }

    public async Task<ProcessResult> ProcessExcelAsync(
        string inputPath,
        string outputDir,
        BatchMode batchBy = BatchMode.Auto,
        double? startLat = null,
        double? startLng = null,
        string startName = "Start",
        IReadOnlyList<string>? groupFilter = null,
        CancellationToken ct = default)
    {
        var profile = ExcelFormatAnalyzer.Analyze(inputPath);
        var opts = options;
        if (profile.RecommendedSkipGeometry && !opts.SkipGeometry)
            opts = new PlannerOptions
            {
                OsrmBaseUrl = options.OsrmBaseUrl,
                MaxWaypointsPerUrl = options.MaxWaypointsPerUrl,
                OsrmBatchSize = options.OsrmBatchSize,
                Optimizer = options.Optimizer,
                MaxOrToolsNodes = options.MaxOrToolsNodes,
                MaxStopsPerBatch = options.MaxStopsPerBatch,
                RequestTimeoutSeconds = options.RequestTimeoutSeconds,
                HaversineFallback = options.HaversineFallback,
                SkipGeometry = true
            };

        var resolved = ExcelFormatAnalyzer.ResolveBatchMode(profile, batchBy);
        Directory.CreateDirectory(outputDir);

        if (resolved != "none")
        {
            var batch = await PlanBatchAsync(inputPath, outputDir, batchBy, startLat, startLng, startName, groupFilter, ct);
            return new ProcessResult
            {
                Profile = profile,
                Mode = "batch",
                BatchBy = resolved,
                Batch = batch,
                OutputDir = outputDir,
                OutputPaths = new Dictionary<string, string>
                {
                    ["index"] = batch.IndexHtml,
                    ["excel"] = batch.MasterExcel
                }
            };
        }

        using var data = ExcelReader.Open(inputPath);
        var (lat, lng) = ExcelReader.ReadStartCoordinates(data, startLat ?? profile.StartLat, startLng ?? profile.StartLng);
        var start = new Stop { Name = startName, Lat = lat, Lng = lng };
        var destinations = ExcelReader.ToStops(data);
        var planned = await PlanRouteFromStopsAsync(start, destinations, ct: ct);
        var paths = RouteExporter.WriteSingleOutputs(planned, outputDir);

        return new ProcessResult
        {
            Profile = profile,
            Mode = "single",
            BatchBy = "none",
            Single = planned,
            OutputDir = outputDir,
            OutputPaths = paths
        };
    }

    private static string SafeDirName(string name)
    {
        var safe = Regex.Replace(name, @"[^\w\s-]", "");
        safe = Regex.Replace(safe.Trim(), @"\s+", "_");
        return safe.Length > 80 ? safe[..80] : safe;
    }
}

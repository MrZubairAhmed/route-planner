namespace RoutePlanner.Core.Models;

public sealed class Stop
{
    public required string Name { get; init; }
    public double Lat { get; init; }
    public double Lng { get; init; }
    public string LocationCode { get; init; } = "";
    public string District { get; init; } = "";
    public string Tehsil { get; init; } = "";
    public int OriginalIndex { get; init; }
}

public sealed class RouteSegment
{
    public Stop? FromStop { get; init; }
    public required Stop ToStop { get; init; }
    public double DistanceKm { get; init; }
    public double DurationSec { get; init; }
    public List<(double Lat, double Lng)> Geometry { get; init; } = [];
}

public sealed class RouteChunk
{
    public int RouteNo { get; init; }
    public List<Stop> Stops { get; init; } = [];
    public required string GoogleMapsUrl { get; init; }
    public double TotalDistanceKm { get; init; }
}

public sealed class PlannedRoute
{
    public required Stop Start { get; init; }
    public List<Stop> OrderedStops { get; init; } = [];
    public List<RouteSegment> Segments { get; init; } = [];
    public List<RouteChunk> Chunks { get; init; } = [];
    public double TotalDistanceKm { get; init; }
    public double TotalDurationSec { get; init; }
    public string BatchName { get; init; } = "";
    public string District { get; init; } = "";
    public string Tehsil { get; init; } = "";
}

public sealed class BatchItemResult
{
    public required string Name { get; init; }
    public string District { get; init; } = "";
    public string Tehsil { get; init; } = "";
    public int StopCount { get; init; }
    public PlannedRoute? Planned { get; set; }
    public string? Error { get; set; }
    public string? OutputDir { get; set; }
    public string MapHtml { get; set; } = "";
}

public sealed class BatchPlanResult
{
    public List<BatchItemResult> Items { get; init; } = [];
    public required string OutputDir { get; init; }
    public required string IndexHtml { get; init; }
    public required string MasterExcel { get; init; }
    public int TotalLocations { get; init; }
    public double TotalDistanceKm { get; init; }
    public int Succeeded { get; init; }
    public int Failed { get; init; }
}

public sealed record ExcelProfile
{
    public int RowCount { get; init; }
    public int DestinationCount { get; init; }
    public bool HasStart { get; init; }
    public double? StartLat { get; init; }
    public double? StartLng { get; init; }
    public int DistrictCount { get; init; }
    public int TehsilCount { get; init; }
    public List<string> Districts { get; init; } = [];
    public List<string> Tehsils { get; init; } = [];
    public string RecommendedBatchBy { get; init; } = "none";
    public bool RecommendedSkipGeometry { get; init; }
    public List<string> Warnings { get; init; } = [];

    public string Summary()
    {
        var parts = new List<string> { $"{DestinationCount} destinations" };
        if (HasStart) parts.Add("start point detected");
        if (RecommendedBatchBy != "none") parts.Add($"batch by {RecommendedBatchBy}");
        return string.Join(" · ", parts);
    }
}

public sealed class ProcessResult
{
    public required ExcelProfile Profile { get; init; }
    public required string Mode { get; init; }
    public required string BatchBy { get; init; }
    public PlannedRoute? Single { get; init; }
    public BatchPlanResult? Batch { get; init; }
    public string? OutputDir { get; init; }
    public Dictionary<string, string> OutputPaths { get; init; } = new();

    public int DestinationCount => Mode == "batch" ? Batch?.TotalLocations ?? 0 : Single?.OrderedStops.Count ?? 0;
    public double TotalDistanceKm => Mode == "batch" ? Batch?.TotalDistanceKm ?? 0 : Single?.TotalDistanceKm ?? 0;
}

public enum BatchMode { Auto, None, District, Tehsil }

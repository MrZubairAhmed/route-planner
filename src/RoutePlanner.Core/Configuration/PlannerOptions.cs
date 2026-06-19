namespace RoutePlanner.Core.Configuration;

public sealed class PlannerOptions
{
    public string OsrmBaseUrl { get; set; } = "https://router.project-osrm.org";
    public int MaxWaypointsPerUrl { get; set; } = 23;
    public int OsrmBatchSize { get; set; } = 50;
    public OptimizerMode Optimizer { get; set; } = OptimizerMode.OrTools;
    public int MaxOrToolsNodes { get; set; } = 500;
    public int MaxStopsPerBatch { get; set; } = 150;
    public int RequestTimeoutSeconds { get; set; } = 60;
    public bool HaversineFallback { get; set; } = true;
    public bool SkipGeometry { get; set; }
}

public enum OptimizerMode { OrTools, NearestNeighbor }

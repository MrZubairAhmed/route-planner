using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using RoutePlanner.Core;
using RoutePlanner.Core.Configuration;
using RoutePlanner.Core.Excel;
using RoutePlanner.Core.Models;
using RoutePlanner.Core.Services;

if (args.Length >= 1 && args[0] == "--create-template")
{
    var path = args.Length > 1 ? args[1] : "route_planner_template.xlsx";
    ExcelReader.WriteTemplate(path);
    Console.WriteLine($"Template written to: {Path.GetFullPath(path)}");
    return;
}

string? input = null, output = "output";
BatchMode batchBy = BatchMode.Auto;
double? startLat = null, startLng = null;
var groupFilter = new List<string>();

for (var i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "-i" or "--input": input = args[++i]; break;
        case "-o" or "--output-dir": output = args[++i]; break;
        case "--start-lat": startLat = double.Parse(args[++i]); break;
        case "--start-lng": startLng = double.Parse(args[++i]); break;
        case "--batch-by": batchBy = args[++i] switch { "none" => BatchMode.None, "district" => BatchMode.District, "tehsil" => BatchMode.Tehsil, _ => BatchMode.Auto }; break;
        case "--group-filter": groupFilter = args[++i].Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries).ToList(); break;
    }
}

if (string.IsNullOrEmpty(input))
{
    Console.WriteLine("Usage: RoutePlanner.Cli -i <excel-file> [-o output-dir] [--batch-by auto|none|district|tehsil]");
    Console.WriteLine("       RoutePlanner.Cli --create-template [path]");
    return;
}

var services = new ServiceCollection();
services.AddLogging(b => b.AddConsole());
services.AddRoutePlanner();
var sp = services.BuildServiceProvider();
var planner = sp.GetRequiredService<RoutePlannerService>();

Console.WriteLine($"Processing: {input}");
var result = await planner.ProcessExcelAsync(
    input, output, batchBy, startLat, startLng,
    groupFilter: groupFilter.Count > 0 ? groupFilter : null);

Console.WriteLine($"\n=== Complete ({result.Mode}, batch={result.BatchBy}) ===");
Console.WriteLine($"Destinations: {result.DestinationCount}");
Console.WriteLine($"Distance:     {result.TotalDistanceKm:F1} km");
foreach (var (k, v) in result.OutputPaths)
    Console.WriteLine($"  {k}: {Path.GetFullPath(v)}");

if (result.Mode == "batch" && result.Batch is not null)
    foreach (var item in result.Batch.Items)
        Console.WriteLine(item.Error is null
            ? $"  [OK] {item.Name}: {item.StopCount} locations"
            : $"  [FAIL] {item.Name}: {item.Error}");

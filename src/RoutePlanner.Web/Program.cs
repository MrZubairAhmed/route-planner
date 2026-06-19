using RoutePlanner.Core;
using RoutePlanner.Core.Configuration;
using RoutePlanner.Core.Excel;
using RoutePlanner.Core.Models;
using RoutePlanner.Core.Services;
using Microsoft.AspNetCore.Http.Features;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.Limits.MaxRequestBodySize = 100 * 1024 * 1024;
    options.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(10);
    options.Limits.RequestHeadersTimeout = TimeSpan.FromMinutes(2);
});

builder.Services.Configure<FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = 100 * 1024 * 1024;
});

builder.Services.AddRoutePlanner(opts =>
{
    opts.MaxWaypointsPerUrl = 23;
    opts.MaxStopsPerBatch = 150;
});

builder.Services.AddSingleton<JobStore>();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8080";
builder.WebHost.UseUrls($"http://0.0.0.0:{port}");

var app = builder.Build();

app.UseStaticFiles();
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));
app.MapGet("/", () => Results.Redirect("/index.html"));
app.MapGet("/index.html", () => Results.Content(File.ReadAllText(Path.Combine(app.Environment.WebRootPath, "index.html")), "text/html"));

app.MapGet("/api/template", () =>
{
    var path = Path.Combine(Path.GetTempPath(), "route_planner_template.xlsx");
    ExcelReader.WriteTemplate(path);
    return Results.File(path, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "route_planner_template.xlsx");
});

app.MapPost("/api/preview", async (HttpRequest request, JobStore jobs) =>
{
    if (!request.HasFormContentType) return Results.BadRequest(new { error = "Expected multipart form" });
    var file = request.Form.Files.GetFile("file");
    if (file is null || file.Length == 0) return Results.BadRequest(new { error = "No file uploaded" });

    var jobId = Guid.NewGuid().ToString("N")[..8];
    var jobDir = jobs.CreateJob(jobId);
    var inputPath = Path.Combine(jobDir, "input.xlsx");
    await using (var fs = File.Create(inputPath))
        await file.CopyToAsync(fs);

    try
    {
        var profile = ExcelFormatAnalyzer.Analyze(inputPath);
        return Results.Ok(new
        {
            job_id = jobId,
            rows = profile.RowCount,
            destinations = profile.DestinationCount,
            has_start = profile.HasStart,
            start_lat = profile.StartLat,
            start_lng = profile.StartLng,
            districts = profile.Districts,
            tehsils = profile.Tehsils,
            recommended_batch_by = profile.RecommendedBatchBy,
            recommended_skip_geometry = profile.RecommendedSkipGeometry,
            warnings = profile.Warnings,
            summary = profile.Summary()
        });
    }
    catch (Exception ex)
    {
        jobs.DeleteJob(jobId);
        return Results.BadRequest(new { error = ex.Message });
    }
});

app.MapPost("/plan", async (
    HttpRequest request,
    RoutePlannerService planner,
    JobStore jobs,
    PlannerOptions options) =>
{
    if (!request.HasFormContentType) return Results.BadRequest();
    var form = await request.ReadFormAsync();
    var jobId = form["job_id"].ToString();
    if (string.IsNullOrWhiteSpace(jobId)) return Results.Redirect("/");

    var inputPath = jobs.GetInputPath(jobId);
    if (!File.Exists(inputPath)) return Results.Text("Upload expired. Please upload again.", "text/html");

    var outputDir = jobs.GetOutputPath(jobId);
    var batchBy = ParseBatchMode(form["batch_by"].ToString());
    if (form["skip_geometry"] == "on") options.SkipGeometry = true;
    if (Enum.TryParse<OptimizerMode>(form["optimizer"].ToString(), true, out var opt))
        options.Optimizer = opt;
    if (int.TryParse(form["max_waypoints"], out var mw)) options.MaxWaypointsPerUrl = mw;
    if (int.TryParse(form["max_stops_per_batch"], out var ms)) options.MaxStopsPerBatch = ms;

    double? startLat = double.TryParse(form["start_lat"], out var slat) ? slat : null;
    double? startLng = double.TryParse(form["start_lng"], out var slng) ? slng : null;
    var filter = form["group_filter"].ToString().Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
    if (filter.Count == 0) filter = null;

    try
    {
        var result = await planner.ProcessExcelAsync(inputPath, outputDir, batchBy, startLat, startLng, groupFilter: filter);
        return Results.Redirect(result.Mode == "batch" ? $"/results/batch/{jobId}" : $"/results/single/{jobId}");
    }
    catch (Exception ex)
    {
        return Results.Content($"<html><body><h1>Error</h1><p>{ex.Message}</p><a href='/'>Back</a></body></html>", "text/html");
    }
});

app.MapGet("/results/single/{jobId}", (string jobId, JobStore jobs) =>
{
    var outputDir = jobs.GetOutputPath(jobId);
    if (!Directory.Exists(outputDir)) return Results.NotFound();
    return Results.Content(SingleResultHtml(jobId), "text/html");
});

app.MapGet("/results/batch/{jobId}", (string jobId, JobStore jobs) =>
{
    var indexPath = Path.Combine(jobs.GetOutputPath(jobId), "batch_index.html");
    if (!File.Exists(indexPath)) return Results.NotFound();
    return Results.Content(File.ReadAllText(indexPath), "text/html");
});

app.MapGet("/files/{jobId}/{**filename}", (string jobId, string filename, JobStore jobs) =>
{
    var path = Path.Combine(jobs.GetOutputPath(jobId), filename.Replace('/', Path.DirectorySeparatorChar));
    if (!File.Exists(path)) return Results.NotFound();
    return Results.File(path);
});

app.Run();

static BatchMode ParseBatchMode(string value) => value?.ToLowerInvariant() switch
{
    "none" => BatchMode.None,
    "district" => BatchMode.District,
    "tehsil" => BatchMode.Tehsil,
    _ => BatchMode.Auto
};

static string SingleResultHtml(string jobId) => $$"""
<!DOCTYPE html><html><head><title>Routes Generated</title>
<style>body{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;padding:24px}
.card{background:#fff;border-radius:12px;padding:28px;max-width:640px;margin:0 auto;box-shadow:0 2px 12px rgba(0,0,0,.08)}
.btn{display:inline-block;padding:10px 18px;background:#4285F4;color:#fff;text-decoration:none;border-radius:8px;margin:6px 6px 0 0}
</style></head><body><div class="card"><h1>Routes Generated</h1>
<a class="btn" href="/files/{{jobId}}/route_map.html" target="_blank">Open Interactive Map</a>
<a class="btn" href="/files/{{jobId}}/optimized_route.xlsx">Download Excel</a>
<a class="btn" href="/files/{{jobId}}/optimized_route.kml">Download KML</a>
<a class="btn" href="/files/{{jobId}}/optimized_route.gpx">Download GPX</a>
<p style="margin-top:20px"><a href="/">Plan another route</a></p></div></body></html>
""";

sealed class JobStore
{
    private readonly string _root = Path.Combine(Directory.GetCurrentDirectory(), "web_jobs");

    public string CreateJob(string jobId)
    {
        var dir = Path.Combine(_root, jobId);
        Directory.CreateDirectory(dir);
        return dir;
    }

    public void DeleteJob(string jobId)
    {
        var dir = Path.Combine(_root, jobId);
        if (Directory.Exists(dir)) Directory.Delete(dir, true);
    }

    public string GetInputPath(string jobId) => Path.Combine(_root, jobId, "input.xlsx");
    public string GetOutputPath(string jobId) => Path.Combine(_root, jobId, "output");
}

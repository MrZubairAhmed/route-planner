using System.Text.RegularExpressions;
using ClosedXML.Excel;
using RoutePlanner.Core.Models;

namespace RoutePlanner.Core.Excel;

public sealed class ColumnMapping
{
    public required int LatCol { get; init; }
    public required int LngCol { get; init; }
    public int? NameCol { get; init; }
    public int? CodeCol { get; init; }
    public int? StartLatCol { get; init; }
    public int? StartLngCol { get; init; }
    public int? DistrictCol { get; init; }
    public int? TehsilCol { get; init; }
}

public sealed class RouteExcelData : IDisposable
{
    private readonly XLWorkbook _workbook;

    public RouteExcelData(string path)
    {
        _workbook = new XLWorkbook(path);
        Sheet = _workbook.Worksheet(1);
        var headerCells = Sheet.Row(1).CellsUsed().ToList();
        var headers = headerCells.Select(c => c.GetString()).ToList();
        Mapping = ColumnResolver.Resolve(headers, headerCells);
    }

    public IXLWorksheet Sheet { get; }
    public ColumnMapping Mapping { get; }
    public void Dispose() => _workbook.Dispose();
}

public static class ExcelReader
{
    public static RouteExcelData Open(string path) => new(path);

    public static (double Lat, double Lng) ReadStartCoordinates(
        RouteExcelData data,
        double? overrideLat = null,
        double? overrideLng = null)
    {
        if (overrideLat.HasValue && overrideLng.HasValue)
            return (overrideLat.Value, overrideLng.Value);

        var m = data.Mapping;
        if (m.StartLatCol is null || m.StartLngCol is null)
            throw new InvalidOperationException(
                "Start coordinates not found. Include Start LAT / Start LNG columns or provide them manually.");

        foreach (var row in data.Sheet.RowsUsed().Skip(1))
        {
            var lat = CoerceDouble(row.Cell(m.StartLatCol.Value).GetString());
            var lng = CoerceDouble(row.Cell(m.StartLngCol.Value).GetString());
            if (lat.HasValue && lng.HasValue)
                return (lat.Value, lng.Value);
        }

        throw new InvalidOperationException("Start LAT / Start LNG columns exist but contain no valid values.");
    }

    public static List<Stop> ToStops(RouteExcelData data, int? groupColumn = null, string? groupValue = null)
    {
        var m = data.Mapping;
        var stops = new List<Stop>();
        var seen = new HashSet<(double, double)>();

        foreach (var row in data.Sheet.RowsUsed().Skip(1))
        {
            if (groupColumn.HasValue && groupValue is not null)
            {
                var gv = row.Cell(groupColumn.Value).GetString().Trim();
                if (!string.Equals(gv, groupValue.Trim(), StringComparison.OrdinalIgnoreCase))
                    continue;
            }

            var lat = CoerceDouble(row.Cell(m.LatCol).GetString());
            var lng = CoerceDouble(row.Cell(m.LngCol).GetString());
            if (!lat.HasValue || !lng.HasValue) continue;

            var key = (Math.Round(lat.Value, 6), Math.Round(lng.Value, 6));
            if (!seen.Add(key)) continue;

            var name = m.NameCol.HasValue ? row.Cell(m.NameCol.Value).GetString().Trim() : "";
            if (string.IsNullOrWhiteSpace(name)) name = $"Stop {stops.Count + 1}";

            stops.Add(new Stop
            {
                Name = name,
                Lat = lat.Value,
                Lng = lng.Value,
                LocationCode = m.CodeCol.HasValue ? row.Cell(m.CodeCol.Value).GetString().Trim() : "",
                District = m.DistrictCol.HasValue ? row.Cell(m.DistrictCol.Value).GetString().Trim() : "",
                Tehsil = m.TehsilCol.HasValue ? row.Cell(m.TehsilCol.Value).GetString().Trim() : "",
                OriginalIndex = row.RowNumber()
            });
        }

        return stops;
    }

    public static List<string> ListGroups(RouteExcelData data, string groupBy)
    {
        var col = GroupColumn(data.Mapping, groupBy);
        if (col is null) return ["All Locations"];

        return data.Sheet.RowsUsed().Skip(1)
            .Select(r => r.Cell(col.Value).GetString().Trim())
            .Where(v => !string.IsNullOrWhiteSpace(v))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(v => v, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public static int? GroupColumn(ColumnMapping mapping, string groupBy) => groupBy switch
    {
        "district" => mapping.DistrictCol,
        "tehsil" => mapping.TehsilCol,
        _ => null
    };

    public static void WriteTemplate(string path)
    {
        using var wb = new XLWorkbook();
        var ws = wb.AddWorksheet("Locations");
        ws.Cell(1, 1).Value = "SchoolCode";
        ws.Cell(1, 2).Value = "Name";
        ws.Cell(1, 3).Value = "District";
        ws.Cell(1, 4).Value = "Tehsil";
        ws.Cell(1, 5).Value = "Latitude";
        ws.Cell(1, 6).Value = "Longitude";
        ws.Cell(1, 7).Value = "Start LAT";
        ws.Cell(1, 8).Value = "Start LNG";
        ws.Cell(2, 1).Value = "LOC-001";
        ws.Cell(2, 2).Value = "Example Location A";
        ws.Cell(2, 3).Value = "DISTRICT_A";
        ws.Cell(2, 4).Value = "TEHSIL_1";
        ws.Cell(2, 5).Value = 31.5204;
        ws.Cell(2, 6).Value = 74.3587;
        ws.Cell(2, 7).Value = 31.5354;
        ws.Cell(2, 8).Value = 74.3442;
        ws.Cell(3, 1).Value = "LOC-002";
        ws.Cell(3, 2).Value = "Example Location B";
        ws.Cell(3, 3).Value = "DISTRICT_A";
        ws.Cell(3, 4).Value = "TEHSIL_1";
        ws.Cell(3, 5).Value = 31.5497;
        ws.Cell(3, 6).Value = 74.3436;
        ws.Cell(3, 7).Value = 31.5354;
        ws.Cell(3, 8).Value = 74.3442;
        wb.SaveAs(path);
    }

    private static double? CoerceDouble(string value)
    {
        if (string.IsNullOrWhiteSpace(value)) return null;
        return double.TryParse(value, out var d) ? d : null;
    }
}

internal static class ColumnResolver
{
    public static ColumnMapping Resolve(IReadOnlyList<string> headers, IReadOnlyList<IXLCell> headerCells)
    {
        int ColIndex(string name) => headerCells.First(c =>
            string.Equals(c.GetString().Trim(), name, StringComparison.OrdinalIgnoreCase)).Address.ColumnNumber;

        var latName = FindColumn(headers, "Latitude", "Lat", "Dest Latitude", "Destination Latitude", "Y")
                      ?? throw new InvalidOperationException("Excel must contain a Latitude column.");
        var lngName = FindColumn(headers, "Longitude", "Lng", "Long", "Dest Longitude", "Destination Longitude", "X")
                      ?? throw new InvalidOperationException("Excel must contain a Longitude column.");

        int? OptionalCol(params string[] candidates)
        {
            var name = FindColumn(headers, candidates);
            return name is null ? null : ColIndex(name);
        }

        return new ColumnMapping
        {
            LatCol = ColIndex(latName),
            LngCol = ColIndex(lngName),
            NameCol = OptionalCol("Name", "Location Name", "Place Name", "Site Name", "Destination", "Destination Name", "School Name", "Stop Name"),
            CodeCol = OptionalCol("SchoolCode", "School Code", "Code", "Location Code", "ID", "Ref"),
            StartLatCol = OptionalCol("Start LAT", "Start Lat", "Start Latitude", "Origin Lat", "Origin Latitude", "Depot Lat"),
            StartLngCol = OptionalCol("Start LNG", "Start Lng", "Start Longitude", "Origin Lng", "Origin Longitude", "Depot Lng"),
            DistrictCol = OptionalCol("District", "Region", "Area"),
            TehsilCol = OptionalCol("Tehsil", "Tehsil Name", "Sub District", "Sub-District")
        };
    }

    private static string? FindColumn(IReadOnlyList<string> columns, params string[] candidates)
    {
        var normalized = columns.ToDictionary(c => Normalize(c), c => c, StringComparer.OrdinalIgnoreCase);
        foreach (var candidate in candidates)
        {
            if (normalized.TryGetValue(Normalize(candidate), out var col))
                return col;
        }
        return null;
    }

    private static string Normalize(string name) =>
        Regex.Replace(name.Trim(), @"\s+", " ").ToLowerInvariant();
}

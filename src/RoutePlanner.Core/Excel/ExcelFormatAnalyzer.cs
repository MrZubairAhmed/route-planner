using RoutePlanner.Core.Excel;
using RoutePlanner.Core.Models;

namespace RoutePlanner.Core.Excel;

public static class ExcelFormatAnalyzer
{
    public static ExcelProfile Analyze(string path)
    {
        using var data = ExcelReader.Open(path);
        return Analyze(data);
    }

    public static ExcelProfile Analyze(RouteExcelData data)
    {
        var destinations = ExcelReader.ToStops(data);
        if (destinations.Count == 0)
            throw new InvalidOperationException("No valid destination rows found. Check Latitude and Longitude values.");

        var warnings = new List<string>();
        var districts = data.Mapping.DistrictCol.HasValue ? ExcelReader.ListGroups(data, "district") : [];
        var tehsils = data.Mapping.TehsilCol.HasValue ? ExcelReader.ListGroups(data, "tehsil") : [];

        var hasStartCols = data.Mapping.StartLatCol.HasValue && data.Mapping.StartLngCol.HasValue;
        double? startLat = null, startLng = null;
        var hasStart = false;

        if (hasStartCols)
        {
            try
            {
                (startLat, startLng) = ExcelReader.ReadStartCoordinates(data);
                hasStart = true;
            }
            catch
            {
                warnings.Add("Start LAT/LNG columns exist but contain no valid values.");
            }
        }
        else
        {
            warnings.Add("No start coordinates in file — provide Start LAT and Start LNG columns.");
        }

        var destinationCount = destinations.Count;
        if (destinationCount > 500)
            warnings.Add($"Large dataset ({destinationCount} destinations). Processing may take a while.");

        var recommended = districts.Count > 1 ? "district" : tehsils.Count > 1 ? "tehsil" : "none";

        return new ExcelProfile
        {
            RowCount = data.Sheet.RowsUsed().Count() - 1,
            DestinationCount = destinationCount,
            HasStart = hasStart,
            StartLat = startLat,
            StartLng = startLng,
            DistrictCount = districts.Count,
            TehsilCount = tehsils.Count,
            Districts = districts,
            Tehsils = tehsils,
            RecommendedBatchBy = recommended,
            RecommendedSkipGeometry = destinationCount > 100,
            Warnings = warnings
        };
    }

    public static string ResolveBatchMode(ExcelProfile profile, BatchMode batchBy) => batchBy switch
    {
        BatchMode.Auto => profile.RecommendedBatchBy,
        BatchMode.None => "none",
        BatchMode.District => "district",
        BatchMode.Tehsil => "tehsil",
        _ => profile.RecommendedBatchBy
    };
}

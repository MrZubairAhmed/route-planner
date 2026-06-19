from pathlib import Path

import pandas as pd

from ..models import PlannedRoute


def write_excel(planned: PlannedRoute, output_path: Path) -> Path:
    """Write optimized route details to Excel."""
    rows = []
    cumulative = 0.0

    stop_to_route: dict[int, int] = {}
    stop_to_url: dict[int, str] = {}
    for chunk in planned.chunks:
        for stop in chunk.stops[1:]:
            stop_to_route[id(stop)] = chunk.route_no
            stop_to_url[id(stop)] = chunk.google_maps_url

    rows.append(
        {
            "VisitOrder": 0,
            "BatchName": planned.batch_name,
            "District": planned.district,
            "Tehsil": planned.tehsil,
            "Name": planned.start.name,
            "SchoolCode": "",
            "Latitude": planned.start.lat,
            "Longitude": planned.start.lng,
            "RouteNo": 1,
            "SegmentDistance_km": 0.0,
            "CumulativeDistance_km": 0.0,
            "GoogleMapsURL": planned.chunks[0].google_maps_url if planned.chunks else "",
            "StopType": "Start",
        }
    )

    for order, (segment, stop) in enumerate(zip(planned.segments, planned.ordered_stops), start=1):
        cumulative += segment.distance_km
        rows.append(
            {
                "VisitOrder": order,
                "BatchName": planned.batch_name,
                "District": stop.district or planned.district,
                "Tehsil": stop.tehsil or planned.tehsil,
                "Name": stop.name,
                "SchoolCode": stop.school_code,
                "Latitude": stop.lat,
                "Longitude": stop.lng,
                "RouteNo": stop_to_route.get(id(stop), 1),
                "SegmentDistance_km": round(segment.distance_km, 2),
                "CumulativeDistance_km": round(cumulative, 2),
                "GoogleMapsURL": stop_to_url.get(id(stop), ""),
                "StopType": "Destination",
            }
        )

    df = pd.DataFrame(rows)

    summary_rows = [
        {
            "Metric": "Total Destinations",
            "Value": len(planned.ordered_stops),
        },
        {
            "Metric": "Total Distance (km)",
            "Value": round(planned.total_distance_km, 2),
        },
        {
            "Metric": "Total Duration (hours)",
            "Value": round(planned.total_duration_sec / 3600, 2),
        },
        {
            "Metric": "Route Chunks (Google Maps URLs)",
            "Value": len(planned.chunks),
        },
    ]
    summary_df = pd.DataFrame(summary_rows)

    route_urls = pd.DataFrame(
        [
            {
                "RouteNo": c.route_no,
                "StopsInChunk": len(c.stops),
                "Distance_km": round(c.total_distance_km, 2),
                "GoogleMapsURL": c.google_maps_url,
            }
            for c in planned.chunks
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="VisitOrder", index=False)
        route_urls.to_excel(writer, sheet_name="GoogleMapsURLs", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

    return output_path


def write_batch_master_excel(items: list, output_path: Path) -> Path:
    """Combine all successful batch routes into one master Excel workbook."""
    from ..models import BatchItemResult

    all_rows = []
    batch_summary = []

    for item in items:
        if not isinstance(item, BatchItemResult) or item.planned is None:
            continue
        planned = item.planned

        stop_to_route: dict[int, int] = {}
        stop_to_url: dict[int, str] = {}
        for chunk in planned.chunks:
            for stop in chunk.stops[1:]:
                stop_to_route[id(stop)] = chunk.route_no
                stop_to_url[id(stop)] = chunk.google_maps_url

        all_rows.append(
            {
                "BatchName": item.name,
                "District": item.district,
                "Tehsil": item.tehsil,
                "VisitOrder": 0,
                "Name": planned.start.name,
                "SchoolCode": "",
                "Latitude": planned.start.lat,
                "Longitude": planned.start.lng,
                "RouteNo": 1,
                "SegmentDistance_km": 0.0,
                "CumulativeDistance_km": 0.0,
                "GoogleMapsURL": planned.chunks[0].google_maps_url if planned.chunks else "",
                "StopType": "Start",
            }
        )

        cumulative = 0.0
        for order, (segment, stop) in enumerate(zip(planned.segments, planned.ordered_stops), start=1):
            cumulative += segment.distance_km
            all_rows.append(
                {
                    "BatchName": item.name,
                    "District": stop.district or item.district,
                    "Tehsil": stop.tehsil or item.tehsil,
                    "VisitOrder": order,
                    "Name": stop.name,
                    "SchoolCode": stop.school_code,
                    "Latitude": stop.lat,
                    "Longitude": stop.lng,
                    "RouteNo": stop_to_route.get(id(stop), 1),
                    "SegmentDistance_km": round(segment.distance_km, 2),
                    "CumulativeDistance_km": round(cumulative, 2),
                    "GoogleMapsURL": stop_to_url.get(id(stop), ""),
                    "StopType": "Destination",
                }
            )

        batch_summary.append(
            {
                "BatchName": item.name,
                "District": item.district,
                "Tehsil": item.tehsil,
                "Schools": item.stop_count,
                "TotalDistance_km": round(planned.total_distance_km, 2),
                "Duration_hours": round(planned.total_duration_sec / 3600, 2),
                "GoogleMapsChunks": len(planned.chunks),
                "MapFile": f"{item.output_dir.name}/{item.map_html}" if item.output_dir else "",
            }
        )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(all_rows).to_excel(writer, sheet_name="AllVisitOrders", index=False)
        pd.DataFrame(batch_summary).to_excel(writer, sheet_name="BatchSummary", index=False)

    return output_path

import logging
import re
from pathlib import Path

from .config import PlannerConfig
from .excel_reader import (
    dataframe_to_stops,
    list_groups,
    read_school_dataframe,
    read_start_coordinates,
    resolve_columns,
    split_stops_geographically,
    _group_column,
)
from .google_maps import split_into_route_chunks
from .models import BatchItemResult, BatchPlanResult, PlannedRoute, RouteChunk, RouteSegment, Stop
from .optimizer import optimize_visit_order
from .osrm_client import OSRMClient

logger = logging.getLogger(__name__)


def plan_route_from_stops(
    start: Stop,
    destinations: list[Stop],
    config: PlannerConfig | None = None,
    batch_name: str = "",
    district: str = "",
    tehsil: str = "",
) -> PlannedRoute:
    """Optimize and route a stop list without reading from Excel."""
    config = config or PlannerConfig()
    all_stops = [start] + destinations
    coords = [(s.lat, s.lng) for s in all_stops]

    osrm = OSRMClient(config)
    logger.info("Building road distance matrix for %d stops...", len(destinations))
    distance_matrix = osrm.build_distance_matrix(coords)

    logger.info("Optimizing visit order (%s)...", config.optimizer)
    order_indices = optimize_visit_order(distance_matrix, config, start_index=0)
    ordered_stops = [all_stops[i] for i in order_indices]

    segments: list[RouteSegment] = []
    total_distance = 0.0
    total_duration = 0.0
    prev: Stop = start

    for stop in ordered_stops:
        if config.skip_geometry:
            from .osrm_client import haversine_km

            dist_km = haversine_km(prev.lat, prev.lng, stop.lat, stop.lng)
            dur_sec = 0.0
            geometry = [(prev.lat, prev.lng), (stop.lat, stop.lng)]
        else:
            dist_km, dur_sec, geometry = osrm.route_segment((prev.lat, prev.lng), (stop.lat, stop.lng))

        segments.append(
            RouteSegment(
                from_stop=prev,
                to_stop=stop,
                distance_km=dist_km,
                duration_sec=dur_sec,
                geometry=geometry,
            )
        )
        total_distance += dist_km
        total_duration += dur_sec
        prev = stop

    chunk_data = split_into_route_chunks(start, ordered_stops, config.max_waypoints_per_url)
    chunks: list[RouteChunk] = []
    for route_no, chunk_stops, url in chunk_data:
        chunk_distance = _chunk_distance(chunk_stops, segments)
        chunks.append(
            RouteChunk(
                route_no=route_no,
                stops=chunk_stops,
                google_maps_url=url,
                total_distance_km=chunk_distance,
            )
        )

    return PlannedRoute(
        start=start,
        ordered_stops=ordered_stops,
        segments=segments,
        chunks=chunks,
        total_distance_km=total_distance,
        total_duration_sec=total_duration,
        batch_name=batch_name,
        district=district,
        tehsil=tehsil,
    )


def plan_route(
    input_path: str,
    config: PlannerConfig | None = None,
    start_lat: float | None = None,
    start_lng: float | None = None,
    start_name: str = "Start",
) -> PlannedRoute:
    """Full pipeline: read Excel, optimize order, compute road segments, split URLs."""
    from .excel_reader import load_stops_from_excel

    config = config or PlannerConfig()
    start, destinations = load_stops_from_excel(
        input_path, start_lat=start_lat, start_lng=start_lng, start_name=start_name
    )
    logger.info("Loaded %d destinations from %s", len(destinations), input_path)
    return plan_route_from_stops(start, destinations, config=config)


def plan_batch(
    input_path: str,
    output_dir: str | Path,
    config: PlannerConfig | None = None,
    start_lat: float | None = None,
    start_lng: float | None = None,
    start_name: str = "Start",
    group_by: str = "district",
    district_filter: list[str] | None = None,
) -> BatchPlanResult:
    """
    Plan routes in batches grouped by district or tehsil.
    Large groups are auto-split geographically when they exceed max_stops_per_batch.
    """
    from .exporters.batch_index_exporter import write_batch_index
    from .exporters.excel_exporter import write_batch_master_excel

    config = config or PlannerConfig()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df, mapping = read_school_dataframe(input_path)
    lat, lng = read_start_coordinates(df, mapping, start_lat, start_lng)
    start = Stop(name=start_name, lat=lat, lng=lng)

    if group_by == "none":
        groups = ["All Locations"]
    else:
        groups = list_groups(df, mapping, group_by)
        if district_filter:
            allowed = {g.strip().upper() for g in district_filter}
            groups = [g for g in groups if g.strip().upper() in allowed]

    group_col = _group_column(mapping, group_by) if group_by != "none" else None
    items: list[BatchItemResult] = []

    for group_name in groups:
        stops = dataframe_to_stops(df, mapping, group_col, group_name if group_by != "none" else None)
        if not stops:
            continue

        district = group_name if group_by == "district" else (stops[0].district if stops else "")
        tehsil = group_name if group_by == "tehsil" else (stops[0].tehsil if stops else "")

        sub_batches = split_stops_geographically(stops, config.max_stops_per_batch)
        for sub_idx, sub_stops in enumerate(sub_batches, start=1):
            batch_label = _batch_label(group_name, sub_idx, len(sub_batches))
            safe_name = _safe_dirname(batch_label)
            batch_dir = output_path / safe_name
            batch_dir.mkdir(parents=True, exist_ok=True)

            item = BatchItemResult(
                name=batch_label,
                district=district,
                tehsil=tehsil,
                stop_count=len(sub_stops),
                output_dir=batch_dir,
            )

            try:
                planned = plan_route_from_stops(
                    start,
                    sub_stops,
                    config=config,
                    batch_name=batch_label,
                    district=district,
                    tehsil=tehsil,
                )
                paths = write_batch_outputs(planned, batch_dir, prefix=safe_name)
                item.planned = planned
                item.map_html = paths["html"].name
            except Exception as exc:
                logger.error("Batch %s failed: %s", batch_label, exc)
                item.error = str(exc)

            items.append(item)

    index_html = write_batch_index(items, output_path / "batch_index.html")
    master_excel = write_batch_master_excel(items, output_path / "all_routes_master.xlsx")

    succeeded = sum(1 for i in items if i.planned is not None)
    failed = sum(1 for i in items if i.error)
    total_schools = sum(i.stop_count for i in items if i.planned)
    total_km = sum(i.planned.total_distance_km for i in items if i.planned)

    return BatchPlanResult(
        items=items,
        output_dir=output_path,
        index_html=index_html,
        master_excel=master_excel,
        total_schools=total_schools,
        succeeded=succeeded,
        failed=failed,
        total_distance_km=total_km,
    )


def _batch_label(group_name: str, sub_idx: int, total_sub: int) -> str:
    if total_sub <= 1:
        return group_name
    return f"{group_name} (Part {sub_idx})"


def _safe_dirname(name: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    safe = re.sub(r"\s+", "_", safe.strip())
    safe = re.sub(r"_+", "_", safe)
    return safe[:80] or "batch"


def _chunk_distance(chunk_stops: list[Stop], segments: list[RouteSegment]) -> float:
    if len(chunk_stops) <= 1:
        return 0.0
    chunk_destinations = chunk_stops[1:]
    segment_map = {id(seg.to_stop): seg for seg in segments}
    return sum(segment_map[id(s)].distance_km for s in chunk_destinations if id(s) in segment_map)


def write_all_outputs(planned: PlannedRoute, output_dir: str | Path) -> dict[str, Path]:
    """Write Excel, KML, GPX, and HTML map (single-route filenames)."""
    from .exporters import write_excel, write_gpx, write_html_map, write_kml

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    return {
        "excel": write_excel(planned, output_path / "optimized_route.xlsx"),
        "kml": write_kml(planned, output_path / "optimized_route.kml"),
        "gpx": write_gpx(planned, output_path / "optimized_route.gpx"),
        "html": write_html_map(planned, output_path / "route_map.html"),
    }


def write_batch_outputs(
    planned: PlannedRoute,
    output_dir: str | Path,
    prefix: str = "optimized_route",
) -> dict[str, Path]:
    """Write Excel, KML, GPX, and HTML map to output directory."""
    from .exporters import write_excel, write_gpx, write_html_map, write_kml

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    paths = {
        "excel": write_excel(planned, output_path / f"{prefix}.xlsx"),
        "kml": write_kml(planned, output_path / f"{prefix}.kml"),
        "gpx": write_gpx(planned, output_path / f"{prefix}.gpx"),
        "html": write_html_map(planned, output_path / f"{prefix}_map.html"),
    }
    return paths

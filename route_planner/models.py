from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Stop:
    name: str
    lat: float
    lng: float
    school_code: str = ""
    original_index: int = 0
    district: str = ""
    tehsil: str = ""


@dataclass
class RouteSegment:
    from_stop: Stop | None
    to_stop: Stop
    distance_km: float
    duration_sec: float = 0.0
    geometry: list[tuple[float, float]] = field(default_factory=list)  # (lat, lng)


@dataclass
class RouteChunk:
    route_no: int
    stops: list[Stop]
    google_maps_url: str
    total_distance_km: float = 0.0


@dataclass
class PlannedRoute:
    start: Stop
    ordered_stops: list[Stop]
    segments: list[RouteSegment]
    chunks: list[RouteChunk]
    total_distance_km: float
    total_duration_sec: float = 0.0
    batch_name: str = ""
    district: str = ""
    tehsil: str = ""


@dataclass
class BatchItemResult:
    name: str
    district: str
    tehsil: str
    stop_count: int
    planned: PlannedRoute | None = None
    error: str | None = None
    output_dir: Path | None = None
    map_html: str = ""


@dataclass
class BatchPlanResult:
    items: list[BatchItemResult]
    output_dir: Path
    index_html: Path
    master_excel: Path
    total_schools: int = 0
    total_distance_km: float = 0.0
    succeeded: int = 0
    failed: int = 0

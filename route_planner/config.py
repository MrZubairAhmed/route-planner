from dataclasses import dataclass


@dataclass
class PlannerConfig:
    """Runtime configuration for the route planner."""

    osrm_base_url: str = "https://router.project-osrm.org"
    max_waypoints_per_url: int = 23  # Google Maps desktop limit (origin + waypoints + destination)
    osrm_batch_size: int = 50
    optimizer: str = "ortools"  # ortools | nearest_neighbor
    max_ortools_nodes: int = 500
    max_stops_per_batch: int = 150  # Split large district/tehsil groups geographically
    request_timeout: int = 60
    haversine_fallback: bool = True
    skip_geometry: bool = False  # Use straight lines instead of OSRM segment geometry (faster)

import logging
import math
from urllib.parse import quote

import numpy as np
import requests

from .config import PlannerConfig

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _coords_to_osrm_string(coords: list[tuple[float, float]]) -> str:
    """Format coordinates as lon,lat pairs for OSRM."""
    return ";".join(f"{lng},{lat}" for lat, lng in coords)


class OSRMClient:
    def __init__(self, config: PlannerConfig):
        self.config = config
        self.base_url = config.osrm_base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "school-route-planner/1.0"})

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, timeout=self.config.request_timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {data.get('message', data.get('code'))}")
        return data

    def build_distance_matrix(self, coords: list[tuple[float, float]]) -> np.ndarray:
        """Build a full NxN road distance matrix (meters) using batched OSRM table requests."""
        n = len(coords)
        matrix = np.zeros((n, n), dtype=np.float64)

        batch = self.config.osrm_batch_size
        for src_start in range(0, n, batch):
            src_end = min(src_start + batch, n)
            src_indices = list(range(src_start, src_end))

            for dst_start in range(0, n, batch):
                dst_end = min(dst_start + batch, n)
                dst_indices = list(range(dst_start, dst_end))
                combined_indices = src_indices + [i for i in dst_indices if i not in src_indices]
                index_map = {orig: pos for pos, orig in enumerate(combined_indices)}

                coord_str = _coords_to_osrm_string([coords[i] for i in combined_indices])
                sources = ";".join(str(index_map[i]) for i in src_indices)
                destinations = ";".join(str(index_map[i]) for i in dst_indices)

                try:
                    data = self._get(
                        f"/table/v1/driving/{coord_str}",
                        params={
                            "annotations": "distance",
                            "sources": sources,
                            "destinations": destinations,
                        },
                    )
                    distances = data["distances"]
                    for si, src_i in enumerate(src_indices):
                        for di, dst_i in enumerate(dst_indices):
                            value = distances[si][di]
                            if value is None:
                                value = self._fallback_distance(coords[src_i], coords[dst_i])
                            matrix[src_i, dst_i] = value
                except Exception as exc:
                    logger.warning("OSRM table batch failed (%s); using Haversine fallback.", exc)
                    for src_i in src_indices:
                        for dst_i in dst_indices:
                            matrix[src_i, dst_i] = self._fallback_distance(coords[src_i], coords[dst_i]) * 1000

        return matrix

    def route_segment(
        self, from_coord: tuple[float, float], to_coord: tuple[float, float]
    ) -> tuple[float, float, list[tuple[float, float]]]:
        """Return distance (km), duration (sec), and geometry [(lat,lng), ...] for one segment."""
        coord_str = _coords_to_osrm_string([from_coord, to_coord])
        try:
            data = self._get(
                f"/route/v1/driving/{coord_str}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            route = data["routes"][0]
            distance_km = route["distance"] / 1000.0
            duration_sec = route["duration"]
            geometry = [(pt[1], pt[0]) for pt in route["geometry"]["coordinates"]]
            return distance_km, duration_sec, geometry
        except Exception as exc:
            logger.warning("OSRM route failed (%s); using straight line.", exc)
            distance_km = haversine_km(from_coord[0], from_coord[1], to_coord[0], to_coord[1])
            return distance_km, 0.0, [from_coord, to_coord]

    def _fallback_distance(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        if self.config.haversine_fallback:
            return haversine_km(a[0], a[1], b[0], b[1]) * 1000
        raise RuntimeError("OSRM unavailable and Haversine fallback is disabled.")

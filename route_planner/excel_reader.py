import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import Stop


def _normalize_column(name: str) -> str:
    return re.sub(r"[\s_]+", " ", str(name).strip().lower())


def _find_column(columns: list[str], *candidates: str) -> str | None:
    normalized = {_normalize_column(c): c for c in columns}
    for candidate in candidates:
        key = _normalize_column(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _coerce_float(value) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ColumnMapping:
    lat: str
    lng: str
    name: str | None
    code: str | None
    start_lat: str | None
    start_lng: str | None
    district: str | None
    tehsil: str | None


def resolve_columns(columns: list[str]) -> ColumnMapping:
    lat_col = _find_column(
        columns,
        "Latitude",
        "Lat",
        "Dest Latitude",
        "Destination Latitude",
        "Y",
    )
    lng_col = _find_column(
        columns,
        "Longitude",
        "Lng",
        "Long",
        "Dest Longitude",
        "Destination Longitude",
        "X",
    )
    if lat_col is None or lng_col is None:
        raise ValueError(
            "Excel file must contain latitude and longitude columns "
            "(e.g. Latitude / Longitude)."
        )
    return ColumnMapping(
        lat=lat_col,
        lng=lng_col,
        name=_find_column(
            columns,
            "Name",
            "Location Name",
            "Place Name",
            "Site Name",
            "Destination",
            "Destination Name",
            "School Name",
            "Stop Name",
        ),
        code=_find_column(
            columns,
            "SchoolCode",
            "School Code",
            "Code",
            "Location Code",
            "ID",
            "Ref",
        ),
        start_lat=_find_column(
            columns,
            "Start LAT",
            "Start Lat",
            "Start Latitude",
            "Origin Lat",
            "Origin Latitude",
            "Depot Lat",
        ),
        start_lng=_find_column(
            columns,
            "Start LNG",
            "Start Lng",
            "Start Longitude",
            "Origin Lng",
            "Origin Longitude",
            "Depot Lng",
        ),
        district=_find_column(columns, "District", "Region", "Area"),
        tehsil=_find_column(columns, "Tehsil", "Tehsil Name", "Sub District", "Sub-District"),
    )


def read_route_dataframe(path: str) -> tuple[pd.DataFrame, ColumnMapping]:
    """Load Excel and resolve column mapping (generic — any compatible format)."""
    df = pd.read_excel(path)
    mapping = resolve_columns(list(df.columns))
    return df, mapping


def read_school_dataframe(path: str) -> tuple[pd.DataFrame, ColumnMapping]:
    """Backward-compatible alias for read_route_dataframe."""
    return read_route_dataframe(path)


def read_start_coordinates(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    start_lat: float | None = None,
    start_lng: float | None = None,
) -> tuple[float, float]:
    if start_lat is not None and start_lng is not None:
        return start_lat, start_lng
    if mapping.start_lat and mapping.start_lng:
        lat = _coerce_float(df[mapping.start_lat].dropna().iloc[0])
        lng = _coerce_float(df[mapping.start_lng].dropna().iloc[0])
        if lat is not None and lng is not None:
            return lat, lng
    raise ValueError(
        "Start coordinates not found. Provide --start-lat/--start-lng or "
        "include Start LAT / Start LNG columns in the Excel file."
    )


def dataframe_to_stops(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    group_col: str | None = None,
    group_value: str | None = None,
) -> list[Stop]:
    work = df
    if group_col and group_value is not None:
        work = df[df[group_col].astype(str).str.strip() == str(group_value).strip()]

    destinations: list[Stop] = []
    seen: set[tuple[float, float]] = set()

    for idx, row in work.iterrows():
        lat = _coerce_float(row[mapping.lat])
        lng = _coerce_float(row[mapping.lng])
        if lat is None or lng is None:
            continue

        key = (round(lat, 6), round(lng, 6))
        if key in seen:
            continue
        seen.add(key)

        name = (
            str(row[mapping.name]).strip()
            if mapping.name and pd.notna(row[mapping.name])
            else f"Stop {len(destinations) + 1}"
        )
        code = str(row[mapping.code]).strip() if mapping.code and pd.notna(row[mapping.code]) else ""
        district = (
            str(row[mapping.district]).strip()
            if mapping.district and pd.notna(row[mapping.district])
            else ""
        )
        tehsil = str(row[mapping.tehsil]).strip() if mapping.tehsil and pd.notna(row[mapping.tehsil]) else ""

        destinations.append(
            Stop(
                name=name,
                lat=lat,
                lng=lng,
                school_code=code,
                original_index=int(idx),
                district=district,
                tehsil=tehsil,
            )
        )

    return destinations


def list_groups(df: pd.DataFrame, mapping: ColumnMapping, group_by: str) -> list[str]:
    col = _group_column(mapping, group_by)
    if col is None:
        return ["All Locations"]
    values = df[col].dropna().astype(str).str.strip()
    values = values[values != ""]
    return sorted(values.unique().tolist())


def _group_column(mapping: ColumnMapping, group_by: str) -> str | None:
    if group_by == "district":
        return mapping.district
    if group_by == "tehsil":
        return mapping.tehsil
    return None


def split_stops_geographically(stops: list[Stop], max_per_batch: int) -> list[list[Stop]]:
    """Split a large stop list into geographic sub-batches using k-means."""
    if len(stops) <= max_per_batch:
        return [stops]

    n_batches = math.ceil(len(stops) / max_per_batch)
    coords = np.array([[s.lat, s.lng] for s in stops], dtype=np.float64)

    # Initialize centroids by spreading across latitude
    order = np.argsort(coords[:, 0])
    step = max(1, len(order) // n_batches)
    centroid_idx = [order[min(i * step, len(order) - 1)] for i in range(n_batches)]
    centroids = coords[centroid_idx].copy()

    assignments = np.zeros(len(stops), dtype=int)
    for _ in range(20):
        dists = np.linalg.norm(coords[:, None, :] - centroids[None, :, :], axis=2)
        assignments = np.argmin(dists, axis=1)
        new_centroids = np.zeros_like(centroids)
        for k in range(n_batches):
            mask = assignments == k
            if mask.any():
                new_centroids[k] = coords[mask].mean(axis=0)
            else:
                new_centroids[k] = centroids[k]
        if np.allclose(new_centroids, centroids):
            break
        centroids = new_centroids

    batches: list[list[Stop]] = [[] for _ in range(n_batches)]
    for stop, cluster in zip(stops, assignments):
        batches[cluster].append(stop)

    # Rebalance oversized batches
    result: list[list[Stop]] = []
    overflow: list[Stop] = []
    for batch in batches:
        if len(batch) > max_per_batch:
            overflow.extend(batch)
        elif batch:
            result.append(batch)

    while overflow:
        chunk = overflow[:max_per_batch]
        overflow = overflow[max_per_batch:]
        if chunk:
            result.append(chunk)

    return result if result else [stops]


def load_stops_from_excel(
    path: str,
    start_lat: float | None = None,
    start_lng: float | None = None,
    start_name: str = "Start",
    group_by: str | None = None,
    group_value: str | None = None,
) -> tuple[Stop, list[Stop]]:
    """Load start point and destinations from an Excel file."""
    df, mapping = read_route_dataframe(path)
    lat, lng = read_start_coordinates(df, mapping, start_lat, start_lng)
    start = Stop(name=start_name, lat=lat, lng=lng)

    group_col = _group_column(mapping, group_by) if group_by else None
    destinations = dataframe_to_stops(df, mapping, group_col, group_value)

    if not destinations:
        label = group_value or "file"
        raise ValueError(f"No valid destination coordinates found for {label}.")

    return start, destinations

"""Detect Excel structure and recommend processing settings."""

from dataclasses import dataclass, field

import pandas as pd

from .excel_reader import (
    ColumnMapping,
    dataframe_to_stops,
    list_groups,
    read_start_coordinates,
    read_route_dataframe,
    resolve_columns,
)


@dataclass
class ExcelProfile:
    """Detected structure and stats for an uploaded Excel file."""

    row_count: int
    destination_count: int
    mapping: ColumnMapping
    has_start: bool
    start_lat: float | None = None
    start_lng: float | None = None
    district_count: int = 0
    tehsil_count: int = 0
    districts: list[str] = field(default_factory=list)
    tehsils: list[str] = field(default_factory=list)
    recommended_batch_by: str = "none"  # none | district | tehsil
    recommended_skip_geometry: bool = False
    missing_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{self.destination_count} destinations"]
        if self.has_start:
            parts.append("start point detected")
        if self.recommended_batch_by != "none":
            parts.append(f"batch by {self.recommended_batch_by}")
        return " · ".join(parts)


def analyze_excel(path: str) -> tuple[pd.DataFrame, ExcelProfile]:
    """Read Excel and return dataframe plus a detected format profile."""
    df, mapping = read_route_dataframe(path)
    missing = _missing_required(mapping)
    if missing:
        raise ValueError(
            "Excel format not recognized. Required columns: Latitude, Longitude. "
            f"Missing: {', '.join(missing)}. "
            "Optional: Start LAT, Start LNG, Name, District, Tehsil, SchoolCode."
        )

    destinations = dataframe_to_stops(df, mapping)
    profile = ExcelProfile(
        row_count=len(df),
        destination_count=len(destinations),
        mapping=mapping,
        has_start=bool(mapping.start_lat and mapping.start_lng),
        district_count=0,
        tehsil_count=0,
    )

    if profile.destination_count == 0:
        raise ValueError("No valid destination rows found. Check Latitude and Longitude values.")

    if mapping.district:
        profile.districts = list_groups(df, mapping, "district")
        profile.district_count = len(profile.districts)
    if mapping.tehsil:
        profile.tehsils = list_groups(df, mapping, "tehsil")
        profile.tehsil_count = len(profile.tehsils)

    if mapping.start_lat and mapping.start_lng:
        try:
            profile.start_lat, profile.start_lng = read_start_coordinates(df, mapping)
            profile.has_start = True
        except ValueError:
            profile.has_start = False
            profile.warnings.append("Start LAT/LNG columns exist but contain no valid values.")

    profile.recommended_batch_by = _recommend_batch_mode(profile)
    profile.recommended_skip_geometry = profile.destination_count > 100

    if not profile.has_start:
        profile.warnings.append("No start coordinates in file — provide Start LAT and Start LNG columns.")

    if profile.destination_count > 500:
        profile.warnings.append(
            f"Large dataset ({profile.destination_count} destinations). "
            "Processing may take a while; batch mode and fast mode are recommended."
        )

    return df, profile


def resolve_batch_mode(profile: ExcelProfile, batch_by: str) -> str:
    """Resolve 'auto' to a concrete batch mode."""
    if batch_by != "auto":
        return batch_by
    return profile.recommended_batch_by


def _recommend_batch_mode(profile: ExcelProfile) -> str:
    if profile.district_count > 1:
        return "district"
    if profile.tehsil_count > 1:
        return "tehsil"
    return "none"


def _missing_required(mapping: ColumnMapping) -> list[str]:
    missing = []
    if not mapping.lat:
        missing.append("Latitude")
    if not mapping.lng:
        missing.append("Longitude")
    return missing

"""Blank Excel template matching the expected route planner format."""

from pathlib import Path

import pandas as pd


def write_format_template(output_path: str | Path) -> Path:
    """Write a sample Excel template users can fill in and upload."""
    output_path = Path(output_path)

    rows = [
        {
            "SchoolCode": "LOC-001",
            "Name": "Example Location A",
            "District": "DISTRICT_A",
            "Tehsil": "TEHSIL_1",
            "Latitude": 31.5204,
            "Longitude": 74.3587,
            "Start LAT": 31.5354,
            "Start LNG": 74.3442,
        },
        {
            "SchoolCode": "LOC-002",
            "Name": "Example Location B",
            "District": "DISTRICT_A",
            "Tehsil": "TEHSIL_1",
            "Latitude": 31.5497,
            "Longitude": 74.3436,
            "Start LAT": 31.5354,
            "Start LNG": 74.3442,
        },
        {
            "SchoolCode": "LOC-003",
            "Name": "Example Location C",
            "District": "DISTRICT_B",
            "Tehsil": "TEHSIL_2",
            "Latitude": 30.1575,
            "Longitude": 71.5249,
            "Start LAT": 31.5354,
            "Start LNG": 74.3442,
        },
    ]

    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False, sheet_name="Locations")
    return output_path

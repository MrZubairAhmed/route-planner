#!/usr/bin/env python3
"""CLI entry point for the Excel route planner."""

import argparse
import logging
import sys
from pathlib import Path

from route_planner.config import PlannerConfig
from route_planner.excel_format import analyze_excel
from route_planner.excel_reader import list_groups, read_route_dataframe
from route_planner.process import process_excel
from route_planner.template import write_format_template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan optimized multi-destination driving routes from any Excel file "
            "with Latitude, Longitude, and optional Start/District columns."
        )
    )
    parser.add_argument("-i", "--input", help="Path to input Excel file (.xlsx)")
    parser.add_argument("-o", "--output-dir", default="output", help="Directory for output files")
    parser.add_argument("--start-lat", type=float, help="Starting latitude (overrides Excel column)")
    parser.add_argument("--start-lng", type=float, help="Starting longitude (overrides Excel column)")
    parser.add_argument("--start-name", default="Start", help="Label for the starting point")
    parser.add_argument(
        "--batch-by",
        choices=["auto", "none", "district", "tehsil"],
        default="auto",
        help="Batch mode: auto detects from District/Tehsil columns (default: auto)",
    )
    parser.add_argument(
        "--group-filter",
        help="Comma-separated district/tehsil names to process (batch mode only)",
    )
    parser.add_argument("--optimizer", choices=["ortools", "nearest_neighbor"], default="ortools")
    parser.add_argument("--max-waypoints", type=int, default=23)
    parser.add_argument("--max-stops-per-batch", type=int, default=150)
    parser.add_argument("--osrm-url", default="https://router.project-osrm.org")
    parser.add_argument("--max-ortools-nodes", type=int, default=500)
    parser.add_argument("--skip-geometry", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="List district/tehsil groups in the file and exit",
    )
    parser.add_argument(
        "--create-template",
        metavar="PATH",
        help="Write a blank Excel template to PATH and exit",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.create_template:
        path = write_format_template(args.create_template)
        print(f"Template written to: {path.resolve()}")
        return 0

    if not args.input:
        parser.error("--input is required (or use --create-template)")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    if args.list_groups:
        df, mapping = read_route_dataframe(str(input_path))
        for mode in ("district", "tehsil"):
            col = mapping.district if mode == "district" else mapping.tehsil
            if col:
                groups = list_groups(df, mapping, mode)
                print(f"{len(groups)} {mode} groups:")
                for g in groups:
                    print(f"  - {g}")
        return 0

    config = PlannerConfig(
        osrm_base_url=args.osrm_url,
        max_waypoints_per_url=args.max_waypoints,
        optimizer=args.optimizer,
        max_ortools_nodes=args.max_ortools_nodes,
        max_stops_per_batch=args.max_stops_per_batch,
        skip_geometry=args.skip_geometry,
    )

    group_filter = None
    if args.group_filter:
        group_filter = [x.strip() for x in args.group_filter.split(",") if x.strip()]

    try:
        _, profile = analyze_excel(str(input_path))
        logging.info("Detected: %s", profile.summary())
        if profile.warnings:
            for w in profile.warnings:
                logging.warning(w)

        result = process_excel(
            str(input_path),
            args.output_dir,
            config=config,
            batch_by=args.batch_by,
            start_lat=args.start_lat,
            start_lng=args.start_lng,
            start_name=args.start_name,
            group_filter=group_filter,
        )
    except Exception as exc:
        logging.error("Route planning failed: %s", exc)
        if args.verbose:
            raise
        return 1

    if result.mode == "batch":
        _print_batch_summary(result)
    else:
        _print_single_summary(result)

    return 0


def _print_single_summary(result) -> None:
    planned = result.single
    paths = result.output_paths or {}
    print("\n=== Route Planning Complete ===")
    print(f"Mode:             Single route (auto)")
    print(f"Destinations:     {len(planned.ordered_stops)}")
    print(f"Total distance:   {planned.total_distance_km:.1f} km")
    print(f"Est. drive time:  {planned.total_duration_sec / 3600:.1f} hours")
    print(f"Google Maps URLs: {len(planned.chunks)} chunk(s)")
    print("\nOutput files:")
    for name, path in paths.items():
        print(f"  {name:6s} -> {path.resolve()}")
    for chunk in planned.chunks:
        print(f"\n  Route {chunk.route_no}: {chunk.google_maps_url}")


def _print_batch_summary(result) -> None:
    batch = result.batch
    print("\n=== Route Planning Complete ===")
    print(f"Mode:              Batch by {result.batch_by}")
    print(f"Batches succeeded: {batch.succeeded}")
    print(f"Batches failed:    {batch.failed}")
    print(f"Total locations:   {batch.total_schools}")
    print(f"Total distance:    {batch.total_distance_km:.1f} km")
    print(f"\nIndex page:   {batch.index_html.resolve()}")
    print(f"Master Excel: {batch.master_excel.resolve()}")
    for item in batch.items:
        if item.error:
            print(f"  [FAIL] {item.name}: {item.error}")
        else:
            km = item.planned.total_distance_km if item.planned else 0
            print(f"  [OK]   {item.name}: {item.stop_count} locations, {km:.1f} km")


if __name__ == "__main__":
    raise SystemExit(main())

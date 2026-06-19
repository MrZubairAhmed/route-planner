import json
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from ..models import PlannedRoute


def _prettify_xml(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def write_gpx(planned: PlannedRoute, output_path: Path) -> Path:
    """Write GPX file with waypoints and track segments for GPS devices."""
    gpx = ET.Element("gpx")
    gpx.set("version", "1.1")
    gpx.set("creator", "school-route-planner")
    gpx.set("xmlns", "http://www.topografix.com/GPX/1/1")

    start_wpt = ET.SubElement(
        gpx,
        "wpt",
        lat=str(planned.start.lat),
        lon=str(planned.start.lng),
    )
    ET.SubElement(start_wpt, "name").text = planned.start.name

    for i, stop in enumerate(planned.ordered_stops, start=1):
        wpt = ET.SubElement(gpx, "wpt", lat=str(stop.lat), lon=str(stop.lng))
        ET.SubElement(wpt, "name").text = f"{i}. {stop.name}"
        ET.SubElement(wpt, "desc").text = stop.school_code or stop.name

    for chunk in planned.chunks:
        trk = ET.SubElement(gpx, "trk")
        ET.SubElement(trk, "name").text = f"Route {chunk.route_no}"
        trkseg = ET.SubElement(trk, "trkseg")

        chunk_destinations = {id(s) for s in chunk.stops[1:]}
        for segment in planned.segments:
            if id(segment.to_stop) not in chunk_destinations:
                continue
            for lat, lng in segment.geometry:
                ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lng))

    output_path.write_text(_prettify_xml(gpx), encoding="utf-8")
    return output_path

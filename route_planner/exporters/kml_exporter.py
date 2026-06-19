import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from ..models import PlannedRoute


def _prettify_xml(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def write_kml(planned: PlannedRoute, output_path: Path) -> Path:
    """Write KML with named stops, road route polylines, and direction layers."""
    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, "Document")
    ET.SubElement(document, "name").text = "Optimized Route"

    stops_folder = ET.SubElement(document, "Folder")
    ET.SubElement(stops_folder, "name").text = "Stops"

    start_pm = ET.SubElement(stops_folder, "Placemark")
    ET.SubElement(start_pm, "name").text = planned.start.name
    start_point = ET.SubElement(start_pm, "Point")
    ET.SubElement(start_point, "coordinates").text = f"{planned.start.lng},{planned.start.lat},0"

    for i, stop in enumerate(planned.ordered_stops, start=1):
        pm = ET.SubElement(stops_folder, "Placemark")
        ET.SubElement(pm, "name").text = f"{i}. {stop.name}"
        point = ET.SubElement(pm, "Point")
        ET.SubElement(point, "coordinates").text = f"{stop.lng},{stop.lat},0"

    routes_folder = ET.SubElement(document, "Folder")
    ET.SubElement(routes_folder, "name").text = "Road Routes"

    for chunk in planned.chunks:
        chunk_pm = ET.SubElement(routes_folder, "Placemark")
        ET.SubElement(chunk_pm, "name").text = f"Route {chunk.route_no} (Road)"
        line = ET.SubElement(chunk_pm, "LineString")
        ET.SubElement(line, "tessellate").text = "1"

        coords_parts: list[str] = []
        chunk_destinations = {id(s) for s in chunk.stops[1:]}
        for segment in planned.segments:
            if id(segment.to_stop) not in chunk_destinations:
                continue
            for lat, lng in segment.geometry:
                coords_parts.append(f"{lng},{lat},0")
        ET.SubElement(line, "coordinates").text = " ".join(coords_parts)

    directions_folder = ET.SubElement(document, "Folder")
    ET.SubElement(directions_folder, "name").text = "Direction Segments"

    prev_name = planned.start.name
    for segment in planned.segments:
        pm = ET.SubElement(directions_folder, "Placemark")
        ET.SubElement(pm, "name").text = f"{prev_name} → {segment.to_stop.name}"
        line = ET.SubElement(pm, "LineString")
        ET.SubElement(line, "tessellate").text = "1"
        coords = " ".join(f"{lng},{lat},0" for lat, lng in segment.geometry)
        ET.SubElement(line, "coordinates").text = coords
        prev_name = segment.to_stop.name

    output_path.write_text(_prettify_xml(kml), encoding="utf-8")
    return output_path

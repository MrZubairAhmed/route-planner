from urllib.parse import quote

from .models import Stop


def build_google_maps_url(stops: list[Stop]) -> str:
    """
    Build a Google Maps directions URL for a sequence of stops.
    stops[0] = origin, stops[-1] = destination, middle = waypoints.
    """
    if len(stops) < 2:
        raise ValueError("At least origin and destination are required.")

    origin = _format_coord(stops[0])
    destination = _format_coord(stops[-1])
    waypoints = stops[1:-1]

    url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}"
    if waypoints:
        wp = "|".join(_format_coord(s) for s in waypoints)
        url += f"&waypoints={wp}"
    url += "&travelmode=driving"
    return url


def split_into_route_chunks(
    start: Stop,
    ordered_stops: list[Stop],
    max_waypoints: int,
) -> list[tuple[int, list[Stop], str]]:
    """
    Split optimized stops into Google Maps URL chunks.
    Returns list of (route_no, stops_in_chunk_including_start, google_maps_url).
    """
    if not ordered_stops:
        return []

    chunks: list[tuple[int, list[Stop], str]] = []
    max_destinations_per_chunk = max_waypoints + 1  # waypoints + final destination
    route_no = 1
    cursor = 0
    current_start = start

    while cursor < len(ordered_stops):
        batch = ordered_stops[cursor : cursor + max_destinations_per_chunk]
        chunk_stops = [current_start] + batch
        url = build_google_maps_url(chunk_stops)
        chunks.append((route_no, chunk_stops, url))

        current_start = batch[-1]
        cursor += len(batch)
        route_no += 1

    return chunks


def _format_coord(stop: Stop) -> str:
    return quote(f"{stop.lat},{stop.lng}", safe="")

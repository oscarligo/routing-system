"""Download a directed driving network, estimate travel times and cache GraphML."""

import hashlib
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import osmnx as ox


def load_graph(
    bbox: tuple[float, float, float, float],
    cache_dir: Path = Path("data/cache"),
    *,
    refresh: bool = False,
) -> tuple[nx.MultiDiGraph, Path]:
    """bbox is (west, south, east, north), in WGS84 degrees.

    Times are free-flow estimates, not observed traffic. Missing maxspeed values
    use OSMnx's highway-class imputation, with 30 km/h as the final fallback.
    """
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise ValueError("bbox must contain four finite coordinates")
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Expected bbox=(west,south,east,north) in WGS84")
    query = {"bbox": list(bbox), "network_type": "drive", "fallback_kph": 30, "schema": 1}
    key = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()[:16]
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    graph_file = cache_dir / f"drive_{key}.graphml"
    if graph_file.exists() and not refresh:
        return ox.io.load_graphml(graph_file), graph_file

    ox.settings.use_cache = not refresh
    ox.settings.cache_folder = str(cache_dir / "overpass")
    ox.settings.requests_timeout = 90
    graph = ox.graph.graph_from_bbox(bbox, network_type="drive", retain_all=False)
    graph = ox.routing.add_edge_speeds(graph, fallback=30)
    graph = ox.routing.add_edge_travel_times(graph)
    graph.graph.update(
        routing_query=json.dumps(query, sort_keys=True),
        downloaded_utc=datetime.now(timezone.utc).isoformat(),
        attribution="© OpenStreetMap contributors, ODbL https://www.openstreetmap.org/copyright",
        travel_time_source="OSM maxspeed / OSMnx highway-class imputation / 30 km/h fallback; free flow",
    )
    # Replace atomically so an interrupted save cannot become a valid cache hit.
    with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".graphml", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        ox.io.save_graphml(graph, temporary)
        temporary.replace(graph_file)
    finally:
        temporary.unlink(missing_ok=True)
    return graph, graph_file

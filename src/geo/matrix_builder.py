"""Build MiniZinc JSON parameters from customers and directed fastest paths."""

import hashlib
import json
import math
from pathlib import Path

import networkx as nx
import osmnx as ox


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def build_instance(
    graph: nx.MultiDiGraph, raw: dict, *, max_snap_distance_m: float = 250
) -> tuple[dict, dict]:
    """Return (model parameters, geography/provenance), keeping node 0 as depot."""
    nodes, fleet = raw["nodes"], raw["vehicles"]
    if len(nodes) < 2 or not fleet:
        raise ValueError("At least one depot, one customer and one vehicle are required")
    if not graph.is_directed() or not graph.is_multigraph() or not graph:
        raise ValueError("Expected a nonempty directed OSMnx MultiDiGraph")
    if str(graph.graph.get("crs", "")).upper() != "EPSG:4326":
        raise ValueError("Expected an unprojected EPSG:4326 graph for latitude/longitude snapping")
    if not math.isfinite(max_snap_distance_m) or max_snap_distance_m <= 0:
        raise ValueError("max_snap_distance_m must be positive and finite")
    for node in nodes:
        lat, lon = node["lat"], node["lon"]
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Invalid coordinates for {node['id']}")
    if len({node["id"] for node in nodes}) != len(nodes):
        raise ValueError("Node ids must be unique; the first node is the depot")
    horizon = _integer(raw["horizon"], "horizon", 1)
    parameters = {
        "n_customers": len(nodes) - 1,
        "n_vehicles": len(fleet),
        "n_docks": _integer(raw["n_docks"], "n_docks", 1),
        "horizon": horizon,
    }
    for key in ("demand", "earliest", "latest", "service"):
        parameters[key] = [_integer(node[key], key) for node in nodes]
    if parameters["demand"][0] != 0 or parameters["service"][0] != 0:
        raise ValueError("Depot demand and service must be zero")
    if any(not (0 <= node["earliest"] <= node["latest"] <= horizon) for node in nodes):
        raise ValueError("Windows must satisfy 0 <= earliest <= latest <= horizon")
    for key in ("capacity", "fixed_cost", "distance_cost", "loading_duration"):
        minimum = 1 if key in ("capacity", "loading_duration") else 0
        parameters[key] = [_integer(vehicle[key], key, minimum) for vehicle in fleet]
    if max(parameters["loading_duration"]) > horizon:
        raise ValueError("Loading duration exceeds horizon")
    if sum(parameters["demand"]) > sum(parameters["capacity"]):
        raise ValueError("Total demand exceeds fleet capacity")
    if max(parameters["demand"]) > max(parameters["capacity"]):
        raise ValueError("A customer demand exceeds every vehicle's capacity")

    snapped, offsets = ox.distance.nearest_nodes(
        graph, X=[node["lon"] for node in nodes], Y=[node["lat"] for node in nodes], return_dist=True
    )
    if any(float(offset) > max_snap_distance_m for offset in offsets):
        raise ValueError(f"A customer or depot is more than {max_snap_distance_m} m from the network")
    for _, _, edge in graph.edges(data=True):
        for key in ("length", "travel_time"):
            if key not in edge or not math.isfinite(edge[key]) or edge[key] < 0:
                raise ValueError(f"Every road edge needs finite nonnegative {key}")

    distances, times = [], []
    for source_index, source in enumerate(snapped):
        seconds, paths = nx.single_source_dijkstra(graph, int(source), weight="travel_time")
        distance_row, time_row = [], []
        for target_index, target in enumerate(snapped):
            target = int(target)
            if target not in paths:
                raise ValueError(f"No directed road path: {nodes[source_index]['id']} -> {nodes[target_index]['id']}; enlarge bbox")
            path = paths[target]
            # Use the SAME fastest path for distance and time, including parallel edges.
            length = sum(
                min(graph[u][v].values(), key=lambda edge: (edge["travel_time"], edge["length"]))["length"]
                for u, v in zip(path, path[1:])
            )
            distance_row.append(math.ceil(length))
            time_row.append(math.ceil(seconds[target] / 60))
        distances.append(distance_row)
        times.append(time_row)
    parameters.update(distance=distances, travel_time=times)
    metadata = {
        "attribution": graph.graph.get("attribution", "© OpenStreetMap contributors"),
        "travel_time_source": graph.graph.get("travel_time_source", "graph edge travel_time, seconds"),
        "downloaded_utc": graph.graph.get("downloaded_utc"),
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "routing_query": json.loads(graph.graph.get("routing_query", "null")),
        "created_with": graph.graph.get("created_with"),
        "units": {"distance": "metres, rounded up along fastest path", "travel_time": "minutes, rounded up per OD pair"},
        "operational_data": raw.get("description", "User-supplied demands, windows and fleet"),
        "nodes": [
            {**node, "model_index": index, "osm_node": int(road_node), "snap_distance_m": round(float(offset), 2),
             "snapped_lat": graph.nodes[int(road_node)]["y"], "snapped_lon": graph.nodes[int(road_node)]["x"]}
            for index, (node, road_node, offset) in enumerate(zip(nodes, snapped, offsets))
        ],
    }
    return parameters, metadata


def write_instance(
    graph: nx.MultiDiGraph, raw_file: Path, output: Path,
    *, graph_file: Path | None = None, max_snap_distance_m: float = 250,
) -> dict:
    raw_bytes = Path(raw_file).read_bytes()
    parameters, metadata = build_instance(graph, json.loads(raw_bytes), max_snap_distance_m=max_snap_distance_m)
    content = json.dumps(parameters, indent=2) + "\n"
    metadata["raw_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    metadata["instance_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    if graph_file is not None:
        metadata["graph_cache"] = str(graph_file)
        metadata["graph_sha256"] = hashlib.sha256(Path(graph_file).read_bytes()).hexdigest()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)
    output.with_suffix(".geo.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    return parameters

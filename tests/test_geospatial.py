"""Offline regression tests, including a real MiniZinc Python invocation if installed."""

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

from src.geo.matrix_builder import build_instance, write_instance
from src.geo.osm_extractor import load_graph
from src.solver.mzn_runner import solve_instance


def road_graph():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    for node, lon in ((10, -90.520), (20, -90.519), (30, -90.518)):
        graph.add_node(node, x=lon, y=14.64)
    for u, v, length, seconds in (
        (10, 20, 200, 30), (10, 20, 10, 80), (20, 30, 100, 30),
        (10, 30, 50, 180), (30, 10, 500, 100), (20, 10, 600, 110),
    ):
        graph.add_edge(u, v, length=float(length), travel_time=float(seconds))
    return graph


def orders():
    return {
        "n_docks": 1, "horizon": 90,
        "vehicles": [{"capacity": 2, "fixed_cost": 10, "distance_cost": 1, "loading_duration": 1}],
        "nodes": [
            {"id": str(i), "lat": 14.64, "lon": lon, "demand": int(i > 0),
             "earliest": 0, "latest": 90, "service": int(i > 0)}
            for i, lon in enumerate((-90.520, -90.519, -90.518))
        ],
    }


class GeospatialTests(unittest.TestCase):
    def test_directed_fastest_paths_and_parallel_roads(self):
        data, metadata = build_instance(road_graph(), orders())
        self.assertEqual(data["distance"][0], [0, 200, 300])
        self.assertEqual(data["distance"][2][0], 500)
        self.assertEqual(data["travel_time"][0][2], 1)
        self.assertEqual(data["travel_time"][2][0], 2)
        self.assertEqual([node["osm_node"] for node in metadata["nodes"]], [10, 20, 30])

    def test_unreachable_node_is_an_error_not_a_fake_distance(self):
        graph = road_graph()
        graph.remove_edges_from(list(graph.out_edges(30, keys=True)))
        with self.assertRaisesRegex(ValueError, "No directed road path"):
            build_instance(graph, orders())

    def test_rejects_far_coordinates_and_invalid_data(self):
        raw = orders()
        raw["nodes"][1]["lat"] = 15
        with self.assertRaisesRegex(ValueError, "from the network"):
            build_instance(road_graph(), raw)
        raw = orders()
        raw["nodes"][1]["demand"] = -1
        with self.assertRaisesRegex(ValueError, "demand"):
            build_instance(road_graph(), raw)
        graph = road_graph()
        del graph[10][20][0]["travel_time"]
        with self.assertRaisesRegex(ValueError, "travel_time"):
            build_instance(graph, orders())

    def test_graphml_cache_works_without_another_download(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("src.geo.osm_extractor.ox.graph.graph_from_bbox", side_effect=lambda *a, **kw: copy.deepcopy(road_graph())) as download,
                patch("src.geo.osm_extractor.ox.routing.add_edge_speeds", side_effect=lambda graph, **kw: graph),
                patch("src.geo.osm_extractor.ox.routing.add_edge_travel_times", side_effect=lambda graph: graph),
            ):
                first, path = load_graph((-90.53, 14.63, -90.50, 14.65), Path(directory))
                second, cached = load_graph((-90.53, 14.63, -90.50, 14.65), Path(directory))
                self.assertEqual(path, cached)
                self.assertEqual(download.call_count, 1)
                self.assertEqual(build_instance(first, orders())[0], build_instance(second, orders())[0])
                load_graph((-90.53, 14.63, -90.50, 14.65), Path(directory), refresh=True)
                self.assertEqual(download.call_count, 2)

    def test_json_contains_only_core_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            raw, output = Path(directory) / "raw.json", Path(directory) / "instance.json"
            raw.write_text(json.dumps(orders()))
            expected = write_instance(road_graph(), raw, output)
            self.assertEqual(json.loads(output.read_text()), expected)
            self.assertNotIn("nodes", expected)
            metadata = json.loads(output.with_suffix(".geo.json").read_text())
            self.assertEqual(metadata["nodes"][0]["model_index"], 0)
            self.assertEqual(len(metadata["instance_sha256"]), 64)

    @unittest.skipUnless(shutil.which("minizinc") or Path("/Applications/MiniZincIDE.app/Contents/Resources/minizinc").exists(), "MiniZinc executable is not installed")
    def test_json_solves_through_python_with_zero_based_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "instance.json"
            data, _ = build_instance(road_graph(), orders())
            instance.write_text(json.dumps(data))
            result = solve_instance(instance, time_limit=10)
            self.assertTrue(result["optimal"])
            self.assertEqual(result["total_cost"], 810)
            self.assertEqual(result["routes"], [[0, 1, 2, 0]])

    @unittest.skipUnless(shutil.which("minizinc") or Path("/Applications/MiniZincIDE.app/Contents/Resources/minizinc").exists(), "MiniZinc executable is not installed")
    def test_infeasible_instance_returns_status_without_fabricating_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "instance.json"
            data, _ = build_instance(road_graph(), orders())
            data["capacity"] = [1]
            instance.write_text(json.dumps(data))
            result = solve_instance(instance, time_limit=10)
            self.assertEqual(result["status"], "UNSATISFIABLE")
            self.assertFalse(result["has_solution"])
            self.assertNotIn("routes", result)


class RealInstanceTests(unittest.TestCase):
    def test_saved_real_solution_satisfies_operational_constraints(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "data/instances/guatemala_zona1_15.json"
        data = json.loads(path.read_text())
        geo = json.loads(path.with_suffix(".geo.json").read_text())
        result = json.loads(path.with_suffix(".solution.json").read_text())
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(geo["instance_sha256"], checksum)
        self.assertEqual(result["instance_sha256"], checksum)
        self.assertEqual(data["n_customers"], 15)
        self.assertTrue(result["optimal"])
        self.assertEqual(result["total_cost"], 16022)
        self.assertEqual(len({node["osm_node"] for node in geo["nodes"]}), 16)
        self.assertTrue(any(data["travel_time"][i][j] != data["travel_time"][j][i]
                            for i in range(16) for j in range(i)))
        visited, objective, docks = [], 0, []
        for k, route in enumerate(result["routes"]):
            if not result["used"][k]:
                self.assertEqual(route, [0])
                continue
            self.assertEqual((route[0], route[-1]), (0, 0))
            visited.extend(route[1:-1])
            self.assertLessEqual(sum(data["demand"][i] for i in route), data["capacity"][k])
            objective += data["fixed_cost"][k] + data["distance_cost"][k] * sum(
                data["distance"][i][j] for i, j in zip(route, route[1:]))
            departure = result["departure"][k]
            self.assertGreaterEqual(result["loading_start"][k], data["earliest"][0])
            self.assertEqual(departure, result["loading_start"][k] + data["loading_duration"][k])
            docks.extend([(result["loading_start"][k], 1), (departure, -1)])
            previous, finished = 0, departure
            for i in route[1:-1]:
                start = result["start_service"][i - 1]
                self.assertLessEqual(finished + data["travel_time"][previous][i], start)
                self.assertLessEqual(data["earliest"][i], start)
                self.assertLessEqual(start, data["latest"][i])
                previous, finished = i, start + data["service"][i]
            self.assertLessEqual(finished + data["travel_time"][previous][0], result["return_time"][k])
            self.assertLessEqual(result["return_time"][k], data["latest"][0])
        self.assertEqual(sorted(visited), list(range(1, 16)))
        self.assertEqual(objective, result["total_cost"])
        occupied = 0
        for _, delta in sorted(docks):  # -1 precedes +1 at a shared endpoint.
            occupied += delta
            self.assertLessEqual(occupied, data["n_docks"])


if __name__ == "__main__":
    unittest.main()

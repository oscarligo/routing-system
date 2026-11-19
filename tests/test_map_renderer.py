import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString

from src.geo.matrix_builder import build_instance
from src.solver.routes import routes_from_successors
from src.viz.map_renderer import build_plan, clock, make_map, render_map


def fixture():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    for node, lon in ((10, -90.520), (20, -90.519), (30, -90.518)):
        graph.add_node(node, x=lon, y=14.64)
    for u, v, length, seconds in ((10, 20, 200, 30), (10, 20, 10, 80),
                                  (20, 30, 100, 30), (30, 10, 500, 100)):
        graph.add_edge(u, v, length=length, travel_time=seconds, oneway=True, name="Vía de prueba")
    # Reversed stored geometry must still render from the edge's source to target.
    graph[10][20][0]["geometry"] = LineString([(-90.519, 14.64), (-90.5195, 14.6402), (-90.520, 14.64)])
    raw = {"n_docks": 1, "horizon": 90,
           "vehicles": [{"capacity": 2, "fixed_cost": 10, "distance_cost": 1, "loading_duration": 1}],
           "nodes": [{"id": str(i), "lat": 14.64, "lon": lon, "demand": int(i > 0),
                      "earliest": 0, "latest": 90, "service": int(i > 0)}
                     for i, lon in enumerate((-90.520, -90.519, -90.518))]}
    data, geo = build_instance(graph, raw)
    solution = {"has_solution": True, "successor": [[1, 2, 0]], "used": [True],
                "start_service": [2, 4], "loading_start": [0], "departure": [1],
                "return_time": [7], "total_cost": 810, "routes": [[0, 2, 1, 0]]}
    return graph, data, geo, solution


class RendererTests(unittest.TestCase):
    def test_follows_successors_directed_edges_and_full_geometry(self):
        graph, data, geo, solution = fixture()
        vehicle = build_plan(graph, data, geo, solution)["vehicles"][0]
        # The redundant routes[] in the input is deliberately wrong.
        self.assertEqual(vehicle["route"], [0, 1, 2, 0])
        self.assertEqual(vehicle["legs"][0]["coordinates"], [(14.64, -90.520), (14.6402, -90.5195), (14.64, -90.519)])
        self.assertEqual(vehicle["legs"][0]["streets"][0]["key"], 0)
        for leg in vehicle["legs"]:
            for edge in leg["streets"]:
                self.assertTrue(graph.has_edge(edge["u"], edge["v"], edge["key"]))

    def test_arrival_is_distinct_from_service_after_waiting(self):
        graph, data, geo, solution = fixture()
        solution.update(start_service=[10, 12], return_time=[15])
        data["earliest"][1] = 10
        stop = build_plan(graph, data, geo, solution)["vehicles"][0]["stops"][0]
        self.assertEqual((stop["arrival"], stop["service"], stop["waiting"]), (2, 10, 8))

    def test_invalid_solutions_are_rejected(self):
        for field, value in (("start_service", [0, 4]), ("return_time", [6]), ("total_cost", 1),
                             ("departure", [2]), ("has_solution", False)):
            graph, data, geo, solution = fixture()
            solution[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_plan(graph, data, geo, solution)
        graph, data, geo, solution = fixture()
        data["distance"][0][1] += 1
        with self.assertRaisesRegex(ValueError, "matrices"):
            build_plan(graph, data, geo, solution)

    def test_dock_capacity_and_half_open_intervals(self):
        graph, data, geo, solution = fixture()
        data.update(n_vehicles=2, capacity=[1, 1], fixed_cost=[10, 10], distance_cost=[1, 1], loading_duration=[1, 1])
        solution.update(successor=[[1, 0, 2], [2, 1, 0]], used=[True, True],
                        loading_start=[0, 0], departure=[1, 1], start_service=[2, 4], return_time=[6, 7])
        solution["total_cost"] = 20 + data["distance"][0][1] + data["distance"][1][0] + data["distance"][0][2] + data["distance"][2][0]
        with self.assertRaisesRegex(ValueError, "dock capacity"):
            build_plan(graph, data, geo, solution)
        solution.update(loading_start=[0, 1], departure=[1, 2])
        plan = build_plan(graph, data, geo, solution)
        self.assertEqual(plan["peak_docks"], 1)
        self.assertEqual([interval["dock"] for interval in plan["docks"]], [1, 1])

    def test_successor_decoder_rejects_disconnected_cycles_and_duplicates(self):
        for successor, used in (([[1, 1, 0]], [True]), ([[0, 2, 1]], [False]),
                                ([[1, 0], [1, 0]], [True, True]), ([[3, 0]], [True])):
            with self.subTest(successor=successor), self.assertRaises(ValueError):
                routes_from_successors(successor, used)

    def test_html_controls_times_and_clock_rollover(self):
        graph, data, geo, solution = fixture()
        html = make_map(graph, data, geo, solution, start_time="08:00").get_root().render()
        for label in ("Operación de rutas", "Servicio / ventana", "08:02", "Muelles del depósito", "road-arrow", "L.control.layers"):
            self.assertIn(label, html)
        self.assertEqual(clock(90, 23 * 60), "00:30 (+1d)")
        with self.assertRaises(ValueError):
            make_map(graph, data, geo, solution, start_time="25:00")

    def test_customer_labels_cannot_inject_script_templates(self):
        graph, data, geo, solution = fixture()
        geo["nodes"][1]["id"] = '</script><script>alert(1)</script>`${alert(1)}'
        html = make_map(graph, data, geo, solution).get_root().render()
        self.assertNotIn('</script><script>alert(1)</script>', html)
        self.assertNotIn('`${alert(1)}', html)

    def test_file_provenance_and_graph_hash(self):
        graph, data, geo, solution = fixture()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            instance, graph_file = directory / "input.json", directory / "roads.graphml"
            solution_file, output = directory / "solution.json", directory / "map.html"
            instance.write_text(json.dumps(data))
            digest = hashlib.sha256(instance.read_bytes()).hexdigest()
            ox.io.save_graphml(graph, graph_file)
            geo.update(instance_sha256=digest, graph_cache=str(graph_file), graph_sha256=hashlib.sha256(graph_file.read_bytes()).hexdigest())
            solution["instance_sha256"] = digest
            instance.with_suffix(".geo.json").write_text(json.dumps(geo))
            solution_file.write_text(json.dumps(solution))
            self.assertEqual(render_map(instance, solution_file, output), output)
            self.assertTrue(output.exists())
            graph_file.write_text(graph_file.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "GraphML checksum"):
                render_map(instance, solution_file, output)
            solution["instance_sha256"] = "stale"
            solution_file.write_text(json.dumps(solution))
            with self.assertRaisesRegex(ValueError, "checksums"):
                render_map(instance, solution_file, output)


if __name__ == "__main__":
    unittest.main()

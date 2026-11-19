"""Build road-based MiniZinc instances and solve them."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Download/cache OSM and build matrices")
    build.add_argument("raw", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    build.add_argument("--refresh", action="store_true")
    build.add_argument("--max-snap-distance", type=float, default=250, metavar="METRES")
    solve = commands.add_parser("solve", help="Solve a JSON instance through MiniZinc Python")
    solve.add_argument("instance", type=Path)
    solve.add_argument("--solver", default="cp-sat")
    solve.add_argument("--time-limit", type=float, default=30)
    solve.add_argument("--minizinc")
    solve.add_argument("--output", type=Path)
    render = commands.add_parser("render", help="Render a road-following operational HTML map")
    render.add_argument("instance", type=Path)
    render.add_argument("solution", type=Path)
    render.add_argument("output", type=Path)
    render.add_argument("--geo", type=Path, help="Defaults to instance.geo.json")
    render.add_argument("--graph", type=Path, help="Original GraphML; defaults to metadata cache path")
    render.add_argument("--start-time", default="08:00", help="Clock time corresponding to model minute 0")
    args = parser.parse_args()
    if args.command == "build":
        from .geo.matrix_builder import write_instance
        from .geo.osm_extractor import load_graph

        raw = json.loads(args.raw.read_text())
        graph, cached = load_graph(tuple(raw["network_bbox"]), args.cache_dir, refresh=args.refresh)
        data = write_instance(graph, args.raw, args.output, graph_file=cached, max_snap_distance_m=args.max_snap_distance)
        print(json.dumps({"instance": str(args.output), "geography": str(args.output.with_suffix('.geo.json')),
                          "graph_cache": str(cached), "n_customers": data["n_customers"]}, indent=2))
        return 0

    if args.command == "render":
        from .viz.map_renderer import render_map

        output = render_map(args.instance, args.solution, args.output,
                            geo_file=args.geo, graph_file=args.graph, start_time=args.start_time)
        print(json.dumps({"map": str(output), "start_time": args.start_time}, indent=2))
        return 0

    from .solver.mzn_runner import solve_instance

    report = solve_instance(args.instance, solver_name=args.solver, time_limit=args.time_limit, executable=args.minizinc)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content, end="")
    return 0 if report["has_solution"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

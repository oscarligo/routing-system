"""Solve a core-compatible JSON instance using the MiniZinc Python library."""

import argparse
import hashlib
import json
import math
import os
import shutil
from datetime import timedelta
from pathlib import Path
from time import perf_counter

import minizinc

ROOT = Path(__file__).resolve().parents[2]


def solve_instance(
    instance_file: Path,
    *,
    solver_name: str = "cp-sat",
    time_limit: float = 30,
    executable: str | None = None,
) -> dict:
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive seconds")
    binary = executable or os.environ.get("MINIZINC") or shutil.which("minizinc")
    if binary is None:
        bundled = Path("/Applications/MiniZincIDE.app/Contents/Resources/minizinc")
        if bundled.is_file():
            binary = str(bundled)
    if binary is None:
        raise FileNotFoundError("Install MiniZinc or set MINIZINC to its executable")
    driver = minizinc.Driver(Path(binary))
    solver = minizinc.Solver.lookup(solver_name, driver=driver)
    model = minizinc.Model(ROOT / "models/hfvrptw_core.mzn")
    # Let MiniZinc read JSON directly: its declared 0-based index sets are preserved.
    model.add_file(Path(instance_file).resolve(), parse_data=False)
    instance = minizinc.Instance(solver, model, driver=driver)
    started = perf_counter()
    result = instance.solve(time_limit=timedelta(seconds=time_limit), processes=1, random_seed=0)
    report = {
        "instance": str(instance_file),
        "instance_sha256": hashlib.sha256(Path(instance_file).read_bytes()).hexdigest(),
        "solver": solver.id,
        "solver_version": solver.version,
        "status": result.status.name,
        "has_solution": result.solution is not None,
        "optimal": result.status == minizinc.Status.OPTIMAL_SOLUTION,
        "elapsed_seconds": round(perf_counter() - started, 4),
        "statistics": {
            key: value.total_seconds() if isinstance(value, timedelta) else value
            for key, value in result.statistics.items()
        },
    }
    if result.solution is None:
        return report
    report["total_cost"] = int(result.objective)
    for name in ("successor", "used", "start_service", "loading_start", "departure", "return_time"):
        report[name] = result[name]
    report["routes"] = []
    for row, active in zip(report["successor"], report["used"]):
        route = [0]
        if active:
            current = row[0]
            while current != 0:
                if current in route or not 0 < current < len(row):
                    raise ValueError("Invalid successor cycle returned by solver")
                route.append(current)
                current = row[current]
            route.append(0)
        report["routes"].append(route)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--solver", default="cp-sat")
    parser.add_argument("--time-limit", type=float, default=30)
    parser.add_argument("--minizinc", help="Path to the MiniZinc executable (or set MINIZINC)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = solve_instance(args.instance, solver_name=args.solver, time_limit=args.time_limit, executable=args.minizinc)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content, end="")
    return 0 if report["has_solution"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

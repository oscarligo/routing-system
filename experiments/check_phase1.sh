#!/bin/sh
# Usage: MINIZINC=/path/to/minizinc sh experiments/check_phase1.sh
set -eu
cd "$(dirname "$0")/.."
MINIZINC=${MINIZINC:-minizinc}
work=$(mktemp -d "${TMPDIR:-/tmp}/routing-phase1.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

for solver in gecode highs cp-sat; do
    /usr/bin/time -p "$MINIZINC" --solver "$solver" --parallel 1 --statistics --time-limit 10000 \
        models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn \
        > "$work/$solver.out" 2> "$work/$solver.time"
    test "$(sed -n 's/^total_cost = \([0-9]*\);$/\1/p' "$work/$solver.out" | tail -n 1)" = 247
    rg -q '^==========$' "$work/$solver.out"
    elapsed=$(awk '/^real / {print $2}' "$work/$solver.time")
    printf '%s: optimal=247, total=%ss\n' "$solver" "$elapsed"
    awk -v elapsed="$elapsed" 'BEGIN {exit !(elapsed < 2)}'
done

# Demand totals 29: reducing total fleet capacity to 28 must be infeasible.
sed 's/capacity = \[8, 9, 12\];/capacity = [7, 9, 12];/' \
    data/instances/toy_10nodes.dzn > "$work/capacity.dzn"
# All three vehicles must load before their first customer windows close.
sed 's/n_docks = 2;/n_docks = 1;/' \
    data/instances/toy_10nodes.dzn > "$work/docks.dzn"
for instance in capacity docks; do
    "$MINIZINC" --solver gecode --time-limit 10000 models/hfvrptw_core.mzn \
        "$work/$instance.dzn" > "$work/$instance.out"
    rg -q '^=====UNSATISFIABLE=====$' "$work/$instance.out"
    printf '%s: infeasibility verified\n' "$instance"
done

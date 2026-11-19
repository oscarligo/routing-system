#!/bin/sh
# Usage: MINIZINC=/path/to/minizinc sh experiments/check_phase2.sh
set -eu
cd "$(dirname "$0")/.."
MINIZINC=${MINIZINC:-minizinc}
work=$(mktemp -d "${TMPDIR:-/tmp}/routing-phase2.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

# Temporary composition adds counterexamples without changing production models.
probe() {
    printf 'include "%s/models/hfvrptw_rules.mzn";\n%s\n' "$PWD" "$1" > "$work/probe.mzn"
}
run() {
    "$MINIZINC" --solver "$solver" --parallel 1 --time-limit 60000 \
        "$work/probe.mzn" "$1" "$2" -D "$flags" > "$work/result"
    if ! rg -q "^$3$" "$work/result"; then
        cat "$work/result"
        printf 'FAIL: %s (%s)\n' "$label" "$solver" >&2
        exit 1
    fi
}

# Boundary fixture: depot departure fixed at 1, one client, one inactive vehicle.
cat > "$work/boundary.dzn" <<'DATA'
n_customers=1; n_vehicles=2; n_docks=1; horizon=400;
distance=array2d(0..1,0..1,[0,1,1,0]);
travel_time=array2d(0..1,0..1,[0,1,1,0]);
demand=array1d(0..1,[0,1]); service=array1d(0..1,[0,0]);
earliest=array1d(0..1,[0,240]); latest=array1d(0..1,[400,240]);
capacity=[1,1]; fixed_cost=[1,1]; distance_cost=[1,1]; loading_duration=[1,1];
DATA
printf 'zone_max_capacity=[1];\n' > "$work/boundary_config.dzn"
sed 's/\[0,240\]/[0,241]/; s/\[400,240\]/[400,241]/' \
    "$work/boundary.dzn" > "$work/over.dzn"
cat > "$work/tight.dzn" <<'DATA'
n_customers=2; n_vehicles=1; n_docks=1; horizon=400;
distance=array2d(0..2,0..2,[0,1,1,1,0,1,1,1,0]);
travel_time=array2d(0..2,0..2,[0,1,1,1,0,120,1,120,0]);
demand=array1d(0..2,[0,1,1]); service=array1d(0..2,[0,0,0]);
earliest=array1d(0..2,[0,120,250]); latest=array1d(0..2,[400,120,250]);
capacity=[2]; fixed_cost=[1]; distance_cost=[1]; loading_duration=[1];
DATA
printf 'zone_max_capacity=[2,2];\n' > "$work/tight_config.dzn"

for solver in gecode highs cp-sat; do
    for enabled in false true; do
        flags="enable_zone_restrictions=$enabled; enable_driver_breaks=$enabled;"
        label="original phase 1 instance, rules=$enabled"
        probe ''
        run data/instances/toy_10nodes.dzn data/instances/toy_rules_config.dzn '=========='
        test "$(sed -n 's/^total_cost = \([0-9]*\);$/\1/p' "$work/result" | tail -n 1)" = 247
    done
    for zones in false true; do
        for breaks in false true; do
            flags="enable_zone_restrictions=$zones; enable_driver_breaks=$breaks;"
            label="zones=$zones breaks=$breaks"
            probe ''
            run data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn '=========='
            expected=246
            if [ "$zones" = true ]; then expected=253; fi
            test "$(sed -n 's/^total_cost = \([0-9]*\);$/\1/p' "$work/result" | tail -n 1)" = "$expected"
            printf '%s: %s, optimal=%s\n' "$solver" "$label" "$expected"
        done
    done

    flags='enable_zone_restrictions=true; enable_driver_breaks=false;'
    label='forbidden large vehicle at node 8'
    probe 'constraint assigned[3,8];'
    run data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn '=====UNSATISFIABLE====='
    flags='enable_zone_restrictions=false; enable_driver_breaks=false;'
    label='same assignment allowed with zones off'
    run data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn '=========='

    flags='enable_zone_restrictions=false; enable_driver_breaks=true;'
    label='long route cannot skip break'
    probe 'constraint forall(k in VEHICLES)(break_after[k] = 0);'
    run data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn '=====UNSATISFIABLE====='

    label='exactly 240 minutes needs no break; inactive vehicle consumes none'
    probe 'constraint loading_start[1]=0 /\ used[1] /\ not used[2] /\ break_after[1]=0;'
    run "$work/boundary.dzn" "$work/boundary_config.dzn" '=========='
    label='241 minutes cannot skip break'
    run "$work/over.dzn" "$work/boundary_config.dzn" '=====UNSATISFIABLE====='
    label='break after last service adds 30 minutes to actual return'
    probe 'constraint loading_start[1]=0 /\ used[1] /\ not used[2] /\ route_finish[1]=272;'
    # Starting at exactly departure+240 is allowed; 241+30+1 gives return 272.
    run "$work/over.dzn" "$work/boundary_config.dzn" '=========='
    label='break cannot overlap return travel'
    probe 'constraint loading_start[1]=0 /\ used[1] /\ not used[2] /\ route_finish[1]<272;'
    run "$work/over.dzn" "$work/boundary_config.dzn" '=====UNSATISFIABLE====='
    label='break cannot overlap intercustomer travel or service windows'
    probe 'constraint loading_start[1]=0;'
    run "$work/tight.dzn" "$work/tight_config.dzn" '=====UNSATISFIABLE====='
    flags='enable_zone_restrictions=false; enable_driver_breaks=false;'
    label='tight route feasible when breaks disabled'
    run "$work/tight.dzn" "$work/tight_config.dzn" '=========='
    printf '%s: zone exclusion, break necessity, boundary, inactive vehicle and return timing verified\n' "$solver"
done

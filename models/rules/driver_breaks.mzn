bool: enable_driver_breaks;
int: break_threshold = 240;
int: break_duration = 30;
constraint assert(break_threshold > 0 /\ break_duration > 0,
                  "Break threshold and duration must be positive minutes");

% A break is taken at a visited customer, immediately after service.
% 0 means no break; this module models a single break, not recurring shifts.
array[VEHICLES] of var NODES: break_after;
array[VEHICLES] of var 0..horizon: break_start;
array[VEHICLES] of var 0..horizon: route_finish;
constraint if enable_driver_breaks then forall(k in VEHICLES)(
    (not used[k] -> break_after[k] = 0) /\
    (break_after[k] = 0 -> break_start[k] = 0) /\
    (not used[k] -> route_finish[k] = 0) /\
    route_finish[k] <= return_time[k] /\
    (used[k] /\ route_finish[k] - departure[k] > break_threshold ->
        break_after[k] != 0) /\
    (break_after[k] != 0 -> break_start[k] <= departure[k] + break_threshold) /\
    forall(i in CUSTOMERS)(
        (break_after[k] = i -> (assigned[k,i] /\
            break_start[k] = start_service[i] + service[i])) /\
        forall(j in CUSTOMERS where i != j)(
            successor[k,i] = j /\ break_after[k] = i ->
            start_service[i] + service[i] + break_duration + travel_time[i,j] <= start_service[j]
        ) /\
        (successor[k,i] = 0 -> route_finish[k] = start_service[i] + service[i] +
            travel_time[i,0] + break_duration * bool2int(break_after[k] = i))
    )
) else forall(k in VEHICLES)(
    break_after[k] = 0 /\ break_start[k] = 0 /\ route_finish[k] = return_time[k]
) endif;

output ["break_after = ", show(break_after), ";\n",
        "break_start = ", show(break_start), ";\n",
        "route_finish = ", show(route_finish), ";\n"];

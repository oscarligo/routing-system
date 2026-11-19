% Capacity is the vehicle-size proxy, in the same units as capacity[].
bool: enable_zone_restrictions;
array[CUSTOMERS] of int: zone_max_capacity;
constraint assert(forall(i in CUSTOMERS)(zone_max_capacity[i] >= 0),
                  "Zone capacity limits must be nonnegative");
constraint forall(k in VEHICLES, i in CUSTOMERS)(
    enable_zone_restrictions /\ capacity[k] > zone_max_capacity[i] -> not assigned[k,i]
);

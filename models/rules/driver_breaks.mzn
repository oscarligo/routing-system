% Regla opcional de descanso: incluir mediante hfvrptw_rules.mzn.
% Tiempos en minutos. Se modela una sola pausa por ruta, no pausas recurrentes.
% La duracion de ruta incluye viaje, servicio y espera, pero no carga inicial.
% No pretende representar por completo una normativa laboral.
bool: enable_driver_breaks;
int: break_threshold = 240;
int: break_duration = 30;
constraint assert(break_threshold > 0 /\ break_duration > 0,
                  "Break threshold and duration must be positive minutes");

% break_after[k]: cliente tras cuyo servicio descansa k; cero significa sin pausa.
% break_start[k]: inicio de la pausa, inmediatamente despues de ese servicio.
% route_finish[k]: regreso calculado desde el ultimo cliente, sin la holgura
% de return_time. Evita exigir descansos por un regreso artificialmente tardio.
array[VEHICLES] of var NODES: break_after;
array[VEHICLES] of var 0..horizon: break_start;
array[VEHICLES] of var 0..horizon: route_finish;
% Si la ruta supera 240 minutos se exige pausa; exactamente 240 no la exige.
% Tambien se permite descansar en rutas cortas. La pausa debe comenzar a mas
% tardar 240 minutos despues de salir y no se solapa con servicio ni conduccion.
constraint if enable_driver_breaks then forall(k in VEHICLES)(
    (not used[k] -> break_after[k] = 0) /\
    (break_after[k] = 0 -> break_start[k] = 0) /\
    (not used[k] -> route_finish[k] = 0) /\
    route_finish[k] <= return_time[k] /\
    (used[k] /\ route_finish[k] - departure[k] > break_threshold ->
        break_after[k] != 0) /\
    (break_after[k] != 0 -> break_start[k] <= departure[k] + break_threshold) /\
    % Vincular la pausa a un cliente visitado y retrasar el siguiente viaje.
    forall(i in CUSTOMERS)(
        (break_after[k] = i -> (assigned[k,i] /\
            break_start[k] = start_service[i] + service[i])) /\
        forall(j in CUSTOMERS where i != j)(
            successor[k,i] = j /\ break_after[k] = i ->
            start_service[i] + service[i] + break_duration + travel_time[i,j] <= start_service[j]
        ) /\
        % Si la pausa ocurre en el ultimo cliente, tambien retrasa el regreso.
        (successor[k,i] = 0 -> route_finish[k] = start_service[i] + service[i] +
            travel_time[i,0] + break_duration * bool2int(break_after[k] = i))
    )
% Regla apagada: fijar variables auxiliares y conservar el regreso del nucleo.
) else forall(k in VEHICLES)(
    break_after[k] = 0 /\ break_start[k] = 0 /\ route_finish[k] = return_time[k]
) endif;

% Campos adicionales: un valor por vehiculo, en orden 1..n_vehicles.
output ["break_after = ", show(break_after), ";\n",
        "break_start = ", show(break_start), ";\n",
        "route_finish = ", show(route_finish), ";\n"];

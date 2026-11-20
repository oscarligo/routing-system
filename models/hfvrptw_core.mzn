% HFVRPTW-C: ruteo con flota heterogenea, ventanas y muelles limitados.
% Entrada independiente: este modelo + data/instances/toy_10nodes.dzn.
% Ejecucion desde la raiz:
% minizinc --solver gecode models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn
% Convenciones: deposito 0; clientes 1..n_customers; vehiculos 1..n_vehicles.
% Tiempos enteros en minutos desde la apertura. distance y distance_cost
% deben usar unidades compatibles; no se presupone simetria de las matrices.

% 1. Restricciones globales de la biblioteca estandar de MiniZinc.
include "subcircuit.mzn";
include "cumulative.mzn";

% 2. Dimensiones y conjuntos de indices definidos por la instancia.
int: n_customers;
int: n_vehicles;
int: n_docks;
int: horizon;
set of int: CUSTOMERS = 1..n_customers;
set of int: NODES = 0..n_customers;
set of int: VEHICLES = 1..n_vehicles;

% 3. Datos: matrices origen-destino, demanda y ventanas de inicio de servicio.
% earliest[0] y latest[0] delimitan la operacion del deposito.
array[NODES, NODES] of int: distance;
array[NODES, NODES] of int: travel_time;
array[NODES] of int: demand;
array[NODES] of int: earliest;
array[NODES] of int: latest;
array[NODES] of int: service;
% Capacidad de carga, costo fijo, tarifa por distancia y duracion de carga.
array[VEHICLES] of int: capacity;
array[VEHICLES] of int: fixed_cost;
array[VEHICLES] of int: distance_cost;
array[VEHICLES] of int: loading_duration;

% 4. Validacion de datos: rechazar parametros inconsistentes antes de buscar.
constraint assert(n_customers > 0 /\ n_vehicles > 0 /\ n_docks > 0 /\ horizon > 0,
                  "Counts and horizon must be positive");
constraint assert(demand[0] = 0 /\ service[0] = 0, "Depot demand and service must be zero");
constraint assert(forall(i in NODES)(demand[i] >= 0 /\ service[i] >= 0 /\
                  0 <= earliest[i] /\ earliest[i] <= latest[i] /\ latest[i] <= horizon),
                  "Invalid demands, service times or windows");
constraint assert(forall(i,j in NODES)(distance[i,j] >= 0 /\ travel_time[i,j] >= 0 /\
                  (i != j \/ (distance[i,j] = 0 /\ travel_time[i,j] = 0))),
                  "Matrices must be nonnegative with zero diagonals");
constraint assert(forall(k in VEHICLES)(capacity[k] > 0 /\ fixed_cost[k] >= 0 /\
                  distance_cost[k] >= 0 /\ loading_duration[k] > 0 /\ loading_duration[k] <= horizon),
                  "Invalid vehicle parameters");

% 5. Variables de decision.
% successor[k,i]: nodo siguiente a i en la ruta de k; i indica exclusion.
% assigned[k,i]: cliente i atendido por k; used[k]: vehiculo k activo.
array[VEHICLES, NODES] of var NODES: successor;
array[VEHICLES, CUSTOMERS] of var bool: assigned;
array[VEHICLES] of var bool: used;
% Un horario por cliente basta porque cada uno se asigna a un unico vehiculo.
array[CUSTOMERS] of var 0..horizon: start_service;
array[VEHICLES] of var 0..horizon: loading_start;
array[VEHICLES] of var 0..horizon: departure;
% Regreso factible con posible holgura; el objetivo no minimiza horarios.
array[VEHICLES] of var 0..horizon: return_time;

% 6. Rutas y capacidad. subcircuit forma un unico ciclo por vehiculo;
% las equivalencias obligan a incluir el deposito si se atiende algun cliente.
constraint forall(k in VEHICLES)(
    subcircuit(array1d(NODES, [successor[k,i] | i in NODES])) /\
    (used[k] <-> successor[k,0] != 0) /\
    (used[k] <-> exists(i in CUSTOMERS)(assigned[k,i])) /\
    forall(i in CUSTOMERS)(assigned[k,i] <-> successor[k,i] != i) /\
    sum(i in CUSTOMERS)(demand[i] * bool2int(assigned[k,i])) <= capacity[k]
);
% Cobertura exacta: ningun cliente queda fuera ni se atiende dos veces.
constraint forall(i in CUSTOMERS)(sum(k in VEHICLES)(bool2int(assigned[k,i])) = 1);
% La ventana restringe el inicio del servicio, no la llegada al cliente.
constraint forall(i in CUSTOMERS)(earliest[i] <= start_service[i] /\ start_service[i] <= latest[i]);

% 7. Secuencia temporal: carga, primer viaje, servicios y regreso.
% Separar salida y regreso evita imponer un ciclo de precedencias en el tiempo.
% Las desigualdades permiten esperar entre visitas; los inactivos quedan a cero.
constraint forall(k in VEHICLES)(
    (used[k] -> (loading_start[k] >= earliest[0] /\
                departure[k] = loading_start[k] + loading_duration[k] /\
                departure[k] <= return_time[k] /\ return_time[k] <= latest[0])) /\
    (not used[k] -> (loading_start[k] = 0 /\ departure[k] = 0 /\ return_time[k] = 0)) /\
    forall(j in CUSTOMERS)(successor[k,0] = j ->
        departure[k] + travel_time[0,j] <= start_service[j]) /\
    forall(i,j in CUSTOMERS where i != j)(successor[k,i] = j ->
        start_service[i] + service[i] + travel_time[i,j] <= start_service[j]) /\
    forall(i in CUSTOMERS)(successor[k,i] = 0 ->
        start_service[i] + service[i] + travel_time[i,0] <= return_time[k])
);
% 8. Muelles compartidos: cada vehiculo activo consume una unidad durante
% [loading_start, departure). Un muelle se puede reutilizar al terminar la carga.
constraint cumulative(loading_start, loading_duration,
                      [bool2int(used[k]) | k in VEHICLES], n_docks);

% 9. Objetivo: activacion + tarifa por distancia de todos los arcos usados.
% La cota finita admite como maximo n_customers + 1 arcos por vehiculo.
% Los bucles de exclusion no cuestan porque la diagonal de distance es cero.
int: max_distance = max(i,j in NODES)(distance[i,j]);
int: cost_upper_bound = sum(k in VEHICLES)(fixed_cost[k] +
    distance_cost[k] * (n_customers + 1) * max_distance);
var 0..cost_upper_bound: total_cost = sum(k in VEHICLES)(
    fixed_cost[k] * bool2int(used[k]) +
    distance_cost[k] * sum(i in NODES)(distance[i,successor[k,i]])
);
solve minimize total_cost;

% 10. Salida textual: matrices por filas e indices en el orden declarado.
% El modulo de descansos agrega sus propios campos al incluir este nucleo.
output ["total_cost = ", show(total_cost), ";\n",
        "successor (rows = vehicles, columns = depot 0 then customers) = ", show(successor), ";\n",
        "used = ", show(used), ";\n",
        "start_service = ", show(start_service), ";\n",
        "loading_start = ", show(loading_start), ";\n",
        "departure = ", show(departure), ";\n",
        "return_time = ", show(return_time), ";\n"];

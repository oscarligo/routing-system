% Regla opcional de acceso: incluir mediante hfvrptw_rules.mzn.
% enable_zone_restrictions activa la regla; zone_max_capacity[i] define
% el tamano maximo admitido en el cliente i, en las unidades de capacity.
% La capacidad del vehiculo aproxima su tamano; no es su carga transportada.
% La igualdad esta permitida; cero impide asignar cualquier vehiculo.
% No modela placas ni restricciones en calles intermedias de la ruta.
bool: enable_zone_restrictions;
array[CUSTOMERS] of int: zone_max_capacity;
constraint assert(forall(i in CUSTOMERS)(zone_max_capacity[i] >= 0),
                  "Zone capacity limits must be nonnegative");
% Al desactivar el indicador no se restringe la asignacion por zona.
constraint forall(k in VEHICLES, i in CUSTOMERS)(
    enable_zone_restrictions /\ capacity[k] > zone_max_capacity[i] -> not assigned[k,i]
);

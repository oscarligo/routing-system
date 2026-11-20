% Punto de entrada del modelo con reglas opcionales.
% Conserva estas rutas relativas: nucleo al lado de este archivo y reglas
% dentro de rules/. No ejecutar los modulos de reglas como modelos aislados.
% Datos: toy_rules_10nodes.dzn + toy_rules_config.dzn, en data/instances/.
% Proporcionar ambos indicadores con -D o en un archivo .dzn adicional:
% enable_zone_restrictions=true; enable_driver_breaks=true;
% El nucleo aporta variables, objetivo y salida; cada modulo agrega restricciones.
include "hfvrptw_core.mzn";
include "rules/zone_restrictions.mzn";
include "rules/driver_breaks.mzn";

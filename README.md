# Optimización Logística mediante Programación por Restricciones (HFVRPTW-C)

---

## 1. Contexto General y Motivación

La distribución de mercancías en entornos urbanos e interurbanos constituye uno de los desafíos operacionales más complejos de la logística moderna. El problema tradicional de ruteo de vehículos (VRP, *Vehicle Routing Problem*) evoluciona rápidamente en escenarios reales hacia formas altamente condicionadas, donde convergen restricciones operativas heterogéneas, compromisos comerciales con clientes y cuellos de botella en la infraestructura física de los centros de distribución.

Las aproximaciones imperativas tradicionales exigen el desarrollo de heurísticas a medida o código procedural acoplado al algoritmo de búsqueda, lo que dificulta la incorporación de nuevas reglas de negocio. En contraste, la **Programación por Restricciones** y el modelado declarativo en **MiniZinc** permiten desacoplar completamente la definición del problema (el *qué*) de la lógica de resolución (el *cómo*), facilitando la evaluación de múltiples paradigmas de optimización (**CP, MIP y SAT/CP Híbrido**) a través del compilador a **FlatZinc**.

---

## 2. Definición del Problema: HFVRPTW-C

El problema a resolver se define como el **Problema de Ruteo de Vehículos con Flota Heterogénea, Ventanas de Tiempo y Capacidad Limitada de Carga en Depósito** (*Heterogeneous Fleet Vehicle Routing Problem with Time Windows and Depot Capacity Constraints*, HFVRPTW-C).

### 2.1. Componentes Operativos

1. **Flota Heterogénea de Vehículos:**
   - La empresa cuenta con una flota $K$ compuesta por distintos tipos de vehículos.
   - Cada vehículo $k \in K$ posee una capacidad fija de carga $Q_k$, un costo fijo de activación $F_k$ y un costo variable por unidad de distancia recorrida $C_k$.

2. **Red de Clientes y Ventanas de Tiempo:**
   - Se debe atender a un conjunto $N = \{1, 2, \dots, n\}$ de clientes distribuidos geográficamente.
   - Cada cliente $i \in N$ demanda una cantidad $d_i$ de producto y exige ser atendido dentro de una ventana de tiempo rígida $[a_i, b_i]$.
   - Si un vehículo llega antes del tiempo $a_i$, debe esperar hasta la apertura de la ventana sin incurrir en penalizaciones adicionales, pero no puede iniciar la atención después de $b_i$. Cada cliente requiere un tiempo de servicio $s_i$.

3. **Cuello de Botella en el Depósito (`cumulative`):**
   - El centro de distribución (nodo $0$) dispone de un número finito $M_{\text{muelles}}$ de bahías o muelles de carga simultánea.
   - Cada vehículo $k$ requiere un tiempo de alistamiento y carga $\delta_k$ en el muelle antes de poder iniciar su ruta.
   - La salida de los vehículos del depósito debe coordinarse para evitar exceder la capacidad física $M_{\text{muelles}}$ en cualquier instante de tiempo.

4. **Agilidad Declarativa ante Reglas Dinámicas:**
   - El modelo debe permitir inyectar o desactivar fácilmente restricciones operativas del mundo real (ej. compatibilidad vehículo-cliente, zonas de acceso restringido por placa o descansos obligatorios de conductores) mediante restricciones aisladas sin alterar la estructura general del modelo ni el solver subyacente.

---

## 3. Formulación Matemática Preliminar

### 3.1. Conjuntos y Parámetros

- $N_0 = N \cup \{0\}$: Conjunto de nodos (donde $0$ representa el depósito principal).
- $K$: Conjunto de vehículos disponibles.
- $c_{ij}$: Distancia/tiempo de traslado entre los nodos $i, j \in N_0$.
- $d_i$: Demanda del cliente $i \in N$ ($d_0 = 0$).
- $[a_i, b_i]$: Ventana de tiempo para iniciar el servicio en el cliente $i \in N_0$.
- $s_i$: Tiempo de servicio en el nodo $i \in N_0$ ($s_0 = 0$).
- $Q_k$: Capacidad de carga del vehículo $k \in K$.
- $F_k$: Costo fijo de activación del vehículo $k \in K$.
- $C_k$: Costo variable por unidad de distancia del vehículo $k \in K$.
- $\delta_k$: Tiempo de ocupación del muelle de carga por el vehículo $k \in K$.
- $M_{\text{muelles}}$: Número de bahías de carga disponibles simultáneamente en el depósito.

### 3.2. Variables de Decisión

- $x_{ijk} \in \{0, 1\}$: Vale $1$ si el vehículo $k \in K$ transita directamente del nodo $i$ al nodo $j$, y $0$ en caso contrario.
- $t_i \ge 0$: Tiempo de inicio del servicio en el nodo $i \in N_0$.
- $u_k \ge 0$: Tiempo de salida del vehículo $k \in K$ desde el depósito.
- $y_k \in \{0, 1\}$: Vale $1$ si el vehículo $k \in K$ es utilizado en la planificación.

### 3.3. Restricciones Principales y Restricciones Globales

1. **Visita Única y Cobertura Completa (`alldifferent`):**
   Cada cliente $i \in N$ debe ser visitado exactamente una vez por un único vehículo:
   $$\sum_{k \in K} \sum_{j \in N_0, j \neq i} x_{ijk} = 1 \quad \forall i \in N$$

   En el modelo MiniZinc, las secuencias de rutas se modelan mediante arrays de sucesores optimizados con la restricción global `alldifferent` o `circuit`.

2. **Capacidad Limitada de Bahías en Depósito (`cumulative`):**
   La salida de los vehículos desde el centro de distribución está acotada por el número de muelles $M_{\text{muelles}}$:
   $$\text{cumulative}\left( [u_k \mid k \in K], [\delta_k \mid k \in K], [y_k \mid k \in K], M_{\text{muelles}} \right)$$

3. **Respeto a la Capacidad de la Flota:**
   La suma de las demandas de los clientes asignados al vehículo $k$ no excede su capacidad $Q_k$:
   $$\sum_{i \in N} d_i \left( \sum_{j \in N_0, j \neq i} x_{ijk} \right) \le Q_k \cdot y_k \quad \forall k \in K$$

4. **Ventanas de Tiempo e Sincronización Temporal:**
   $$t_i + s_i + c_{ij} - M(1 - x_{ijk}) \le t_j \quad \forall i, j \in N_0, \forall k \in K$$
   $$a_i \le t_i \le b_i \quad \forall i \in N_0$$

### 3.4. Función Objetivo Multicriterio

Se busca minimizar una función global de costos que balancea el costo fijo de la flota activada y el costo variable del recorrido total:

$$\min \quad Z = \sum_{k \in K} F_k \cdot y_k + \sum_{k \in K} C_k \sum_{i \in N_0} \sum_{j \in N_0} c_{ij} \cdot x_{ijk}$$

---

## 4. Arquitectura Tecnológica y Filosofía "Model Once, Solve Anywhere"

El proyecto adopta un enfoque desacoplado en dos capas principales:

```
+-------------------------------------------------------------+
|               Capa de Integracion (Python)                  |
|  - Generacion de instancias y lectura de datos              |
|  - Orquestacion via MiniZinc-Python API                     |
|  - Procesamiento, visualizacion de rutas y metricas         |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                Capa de Modelado (MiniZinc)                  |
|  - Modelo declarativo puro (.mzn)                           |
|  - Uso de restricciones globales (alldifferent, cumulative) |
|  - Compilacion a FlatZinc (.fzn)                            |
+-------------------------------------------------------------+
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
    +--------------+   +--------------+   +--------------+
    | CP Engine    |   | MIP Engine   |   | SAT/CP Engine|
    | (Gecode)     |   | (HiGHS)      |   | (OR-Tools)   |
    +--------------+   +--------------+   +--------------+
```

### 4.1. El Rol de FlatZinc y la Portabilidad entre Solvers
MiniZinc compila el modelo abstracto `.mzn` junto con los datos `.dzn` a una representación intermedia de bajo nivel denominada **FlatZinc (`.fzn`)**. Esta arquitectura permite ejecutar el **mismo modelo matemático** en distintos motores de búsqueda sin modificar el código:
- **Gecode (CP):** Motor clásico de Programación por Restricciones especializado en propagación e inferencia sobre dominios finitos.
- **HiGHS (MIP):** Motor de Programación Entera Mixta para evaluar linealización y relajaciones continuas.
- **OR-Tools CP-SAT (Híbrido):** Solver de vanguardia basado en tecnología SAT y propagación de restricciones.

---

## 5. Objetivos del Proyecto

### 5.1. Objetivo General
Diseñar, formular e implementar un modelo de optimización declarativo en MiniZinc integrado con Python para resolver el problema HFVRPTW-C, evaluando la agilidad declarativa de la herramienta y comparando cuantitativamente el desempeño de compilación a FlatZinc y resolución bajo motores CP, MIP y SAT/CP Híbrido.

### 5.2. Objetivos Específicos
1. **Formulación y Restricciones Globales:** Formular de forma matemática rigurosa las restricciones de ruteo, heterogeneidad de flota, ventanas de tiempo y capacidad en depósito aprovechando las restricciones globales `alldifferent` y `cumulative`.
2. **Evaluación Multiparadigma (*Model Once, Solve Anywhere*):** Comparar el rendimiento (tiempo de respuesta, calidad del valor objetivo y brecha de optimalidad) entre los solvers Gecode (CP), HiGHS (MIP) y OR-Tools CP-SAT ante instancias de escala pequeña, mediana y grande.
3. **Análisis del Proceso de *Flattening*:** Analizar la transformación del modelo `.mzn` a `.fzn`, evaluando la explosión combinatoria del número de variables y restricciones generadas al escalar el tamaño de la red de clientes.
4. **Agilidad Declarativa ante Reglas Dinámicas:** Demostrar la flexibilidad del paradigma agregando y removiendo restricciones de negocio secundarias (ej. restricciones de incompatibilidad de carga o ventanas de descanso) sin alterar la arquitectura algorítmica ni el código en Python.
5. **Capa de Visualización e Interfaz:** Desarrollar un módulo en Python que automatice el flujo de datos, ejecute las pruebas experimentales y genere diagramas de Gantt (para uso de muelles) y mapas interactivos de las rutas óptimas resultantes.

---

## 6. Plan de Experimentación y Evaluación de Escalabilidad

Las pruebas experimentales se realizarán sobre un conjunto de instancias adaptadas de la literatura estándar (Solomon / VRPTW adaptadas a flota heterogénea y muelles), clasificadas en tres niveles:

| Escenario | Clientes ($N$) | Flota ($K$) | Muelles ($M_{\text{muelles}}$) | Propósito del Experimento |
| :--- | :--- | :--- | :--- | :--- |
| **Pequeno** | $10 - 20$ | $3 - 5$ | $2$ | Validación de exactitud matemática y prueba de optimalidad global. |
| **Mediano** | $25 - 50$ | $6 - 10$ | $3$ | Comparación de velocidad de propagador vs. relajación lineal (CP vs. MIP). |
| **Grande** | $100+$ | $15+$ | $4 - 5$ | Evaluación del límite de escalabilidad, flattening time y rendimiento de CP-SAT. |

---

## 7. Resultados Esperados

- Modelo declarativo en MiniZinc altamente legible, modular y mantenible.
- Estudio comparativo detallado que identifique qué paradigma (CP, MIP o SAT) responde mejor al problema HFVRPTW-C según el tamaño de la instancia.
- Demostración práctica de cómo la restricción `cumulative` modela con exactitud y eficiencia los cuellos de botella en depósitos logísticos.
- Cuadro comparativo del impacto del *flattening* (tiempo de traducción y tamaño del archivo `.fzn`).

---

## 8. Estructura del Repositorio

El repositorio contiene el planteamiento, el núcleo MiniZinc y una instancia
sintética ejecutable (fase 1), más reglas modulares de zonas y descansos
(fase 2), el pipeline geoespacial Python + OpenStreetMap (fase 3) y el mapa
operativo Folium (fase 4).
Los `.gitkeep` conservan las carpetas reservadas. Los perfiles, la cadena de
frío, el clustering y el contenedor siguen pendientes.
La sección 9 interpreta los resultados obtenidos.

```text
routing-system/
├── README.md
├── pyproject.toml
├── models/
│   ├── hfvrptw_core.mzn
│   ├── hfvrptw_rules.mzn
│   ├── rules/
│   │   ├── zone_restrictions.mzn
│   │   ├── driver_breaks.mzn
│   │   └── .gitkeep
│   ├── extensions/
│   │   └── .gitkeep
│   └── profiles/
│       └── .gitkeep
├── src/
│   ├── cli.py
│   ├── geo/
│   │   ├── osm_extractor.py
│   │   ├── matrix_builder.py
│   │   └── .gitkeep
│   ├── decomposition/
│   │   └── .gitkeep
│   ├── solver/
│   │   ├── mzn_runner.py
│   │   ├── routes.py
│   │   └── .gitkeep
│   └── viz/
│       ├── map_renderer.py
│       └── .gitkeep
├── data/
│   ├── raw/
│   │   ├── guatemala_zona1_15.json
│   │   └── .gitkeep
│   ├── cache/
│   │   └── .gitkeep
│   ├── maps/
│   │   └── guatemala_zona1_15.html
│   └── instances/
│       ├── guatemala_zona1_15.json
│       ├── guatemala_zona1_15.geo.json
│       ├── guatemala_zona1_15.solution.json
│       ├── toy_10nodes.dzn
│       ├── toy_rules_10nodes.dzn
│       ├── toy_rules_config.dzn
│       └── .gitkeep
├── experiments/
│   ├── check_phase1.sh
│   ├── check_phase2.sh
│   └── .gitkeep
└── tests/
    ├── test_geospatial.py
    └── test_map_renderer.py
```

### 8.1. Archivos y Responsabilidades

`models/hfvrptw_core.mzn`, `models/rules/zone_restrictions.mzn` y
`models/rules/driver_breaks.mzn` ya están implementados. También existen
`pyproject.toml`, `src/cli.py`, los módulos de `src/geo/` y
`src/solver/mzn_runner.py` y `src/viz/map_renderer.py`; los demás archivos de esta tabla corresponden a
fases posteriores. El árbol omite los archivos Python `__init__.py`.

| Ruta prevista | Responsabilidad |
| :--- | :--- |
| `pyproject.toml` | Dependencias de Python: minizinc, osmnx, networkx, folium y scikit-learn para snapping geográfico. |
| `Dockerfile` | Proveer un entorno reproducible con MiniZinc, Gecode, HiGHS y OR-Tools. |
| `models/hfvrptw_core.mzn` | Núcleo declarativo agnóstico del solver: rutas con `subcircuit`, capacidad de muelles con `cumulative` y ventanas de tiempo. |
| `models/rules/zone_restrictions.mzn` | Restricciones modulares de compatibilidad vehículo-zona, como acceso de carga pesada. |
| `models/rules/cold_chain.mzn` | Prioridad o tiempo máximo en ruta para mercancía perecedera. |
| `models/rules/driver_breaks.mzn` | Ventanas obligatorias de descanso de conductores. |
| `models/extensions/lns_search.mzn` | Búsqueda `relax_and_reconstruct` para instancias que superen el alcance práctico de la resolución exacta. |
| `models/profiles/cp_gecode.mpc` | Perfil de ejecución para programación por restricciones con Gecode. |
| `models/profiles/mip_highs.mpc` | Perfil de ejecución para programación entera mixta con HiGHS. |
| `models/profiles/sat_ortools.mpc` | Perfil de ejecución para CP-SAT híbrido con OR-Tools. |
| `src/cli.py` | Punto de entrada único para la capa de datos y orquestación. |
| `src/geo/osm_extractor.py` | Descargar y almacenar en caché la red vial de OpenStreetMap. |
| `src/geo/matrix_builder.py` | Construir matrices asimétricas y exportar datos JSON para MiniZinc. |
| `src/decomposition/clusterer.py` | Particionamiento espacial capacitado para instancias de más de 100 nodos. |
| `src/solver/mzn_runner.py` | Ejecutar MiniZinc, gestionar la compilación a FlatZinc y extraer métricas. |
| `src/viz/map_renderer.py` | Representar rutas sobre calles reales en mapas HTML con Folium. |
| `experiments/compare_paradigms.py` | Medir tiempo de compilación, tamaño de `.fzn` y tiempo de resolución por paradigma. |
| `experiments/benchmark_agility.py` | Evaluar el impacto de activar o desactivar las restricciones de `models/rules/`. |

Los perfiles buscan facilitar el enfoque «Model once, solve anywhere». Su
compatibilidad con las restricciones y anotaciones elegidas deberá validarse
cuando se implementen los modelos y se configuren los motores.

### 8.2. Organización de Datos

| Directorio | Contenido previsto |
| :--- | :--- |
| `data/raw/` | Pedidos, coordenadas, ventanas horarias y definición de la flota. |
| `data/cache/` | Grafos viales locales en formato `.graphml`. |
| `data/instances/` | Instancias `.json` o `.dzn` listas para MiniZinc. |
| `data/maps/` | Mapas HTML operativos con calles, rutas y horarios. |

### 8.3. Guía de Uso

Se puede ejecutar directamente MiniZinc o usar el pipeline Python mediante
`src/cli.py`. Al implementar cada componente pendiente,
su código se ubicará en la ruta prevista de la tabla y se podrá retirar el
`.gitkeep` de esa carpeta cuando contenga archivos versionados.

El flujo de uso previsto es:

1. Preparar pedidos, ventanas y flota en `data/raw/`.
2. Descargar o reutilizar la red vial de `data/cache/` y construir las matrices.
3. Exportar una instancia a `data/instances/`.
4. Ejecutar el modelo central con las reglas y el perfil de solver seleccionados.
5. Visualizar las rutas con Folium y comparar las métricas mediante `experiments/`.

Las opciones de la CLI se consultan con `python -m src.cli --help`. La
construcción del contenedor se documentará cuando exista `Dockerfile`.

## 9. Interpretación de los Resultados

### 9.1. Calidad de la Solución y Uso de la Flota

La [solución registrada](data/instances/guatemala_zona1_15.solution.json) para
los 15 clientes de zona 1 de Guatemala tiene estado `OPTIMAL_SOLUTION` y costo
**16.022**. El objetivo y su cota coinciden, por lo que CP-SAT demostró que no
existe una solución de menor costo para esa instancia y las restricciones del
núcleo. Este valor suma costos fijos de activación y costos de recorrido por
metro; se expresa en unidades abstractas, no en quetzales.

| Vehículo | Clientes atendidos | Carga utilizada | Distancia recorrida | Interpretación |
| :--- | ---: | :--- | :--- | :--- |
| 1 | 0 | Inactivo | — | El plan óptimo no necesita activar toda la flota disponible. |
| 2 | 7 | 7/7 | 3,681 km | Utiliza toda su capacidad para atender el primer grupo de clientes. |
| 3 | 8 | 8/8 | 5,960 km | Completa la cobertura con una ruta más larga y capacidad totalmente ocupada. |

Los dos vehículos activos transportan las 15 unidades demandadas y recorren
**9,641 km** en total. La combinación permite cubrir a todos los clientes con
dos de los tres vehículos disponibles. La ocupación del 100 % de ambos vehículos
indica que este plan no tiene capacidad libre para añadir demanda sin revisar
la asignación o activar otro vehículo. El objetivo minimiza costo total, por lo
que no implica por sí solo la menor distancia ni el menor número de vehículos.

Las rutas obtenidas son:

- Vehículo 2: `0 → 1 → 2 → 3 → 7 → 6 → 5 → 4 → 0`.
- Vehículo 3: `0 → 8 → 9 → 11 → 10 → 13 → 15 → 14 → 12 → 0`.

El nodo `0` representa el depósito. Las distancias se calculan sobre caminos
dirigidos de la red vial: el sentido de circulación puede hacer que ir de un
cliente a otro tenga un costo distinto al recorrido inverso.

### 9.2. Cumplimiento Horario y Capacidad del Depósito

El [mapa operativo](data/maps/guatemala_zona1_15.html) muestra **15/15 servicios
iniciados dentro de su ventana horaria**. Llegar antes de la apertura es factible
si el vehículo espera; el cumplimiento se evalúa sobre el inicio del servicio.
Por eso una espera no representa necesariamente una ineficiencia evitable:
puede ser necesaria para coordinar la ruta con las ventanas de los clientes.

Tomando las 08:00 como minuto cero, el vehículo 2 ocupa un muelle de 08:00 a
08:07 y el vehículo 3 ocupa otro de 08:00 a 08:09. El pico de ocupación es
**2/2 muelles**, compatible con la capacidad del depósito. Ambos pueden cargar
simultáneamente en este plan; esto no demuestra que dos muelles sean
indispensables, pues habría que resolver nuevamente con uno para medir el efecto.
La asignación visual de cada muelle la realiza el renderer a partir de los
intervalos, no el solver.

Los regresos estimados son a las **09:00** y **10:03**, respectivamente. El
segundo recorrido combina más clientes y mayor distancia, pero su duración
también incluye servicio y posibles esperas. Los horarios no se minimizan en
la función objetivo: distintas soluciones de igual costo pueden tener horarios
diferentes. Además, `return_time` admite holgura; para interpretar la operación
conviene usar el regreso estimado al completar el último trayecto.

### 9.3. Efecto de las Reglas de Negocio

Los casos sintéticos permiten aislar el efecto de las restricciones de zonas
y descansos en la variante `toy_rules_10nodes.dzn`:

| Restricciones activas | Costo óptimo | Interpretación |
| :--- | ---: | :--- |
| Ninguna | 246 | Referencia para comparar las reglas sobre la misma instancia. |
| Zonas | 253 | La prohibición de acceso obliga a reasignar clientes entre vehículos. |
| Descansos | 246 | La pausa puede encajar en una espera sin aumentar el costo de recorrido. |
| Zonas y descansos | 253 | Se modifica la asignación y se incorpora la pausa, conservando el costo del caso con zonas. |

La restricción de zonas aumenta el costo en **7 unidades, aproximadamente
2,85 %**, respecto de la referencia. Este incremento cuantifica el costo de
cumplir esa regla en el ejemplo. Que el descanso no cambie el objetivo no
significa que carezca de efecto: modifica el horario y exige reservar una pausa
factible. En este caso, la espera antes de una ventana tardía permite absorberla.

La instancia sintética original `toy_10nodes.dzn` conserva el óptimo **247**
con las reglas activadas o desactivadas porque no fuerza esos conflictos. Sus
costos no deben compararse directamente con los 246 de la variante, que cambia
capacidades y ventanas, ni con los 16.022 del caso geoespacial, que usa otras
matrices y escalas de distancia.

### 9.4. Rendimiento y Alcance de las Conclusiones

La ejecución geoespacial registrada con CP-SAT 9.15 tardó **2,65 segundos** en
el runner, incluyendo compilación y resolución. Las estadísticas reportan
aproximadamente **0,069 segundos de compilación a FlatZinc** y **2,48 segundos
de resolución**; el resto corresponde a otras tareas de ejecución. La descarga
de OpenStreetMap y la construcción de matrices quedan fuera de esa medición.
En este caso, la búsqueda concentra la mayor parte del tiempo.

El resultado demuestra que el modelo puede resolver esta instancia pequeña
con optimalidad probada. No permite concluir qué solver es superior ni que el
mismo rendimiento se mantenga con 50 o 100 clientes: faltan mediciones comparables
por tamaño, motor y límite de tiempo. Un estado `SATISFIED` con `optimal=false`
indicaría una solución factible sin prueba de optimalidad; debe distinguirse
del estado óptimo registrado aquí.

La red vial procede de OpenStreetMap, pero las demandas, ventanas y flota son
sintéticas. Los tiempos estiman circulación en flujo libre y no incorporan
tráfico en vivo, demoras en cruces ni el acceso desde cada coordenada al nodo
vial ajustado. El mapa geoespacial corresponde al núcleo y no incorpora las
reglas adicionales de descansos y zonas. Por tanto, la solución es óptima para
los datos y supuestos modelados; su uso operativo requiere validar esos datos
y condiciones con la operación real.

Fuente de la red: **© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)**,
[Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).

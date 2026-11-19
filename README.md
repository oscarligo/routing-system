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
Las secciones 9–12 describen la ejecución disponible.

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

Se puede ejecutar directamente MiniZinc como se indica en la sección 9 o usar
el pipeline Python de la sección 11. Al implementar cada componente pendiente,
su código se ubicará en la ruta prevista de la tabla y se podrá retirar el
`.gitkeep` de esa carpeta cuando contenga archivos versionados.

El flujo de uso previsto es:

1. Preparar pedidos, ventanas y flota en `data/raw/`.
2. Descargar o reutilizar la red vial de `data/cache/` y construir las matrices.
3. Exportar una instancia a `data/instances/`.
4. Ejecutar el modelo central con las reglas y el perfil de solver seleccionados.
5. Visualizar las rutas con Folium y comparar las métricas mediante `experiments/`.

La sección 11 documenta instalación y CLI. La construcción del contenedor
se documentará cuando exista `Dockerfile`.

## 9. Fase 1: Núcleo Matemático con Datos Sintéticos

### 9.1. Alcance y Convenciones

`models/hfvrptw_core.mzn` implementa rutas con `subcircuit`, cobertura única,
capacidades heterogéneas, ventanas rígidas para el **inicio** del servicio,
espera permitida y carga de vehículos mediante `cumulative`. Cada vehículo
activo tiene un único ciclo que incluye el depósito; los nodos no asignados
son bucles a sí mismos. Los vehículos inactivos no consumen muelles ni pagan
costos. El objetivo es costo fijo de activación más distancia por tarifa de
cada vehículo, con cotas enteras finitas para los tres motores.

El depósito es el nodo **0** y los clientes son `1..n_customers`. Se conservan
esos índices al construir el array de `subcircuit`. La salida ocurre al terminar
la carga; salida y regreso tienen variables distintas para no imponer una
precedencia temporal circular. La ventana del depósito contiene toda la carga
y el regreso. `return_time` representa una hora factible de regreso y puede
incluir espera; el objetivo no minimiza horarios. Los intervalos de ocupación
de muelles son `[loading_start, departure)`.

La instancia `data/instances/toy_10nodes.dzn` tiene **11 nodos: un depósito y
10 clientes**, pese al nombre solicitado. Incluye dos muelles, tres vehículos
con capacidades `[8, 9, 12]`, costos y duraciones de carga diferentes, y matrices
asimétricas inventadas. Por simplicidad, distancia y tiempo tienen los mismos
valores en esta instancia, pero son parámetros independientes del modelo.
Los tiempos se expresan en minutos desde la apertura. Las ventanas estrechas
facilitan una primera validación; este caso no mide escalabilidad.

### 9.2. Ejecutar en MiniZinc IDE

1. Abrir `models/hfvrptw_core.mzn` y `data/instances/toy_10nodes.dzn` en MiniZinc IDE.
2. Mantener activo el `.mzn`, pulsar **Run** y seleccionar el `.dzn` cuando lo solicite.
3. Configurar **un hilo** en las opciones de ejecución para reproducir la medición.
4. Ejecutar cambiando el selector entre **Gecode**, **HiGHS** y **OR Tools CP-SAT**, con el mismo modelo y datos.
5. Comprobar `total_cost = 247;` y el marcador `==========`, que indica óptimo demostrado. Los horarios pueden diferir entre solvers.

No hacen falta archivos de perfil `.mpc` ni Python. Si el IDE no encuentra el
motor, revisar su instalación y las configuraciones listadas por `minizinc --solvers`.

### 9.3. Ejecutar y Verificar por Consola

Con `minizinc` en el `PATH`:

```sh
minizinc --solver gecode --parallel 1 --statistics models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn
minizinc --solver highs --parallel 1 --statistics models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn
minizinc --solver cp-sat --parallel 1 --statistics models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn
sh experiments/check_phase1.sh
```

En macOS puede usarse directamente el ejecutable incluido en el IDE:

```sh
MINIZINC=/Applications/MiniZincIDE.app/Contents/Resources/minizinc sh experiments/check_phase1.sh
```

El verificador requiere `sh`, `rg`, `awk`, `sed` y `/usr/bin/time`. Comprueba el
mismo óptimo demostrado en los tres motores y un tiempo total de proceso menor
a dos segundos por motor, incluyendo compilación y arranque. Además comprueba
con Gecode que reducir la capacidad total a 28 (demanda 29) o los muelles a uno
hace inviable esta instancia. Los datos modificados se crean temporalmente.

### 9.4. Resultado de Validación

Medición por consola el 19 de noviembre de 2026 en macOS ARM64, MiniZinc 2.11.0,
un hilo por motor. El modelo y la instancia también se abrieron en el IDE;
no se automatizó el selector de su interfaz gráfica.

| Solver | Versión | Óptimo demostrado | Tiempo total de proceso |
| :--- | :--- | ---: | ---: |
| Gecode | 6.6.0 | 247 | 0,60 s |
| HiGHS | 1.16.0 | 247 | 1,39 s |
| OR-Tools CP-SAT | 9.15 | 247 | 0,24 s |

Las rutas obtenidas fueron `0 → 1 → 2 → 3 → 4 → 0`,
`0 → 5 → 6 → 7 → 0` y `0 → 8 → 9 → 10 → 0` para los vehículos 1, 2 y 3.
Sus cargas son 8, 9 y 12; sus distancias, 26, 25 y 29. El costo se verifica como
`20 + 30 + 40 + 3×26 + 2×25 + 1×29 = 247`.
Un horario factible carga los vehículos en `[0,8)`, `[0,10)` y `[8,20)`:
se ocupan como máximo dos muelles y los servicios pueden comenzar en las
aperturas de las ventanas de todos los clientes.

Los tiempos dependen del equipo, la carga y la configuración de hilos. Una
medición preliminar con hilos predeterminados dio 2,93 s para HiGHS; por eso la
configuración de un hilo forma parte de la reproducción del criterio. Este
resultado no garantiza el umbral de dos segundos para otras instancias.

## 10. Fase 2: Reglas Modulares de Negocio

### 10.1. Composición y Activación

`models/hfvrptw_rules.mzn` incluye el núcleo y los módulos de zonas y descansos.
**`hfvrptw_core.mzn` permanece sin cambios** y sigue ejecutándose por separado.
Los módulos no contienen su propio `solve` ni cambian la función objetivo.
También se puede crear otro archivo de composición con el núcleo y únicamente
el `include` de la regla deseada.

| Módulo | Parámetro de activación | Datos o constantes |
| :--- | :--- | :--- |
| `rules/zone_restrictions.mzn` | `enable_zone_restrictions` | `zone_max_capacity[i]`, capacidad máxima del vehículo admitido en cada cliente. |
| `rules/driver_breaks.mzn` | `enable_driver_breaks` | Constantes de negocio: `break_threshold = 240` y `break_duration = 30`, en minutos. |

Los booleanos se suministran explícitamente mediante `-D` o en un `.dzn`.
`toy_rules_config.dzn` aporta los límites por zona; se necesita incluso si la
regla está apagada al usar el archivo de composición que incluye ambos módulos.
No definir un mismo parámetro en dos archivos de datos.

```sh
# Ambas apagadas: óptimo 246 en la variante de fase 2.
minizinc --solver gecode --parallel 1 models/hfvrptw_rules.mzn data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn -D 'enable_zone_restrictions=false; enable_driver_breaks=false;'

# Solo zonas: óptimo 253 y reasignación de las rutas.
minizinc --solver gecode --parallel 1 models/hfvrptw_rules.mzn data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn -D 'enable_zone_restrictions=true; enable_driver_breaks=false;'

# Solo descansos: óptimo 246, con pausa en la ruta larga.
minizinc --solver gecode --parallel 1 models/hfvrptw_rules.mzn data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn -D 'enable_zone_restrictions=false; enable_driver_breaks=true;'

# Ambas activadas: óptimo 253 y pausa en la ruta reasignada.
minizinc --solver gecode --parallel 1 models/hfvrptw_rules.mzn data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn -D 'enable_zone_restrictions=true; enable_driver_breaks=true;'
```

En el IDE, abrir `hfvrptw_rules.mzn`, seleccionar la instancia y el archivo de
configuración, y proporcionar ambos booleanos como datos adicionales o mediante
un tercer `.dzn`. Se pueden cambiar los motores igual que en la fase 1.

### 10.2. Semántica de las Reglas

**Zonas.** La capacidad del vehículo representa su tamaño: se prohíbe asignarlo
a un cliente si `capacity[k] > zone_max_capacity[i]`. La igualdad está permitida.
Un límite cero prohíbe todos los vehículos del núcleo, cuyas capacidades son
positivas. Este módulo no modela peso real, placas ni zonas de tránsito intermedio.

**Descansos.** Si el tiempo desde la salida hasta el regreso efectivo supera
240 minutos, se exige una pausa continua de 30 minutos en un cliente visitado,
inmediatamente después de su servicio. La pausa debe comenzar como máximo
240 minutos después de la salida. Se añade su duración a la precedencia del
siguiente viaje, incluido el regreso al depósito si es el último cliente.
No puede solaparse con conducción ni servicio; puede aprovechar una espera
antes de la siguiente ventana. También se permiten pausas en rutas cortas.

El tiempo de ruta incluye conducción, servicio y espera; no incluye la carga
inicial. Se modela una sola pausa por ruta, sin descansos recurrentes ni paradas
en carretera. Son convenciones de esta fase, no un modelo de normativa laboral.

`break_after[k]` identifica el cliente de la pausa, o cero si no hay pausa;
`break_start[k]` indica su inicio. Con la regla activa, `route_finish[k]` calcula
el regreso al terminar el último viaje, sin la holgura de `return_time[k]` del
núcleo. Esto evita exigir una pausa solo porque el solver elija una hora de
regreso artificialmente tardía. Con la regla apagada, `route_finish` muestra
`return_time`; no se agregan las restricciones temporales de descansos.
Los vehículos inactivos siempre tienen `break_after = 0`.

### 10.3. Instancias y Resultados Esperados

La instancia original conserva su óptimo **247** con ambas reglas apagadas o
encendidas: ningún vehículo infringe la zona y ninguna ruta requiere cuatro
horas. Para ejercitar cambios reales se añade `toy_rules_10nodes.dzn`, que
conserva los diez clientes y las matrices, cambia capacidades a `[12, 9, 16]`,
extiende el horizonte a 420 minutos y mueve la ventana del cliente 10 a
`[300,304]`. La configuración limita a 12 la capacidad admitida en el cliente 8.

| Zonas | Descansos | Óptimo | Efecto en la variante |
| :--- | :--- | ---: | :--- |
| Apagadas | Apagados | 246 | Vehículos 1, 2 y 3 atienden grupos 5–7, 1–4 y 8–10. |
| Encendidas | Apagados | 253 | Vehículos 1 y 3 intercambian grupos: el vehículo 3 ya no puede visitar el cliente 8. |
| Apagadas | Encendidos | 246 | El vehículo 3 incorpora una pausa, por ejemplo después del cliente 9. |
| Encendidas | Encendidos | 253 | El vehículo 1 atiende 8–10 e incorpora la pausa. |

Un horario factible con ambas reglas carga el vehículo 1 en `[10,18)` y atiende
los clientes 8, 9 y 10 en los minutos 30, 55 y 300. Descansa tras el servicio del
cliente 9, entre 60 y 90; luego viaja 5 minutos y espera hasta 300. Regresa en
317. La espera absorbe la pausa, por lo que activar descansos no aumenta el costo.
Los horarios y la ubicación de la pausa pueden variar entre soluciones óptimas.

### 10.4. Verificación Reproducible

```sh
sh experiments/check_phase2.sh
# macOS, si MiniZinc no está en PATH:
MINIZINC=/Applications/MiniZincIDE.app/Contents/Resources/minizinc sh experiments/check_phase2.sh
```

El verificador usa las mismas herramientas de consola que el de fase 1.
Ejecuta Gecode, HiGHS y OR-Tools CP-SAT con un hilo y hasta 60 segundos por caso.
Comprueba los óptimos de la tabla, la regresión de la instancia original y
contraejemplos que deben resultar inviables: vehículo prohibido, ruta larga
sin pausa, pausa solapada con viaje y regreso antes de completar el descanso.
También comprueba el umbral exacto de 240 minutos y un vehículo inactivo.
Una ventana incompatible con el descanso debe producir inviabilidad, sin
relajar la regla ni las ventanas del núcleo. Los casos se crean temporalmente.
Esta fase valida modularidad y factibilidad; no impone el umbral de dos segundos
a la instancia ampliada ni a sus pruebas de inviabilidad.

Validación realizada con MiniZinc 2.11.0, Gecode 6.6.0, HiGHS 1.16.0 y
OR-Tools CP-SAT 9.15: todos los casos de `check_phase2.sh` pasaron. También
volvió a pasar `check_phase1.sh`, conservando el óptimo 247 y el umbral de dos
segundos en esta ejecución. No se modificó el núcleo ni se añadió Python.

## 11. Fase 3: Pipeline Geoespacial Real

### 11.1. Instalación

Desde la raíz del repositorio, usar Python 3.12 o posterior y una instalación
independiente de MiniZinc con CP-SAT disponible:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/routing-system --help
```

La instalación editable mantiene accesible `models/hfvrptw_core.mzn` desde el
repositorio. El runner busca el ejecutable en `--minizinc`, en la variable
`MINIZINC`, en el `PATH` y finalmente en la ubicación estándar de MiniZinc IDE
para macOS. La librería `minizinc` de Python no instala los solvers.

### 11.2. Descargar, Construir y Resolver

```sh
# Primera ejecución: requiere internet para consultar Overpass/OpenStreetMap.
.venv/bin/python -m src.cli build data/raw/guatemala_zona1_15.json data/instances/guatemala_zona1_15.json

# Usa MiniZinc Python y el núcleo existente; no requiere internet.
.venv/bin/python -m src.cli solve data/instances/guatemala_zona1_15.json --solver cp-sat --time-limit 30 --output data/instances/guatemala_zona1_15.solution.json

# El runner también se puede invocar directamente.
.venv/bin/python -m src.solver.mzn_runner data/instances/guatemala_zona1_15.json --solver cp-sat --time-limit 30 --output /tmp/guatemala-solution.json
```

Tras instalar el proyecto, `routing-system build ...` y `routing-system solve ...`
son equivalentes, activando el entorno virtual o usando `.venv/bin/routing-system`.
Los comandos `solve` aceptan también `--solver gecode` o `--solver highs`; el
resultado registrado en esta fase se verificó con CP-SAT. El runner usa un hilo
y semilla cero, reporta estado, objetivo, rutas, horarios y estadísticas de
compilación/resolución. `OPTIMAL_SOLUTION` demuestra optimalidad;
`SATISFIED` con `optimal=false` indica una solución factible sin prueba de
optimalidad. Si no encuentra solución, conserva el estado, no inventa rutas y
el comando termina con código 2.

La misma orden `build` reutiliza el GraphML existente sin llamadas de red.
`--refresh` vuelve a descargar, y `--cache-dir` cambia la carpeta de caché.
La clave de caché depende del bbox, tipo de red y configuración de estimación.
Los GraphML y respuestas de Overpass se guardan en `data/cache/`, excluido de
Git salvo `.gitkeep`. Conviene conservar el GraphML si se desea reconstruir
exactamente la misma instancia: OSM puede cambiar entre descargas.

### 11.3. Contratos y Cálculo de Matrices

- `osm_extractor.py` descarga una red dirigida `drive` con OSMnx, conserva sus
  sentidos de circulación, agrega velocidades y tiempos por arco y la guarda
  atómicamente en GraphML. No convierte la red en un grafo no dirigido.
- El archivo de entrada contiene `network_bbox` en orden **oeste, sur, este,
  norte**, coordenadas WGS84 `lat`/`lon`, la flota y los datos operativos. El
  primer elemento de `nodes` es el depósito; los siguientes son los clientes.
  `data/raw/guatemala_zona1_15.json` sirve como ejemplo completo del formato.
- `matrix_builder.py` asigna cada coordenada al nodo vial más cercano. Rechaza
  puntos a más de 250 metros de la red por defecto, configurable con
  `--max-snap-distance`. Rechaza demandas negativas, ventanas inválidas,
  capacidades insuficientes y arcos sin pesos válidos.
- Para cada origen ejecuta Dijkstra ponderado por `travel_time` en segundos.
  Calcula cada destino de forma dirigida; nunca copia el triángulo opuesto.
  Si un destino es inaccesible, falla indicando el par; se debe revisar la
  coordenada o ampliar el bbox, sin reemplazarlo por distancia en línea recta.
- La matriz `distance` usa metros enteros redondeados hacia arriba **sobre el
  mismo camino de menor tiempo**, incluyendo la selección de arcos paralelos.
  No mezcla distancia mínima de un camino con tiempo mínimo de otro.
  `travel_time` convierte segundos a minutos redondeando hacia arriba por par
  origen–destino. Los clientes que compartan nodo vial pueden tener costo y
  tiempo cero entre sí; cada cliente conserva su demanda y servicio.
- El JSON del modelo contiene únicamente sus parámetros, matrices rectangulares
  y vectores. MiniZinc recibe el archivo directamente y aplica sus índices
  declarados: depósito 0, clientes 1–15. No se modificó el núcleo matemático.

El tiempo vial es una **estimación de flujo libre**, calculada a partir de
`maxspeed` de OSM e imputación de OSMnx por tipo de vía, con 30 km/h como último
valor de respaldo. No son mediciones de tráfico en vivo. El snapping aproxima
el acceso a la calle: no suma el trayecto entre la coordenada y el nodo vial.
Tampoco se incorporan demoras en cruces, restricciones de giro ni restricciones
específicas de camiones. La [referencia oficial de OSMnx](https://osmnx.readthedocs.io/en/stable/user-reference.html)
describe estas funciones de velocidades, tiempos y nodos cercanos; la
[API de MiniZinc Python](https://python.minizinc.dev/en/latest/api.html) describe
la carga de JSON y la ejecución mediante `Model` e `Instance`.

### 11.4. Artefactos y Resultado Verificado

| Archivo | Contenido |
| :--- | :--- |
| `data/raw/guatemala_zona1_15.json` | Depósito y 15 coordenadas propuestas en zona 1, dos muelles y tres vehículos. Demandas, flota y ventanas sintéticas; no representa pedidos de comercios reales. |
| `data/instances/guatemala_zona1_15.json` | Instancia MiniZinc de 16 nodos, con matrices viales reales y datos operativos de prueba. Se puede resolver sin red ni GraphML. |
| `data/instances/guatemala_zona1_15.geo.json` | Coordenadas originales y ajustadas, ids OSM, errores de snapping, consulta, fecha, unidades, atribución y SHA-256 de entrada, instancia y caché. |
| `data/instances/guatemala_zona1_15.solution.json` | Solución obtenida mediante MiniZinc Python, con estado, estadísticas y SHA-256 del archivo de instancia. |

Los archivos `.geo.json` y `.solution.json` son metadatos y resultados; no se
pasan como datos al núcleo. La red se descargó el **19 de noviembre de 2026**:
660 nodos, 1.340 arcos dirigidos, 16 nodos viales distintos para las coordenadas
y una distancia máxima de snapping de 76,44 m. Hay 116 pares no ordenados con
distancia asimétrica y 41 con tiempo asimétrico después del redondeo a minutos.

La validación en macOS ARM64 con Python 3.12, OSMnx 2.2.0, NetworkX 3.7,
MiniZinc Python 0.10.0, MiniZinc 2.11.0 y CP-SAT 9.15 encontró
**`OPTIMAL_SOLUTION`, objetivo 16.022**, en 2,65 segundos medidos por el runner
(incluyendo compilación y resolución, excluyendo descarga y construcción de
matrices). El límite configurado fue de 30 segundos. El vehículo 1 queda
inactivo; los vehículos 2 y 3 transportan 7 y 8 unidades:

- Vehículo 2: `0 → 1 → 2 → 3 → 7 → 6 → 5 → 4 → 0`.
- Vehículo 3: `0 → 8 → 9 → 11 → 10 → 13 → 15 → 14 → 12 → 0`.

El costo usa las unidades abstractas declaradas en el ejemplo y tarifas por
metro; no representa quetzales ni una cotización logística. Los tiempos de
proceso dependen del equipo y del estado de OSM al regenerar los datos.

Fuente de la red: **© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)**,
[Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).
La atribución y procedencia también se conservan en el GraphML y el `.geo.json`.

### 11.5. Pruebas

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Las pruebas funcionan sin red y comprueban caminos dirigidos y arcos paralelos,
coherencia entre distancia y tiempo, caché GraphML y actualización explícita,
coordenadas alejadas, nodos inaccesibles, validación de datos y serialización.
También ejecutan MiniZinc Python sobre un grafo pequeño con óptimo conocido y
una instancia inviable; estas dos pruebas se omiten si MiniZinc no está instalado
en el PATH o su ubicación estándar de macOS. Una comprobación independiente
verifica la solución real guardada: cobertura de los 15 clientes, capacidades,
ventanas, tiempos de recorrido, ocupación de muelles, costo y hashes de la
instancia. La descarga real y la reconstrucción posterior desde caché se
verificaron durante la implementación.

## 12. Fase 4: Visualización Operativa con Folium

### 12.1. Generar y Abrir el Mapa

Desde la raíz del repositorio y con las dependencias de la sección 11 instaladas:

```sh
.venv/bin/python -m src.cli render data/instances/guatemala_zona1_15.json data/instances/guatemala_zona1_15.solution.json data/maps/guatemala_zona1_15.html --start-time 08:00

# macOS: abrir el HTML en el navegador predeterminado.
open data/maps/guatemala_zona1_15.html
```

También se puede usar `.venv/bin/routing-system render ...`. El renderer utiliza
por defecto `instance.geo.json` y el GraphML indicado en sus metadatos. Las
opciones `--geo` y `--graph` permiten indicar esas rutas explícitamente.
`--start-time` establece la hora equivalente al minuto cero del modelo: 08:00
es una convención visual configurable, no una hora tomada de OpenStreetMap.

El HTML generado incluye las calles del grafo original como fondo y no solicita
teselas externas. Folium carga Leaflet y sus librerías de presentación desde CDN:
la primera apertura necesita acceso a esos recursos; no es un paquete totalmente
autocontenido para uso sin conexión. La generación desde GraphML no consulta
OpenStreetMap, no ejecuta de nuevo el solver ni requiere red.

Para generar un mapa nuevo se necesita conservar el **GraphML original**. Si
la caché no está disponible, se debe reconstruir el pipeline de fase 3 y volver
a resolver la nueva instancia. No se sustituye silenciosamente la red por una
descarga actual que podría tener otras calles o sentidos. El HTML ya generado
no necesita los archivos JSON ni GraphML para abrirse.

### 12.2. Lectura de la Vista Operativa

- Cada vehículo activo tiene su color y una capa independiente, activable en
  el control superior derecho. Los inactivos se identifican en el panel.
- Las líneas siguen la geometría de las calles, no segmentos rectos entre
  clientes. Las flechas indican el sentido de recorrido de cada arco dirigido.
  Al pasar por una flecha se consulta la calle, el sentido y los extremos OSM;
  las calles de fondo también muestran nombre y sentido al pasar el cursor.
- Los marcadores `V2·1`, `V2·2`, etc. indican vehículo y orden de visita. Un clic
  muestra llegada estimada, inicio de servicio, ventana y espera. El panel
  conserva esa información por vehículo, junto con carga, distancia, salida y
  regreso estimado. Se puede hacer zoom y desplazar el mapa.
- La llegada estimada se calcula viajando inmediatamente después de terminar
  el servicio anterior, usando los minutos redondeados de la instancia. El
  vehículo puede llegar **antes** de la apertura y esperar: la condición del
  modelo es iniciar el servicio dentro de la ventana. Las dos horas se muestran
  por separado para no confundir llegada temprana con incumplimiento.
- En el depósito, el diagrama muestra los intervalos `[inicio de carga, salida)`
  con colores de vehículo y el pico de ocupación. `cumulative` no decide ids de
  muelle: el renderer asigna los intervalos a muelles disponibles de forma
  compatible con el plan. No atribuye al solver una asignación que no produjo.

El regreso mostrado en el resumen es la llegada estimada al terminar el último
viaje. Puede ser anterior a `return_time`, que en el núcleo admite holgura.
La vista corresponde al núcleo de fase 3; no reconstruye descansos de módulos
adicionales ni incorpora tráfico en vivo, cruces o tiempos de acceso desde el
punto original hasta el nodo vial ajustado.

### 12.3. Reconstrucción y Comprobaciones

`src/solver/routes.py` convierte los sucesores en rutas y se reutiliza tanto en
el runner como en el renderer. Este último vuelve a leer `successor`, sin fiarse
del campo redundante `routes`: exige regreso al depósito, cobertura única y
bucles propios en los nodos excluidos de cada vehículo.

`src/viz/map_renderer.py` ejecuta el mismo Dijkstra por origen y la misma
selección de arcos paralelos que `matrix_builder.py`, sobre el GraphML original.
Para cada tramo recupera la geometría completa y la orienta desde el origen
hacia el destino. Comprueba que metros y minutos coincidan con la matriz.
Antes de dibujar valida los SHA-256 de instancia, solución y grafo, cobertura,
capacidad, precedencias, ventanas, carga, regreso, ocupación de muelles y costo.
Un archivo desactualizado o un plan inválido produce un error; no se dibuja
como si estuviera verificado.

El mapa de ejemplo conserva el óptimo 16.022 y muestra **15/15 servicios dentro
de ventana**, dos vehículos activos y ocupación máxima **2/2**:

| Vehículo | Carga | Distancia | Carga en depósito | Regreso estimado |
| :--- | ---: | ---: | :--- | :--- |
| 1 | Inactivo | — | — | — |
| 2 | 7/7 | 3,681 km | 08:00–08:07, muelle visual M1 | 09:00 |
| 3 | 8/8 | 5,960 km | 08:00–08:09, muelle visual M2 | 10:03 |

### 12.4. Validación

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Las 16 pruebas de fases 3 y 4 incluyen geometría de calle almacenada al revés,
selección del arco paralelo más rápido, sucesores inválidos, espera antes del
servicio, regreso imposible, exceso de muelles, liberación y reutilización de
un muelle en el mismo minuto, integridad de archivos y etiquetas HTML seguras.
El HTML del ejemplo se abrió y se inspeccionó en Firefox en vistas de escritorio
y móvil. El núcleo MiniZinc no cambió y el runner conserva su comportamiento.

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
(fase 2). Los `.gitkeep` conservan las carpetas reservadas.
La capa Python, los perfiles, la cadena de frío, las dependencias y el
contenedor siguen pendientes. La sección 9 describe la ejecución disponible.

```text
routing-system/
├── README.md
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
│   ├── geo/
│   │   └── .gitkeep
│   ├── decomposition/
│   │   └── .gitkeep
│   ├── solver/
│   │   └── .gitkeep
│   └── viz/
│       └── .gitkeep
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── cache/
│   │   └── .gitkeep
│   └── instances/
│       ├── toy_10nodes.dzn
│       ├── toy_rules_10nodes.dzn
│       ├── toy_rules_config.dzn
│       └── .gitkeep
└── experiments/
    ├── check_phase1.sh
    ├── check_phase2.sh
    └── .gitkeep
```

### 8.1. Archivos y Responsabilidades

`models/hfvrptw_core.mzn`, `models/rules/zone_restrictions.mzn` y
`models/rules/driver_breaks.mzn` ya están implementados; los demás archivos
de esta tabla corresponden a fases posteriores.

| Ruta prevista | Responsabilidad |
| :--- | :--- |
| `pyproject.toml` | Declarar las dependencias de Python: minizinc, osmnx, networkx y folium. |
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

### 8.3. Guía de Uso

En esta etapa se ejecuta directamente MiniZinc como se indica en la sección 9;
la aplicación Python sigue pendiente. Al implementar cada componente,
su código se ubicará en la ruta prevista de la tabla y se podrá retirar el
`.gitkeep` de esa carpeta cuando contenga archivos versionados.

El flujo de uso previsto es:

1. Preparar pedidos, ventanas y flota en `data/raw/`.
2. Descargar o reutilizar la red vial de `data/cache/` y construir las matrices.
3. Exportar una instancia a `data/instances/`.
4. Ejecutar el modelo central con las reglas y el perfil de solver seleccionados.
5. Visualizar las rutas con Folium y comparar las métricas mediante `experiments/`.

Los comandos de instalación, ejecución de la CLI y construcción del contenedor
se documentarán cuando existan `pyproject.toml`, `src/cli.py` y `Dockerfile`.

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

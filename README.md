# Optimización Logística mediante Programación por Restricciones (HFVRPTW-C)

Repositorio: [oscarligo/routing-system](https://github.com/oscarligo/routing-system).
Código fuente: [modelos MiniZinc](https://github.com/oscarligo/routing-system/tree/main/models),
[instancias de datos](https://github.com/oscarligo/routing-system/tree/main/data/instances) y
[pipeline Python](https://github.com/oscarligo/routing-system/tree/main/src).

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

## 4. Objetivos del Proyecto

### 4.1. Objetivo General

Diseñar, formular e implementar un modelo de optimización declarativo en MiniZinc integrado con Python para resolver el problema HFVRPTW-C, evaluando la agilidad declarativa de la herramienta y comparando cuantitativamente el desempeño de compilación a FlatZinc y resolución bajo motores CP, MIP y SAT/CP Híbrido.

### 4.2. Objetivos Específicos

1. **Formulación y Restricciones Globales:** formular de forma matemática rigurosa las restricciones de ruteo, heterogeneidad de flota, ventanas de tiempo y capacidad en depósito aprovechando las restricciones globales `alldifferent` y `cumulative`.
2. **Evaluación Multiparadigma (*Model Once, Solve Anywhere*):** comparar el rendimiento (tiempo de respuesta, calidad del valor objetivo y brecha de optimalidad) entre los solvers Gecode (CP), HiGHS (MIP) y OR-Tools CP-SAT ante instancias de escala pequeña, mediana y grande.
3. **Análisis del Proceso de *Flattening*:** analizar la transformación del modelo `.mzn` a `.fzn`, evaluando la explosión combinatoria del número de variables y restricciones generadas al escalar el tamaño de la red de clientes.
4. **Agilidad Declarativa ante Reglas Dinámicas:** demostrar la flexibilidad del paradigma agregando y removiendo restricciones de negocio secundarias (ej. restricciones de incompatibilidad de carga o ventanas de descanso) sin alterar la arquitectura algorítmica ni el código en Python.
5. **Capa de Visualización e Interfaz:** desarrollar un módulo en Python que automatice el flujo de datos, ejecute las pruebas experimentales y genere diagramas de Gantt (para uso de muelles) y mapas interactivos de las rutas óptimas resultantes.

---

## 5. Plan de Experimentación y Evaluación de Escalabilidad

Las pruebas experimentales se realizarán sobre un conjunto de instancias adaptadas de la literatura estándar (Solomon / VRPTW adaptadas a flota heterogénea y muelles), clasificadas en tres niveles:

| Escenario | Clientes ($N$) | Flota ($K$) | Muelles ($M_{\text{muelles}}$) | Propósito del Experimento |
| :--- | :--- | :--- | :--- | :--- |
| **Pequeno** | $10 - 20$ | $3 - 5$ | $2$ | Validación de exactitud matemática y prueba de optimalidad global. |
| **Mediano** | $25 - 50$ | $6 - 10$ | $3$ | Comparación de velocidad de propagador vs. relajación lineal (CP vs. MIP). |
| **Grande** | $100+$ | $15+$ | $4 - 5$ | Evaluación del límite de escalabilidad, flattening time y rendimiento de CP-SAT. |

---

## 6. Resultados Esperados

- Modelo declarativo en MiniZinc altamente legible, modular y mantenible.
- Estudio comparativo detallado que identifique qué paradigma (CP, MIP o SAT) responde mejor al problema HFVRPTW-C según el tamaño de la instancia.
- Demostración práctica de cómo la restricción `cumulative` modela con exactitud y eficiencia los cuellos de botella en depósitos logísticos.
- Cuadro comparativo del impacto del *flattening* (tiempo de traducción y tamaño del archivo `.fzn`).

---

## 7. MiniZinc: Modelo, Ejecución y Salidas

### 7.1. El Rol de FlatZinc y la Portabilidad entre Solvers

MiniZinc compila el modelo abstracto `.mzn` junto con los datos `.dzn` a una representación intermedia de bajo nivel denominada **FlatZinc (`.fzn`)**. Esta arquitectura permite ejecutar el **mismo modelo matemático** en distintos motores de búsqueda sin modificar el código:

- **Gecode (CP):** motor clásico de Programación por Restricciones especializado en propagación e inferencia sobre dominios finitos.

- **HiGHS (MIP):** motor de Programación Entera Mixta para evaluar linealización y relajaciones continuas.

- **OR-Tools CP-SAT (Híbrido):** Solver de vanguardia basado en tecnología SAT y propagación de restricciones.

### 7.2. Ejecución Independiente y Lectura de Salidas

Estos ejemplos requieren **MiniZinc y el solver Gecode instalado**. No requieren
Python, el entorno virtual, acceso a OpenStreetMap ni los archivos del pipeline
geoespacial. `subcircuit.mzn` y `cumulative.mzn` pertenecen a la biblioteca
estándar de MiniZinc y no deben copiarse desde este repositorio.

#### Archivos exactos requeridos

Para ejecutar **solo el núcleo sintético**, bastan estos dos archivos:

```text
models/hfvrptw_core.mzn
data/instances/toy_10nodes.dzn
```

Para ejecutar **el modelo con zonas y descansos**, se requieren estos seis
archivos, conservando las rutas relativas entre los `.mzn`:

```text
models/hfvrptw_rules.mzn
models/hfvrptw_core.mzn
models/rules/zone_restrictions.mzn
models/rules/driver_breaks.mzn
data/instances/toy_rules_10nodes.dzn
data/instances/toy_rules_config.dzn
```

`hfvrptw_rules.mzn` incluye el núcleo y ambos módulos. Los módulos de reglas
no se ejecutan por separado. `toy_rules_config.dzn` define los límites por zona
y se requiere incluso si se desactiva esa regla. Los dos booleanos de activación
se proporcionan con `-D` en el comando; no están definidos en esos datos.
No hay que agregar `toy_10nodes.dzn` al caso con reglas, pues duplicaría parámetros.

Los archivos originales están disponibles en el repositorio:

- [Núcleo: hfvrptw_core.mzn](models/hfvrptw_core.mzn).
- [Composición: hfvrptw_rules.mzn](models/hfvrptw_rules.mzn).
- [Regla de zonas: zone_restrictions.mzn](models/rules/zone_restrictions.mzn).
- [Regla de descansos: driver_breaks.mzn](models/rules/driver_breaks.mzn).
- [Instancia del núcleo: toy_10nodes.dzn](data/instances/toy_10nodes.dzn).
- [Instancia con reglas: toy_rules_10nodes.dzn](data/instances/toy_rules_10nodes.dzn).
- [Configuración: toy_rules_config.dzn](data/instances/toy_rules_config.dzn).

#### Ejecutar el núcleo y consultar su salida

Desde la raíz del repositorio:

```sh
minizinc --solver gecode --parallel 1 models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn
```

Si MiniZinc IDE está instalado en macOS pero `minizinc` no está en el `PATH`,
se puede reemplazar el ejecutable por
`/Applications/MiniZincIDE.app/Contents/Resources/minizinc`.
En el IDE, abrir el modelo y el archivo de datos, seleccionar Gecode y ejecutar
el modelo con ese `.dzn`.

Ejemplo de salida obtenido con Gecode:

```text
total_cost = 247;
successor (rows = vehicles, columns = depot 0 then customers) = [1, 2, 3, 4, 0, 5, 6, 7, 8, 9, 10, 5, 1, 2, 3, 4, 6, 7, 0, 8, 9, 10, 8, 1, 2, 3, 4, 5, 6, 7, 9, 10, 0];
used = [true, true, true];
start_service = [20, 35, 50, 65, 22, 42, 62, 30, 55, 80];
loading_start = [0, 0, 8];
departure = [8, 10, 20];
return_time = [80, 77, 97];
----------
==========
```

El depósito es el nodo `0` y esta instancia contiene diez clientes (`1..10`).
Los campos se interpretan así:

| Campo | Significado |
| :--- | :--- |
| `total_cost` | Costo fijo de los vehículos activos más costo de distancia por vehículo. |
| `successor` | Matriz impresa como lista por filas: una fila por vehículo y una columna por nodo, comenzando en el depósito. Cada valor indica el siguiente nodo. |
| `used` | Indica qué vehículos están activos, en orden `1..n_vehicles`. |
| `start_service` | Minuto de inicio del servicio de cada cliente, en orden `1..n_customers`; no incluye el depósito. |
| `loading_start` | Minuto de inicio de carga por vehículo. |
| `departure` | Minuto de salida del depósito por vehículo, al finalizar la carga. |
| `return_time` | Minuto factible de regreso por vehículo; puede incluir holgura porque el objetivo no minimiza horarios. |

En este ejemplo, `successor` se divide en tres filas de once valores. Para
reconstruir cada ruta, comenzar en la columna `0` y seguir los sucesores hasta
volver a `0`. Un nodo cuyo sucesor es él mismo no pertenece a esa ruta:

- Vehículo 1: `0 → 1 → 2 → 3 → 4 → 0`.
- Vehículo 2: `0 → 5 → 6 → 7 → 0`.
- Vehículo 3: `0 → 8 → 9 → 10 → 0`.

Los tiempos son minutos desde la apertura; las distancias y costos son unidades
sintéticas. El intervalo de carga es `[loading_start, departure)`: los vehículos
1 y 2 cargan desde el minuto cero, y el vehículo 3 utiliza el muelle liberado
por el vehículo 1 en el minuto 8.

#### Ejecutar con zonas y descansos

Desde la raíz del repositorio, activar ambas reglas:

```sh
minizinc --solver gecode --parallel 1 models/hfvrptw_rules.mzn data/instances/toy_rules_10nodes.dzn data/instances/toy_rules_config.dzn -D 'enable_zone_restrictions=true; enable_driver_breaks=true;'
```

Cambiar cada booleano a `false` permite desactivar su regla. En el IDE,
seleccionar los dos `.dzn` y proporcionar ambos booleanos como datos adicionales;
si se prefiere un archivo, crear un tercer `.dzn` con esas dos asignaciones y
seleccionarlo junto con los otros dos.

Además de los campos del núcleo, esta ejecución imprime los siguientes campos.
Extracto de la salida obtenida con ambas reglas activadas:

```text
total_cost = 253;
break_after = [9, 0, 0];
break_start = [60, 0, 0];
route_finish = [317, 77, 80];
----------
==========
```

`break_after` identifica el cliente después del cual descansa cada vehículo;
`0` significa que no hay pausa. `break_start` indica su minuto de inicio. En el
extracto, el vehículo 1 descansa después del cliente 9, desde el minuto 60
hasta el 90. Con descansos activos, `route_finish` calcula el regreso al terminar
el último viaje, incluyendo la pausa si corresponde; con la regla apagada
coincide con `return_time`.

#### Reconocer el estado y guardar resultados

`----------` separa soluciones y `==========` confirma que se demostró el
óptimo. Pueden aparecer varias soluciones de costo decreciente; debe consultarse
la última. Los horarios pueden variar entre ejecuciones o solvers aun cuando
el costo óptimo sea el mismo. `=====UNSATISFIABLE=====` indica que no existe
solución factible y `=====UNKNOWN=====` que no se pudo determinar el resultado.
Si se alcanza un límite de tiempo después de encontrar una solución, su costo
no debe considerarse óptimo sin el marcador de optimalidad.

Para guardar la salida textual y añadir estadísticas:

```sh
minizinc --solver gecode --parallel 1 --statistics models/hfvrptw_core.mzn data/instances/toy_10nodes.dzn > /tmp/toy_10nodes.out
```

La salida directa es texto: no genera por sí sola los archivos `.solution.json`,
los mapas HTML ni los metadatos geográficos del pipeline Python.

## 8. Interpretación de los Resultados de MiniZinc

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
capacidades y ventanas. El caso geoespacial de la sección 9 utiliza otras matrices y escalas de
distancia, por lo que tampoco admite una comparación directa de costos.

## 9. Integración y Resultados con Python

### 9.1. Arquitectura del Pipeline

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

### 9.2. Guía de Uso del Pipeline

Se puede ejecutar MiniZinc directamente sobre los modelos y datos sintéticos,
o usar el pipeline Python mediante `src/cli.py`. El flujo geoespacial es:

1. Preparar coordenadas, demandas, ventanas y flota en `data/raw/`.
2. Ejecutar `build` para descargar o reutilizar la red vial y exportar las matrices y metadatos a `data/instances/`.
3. Ejecutar `solve` para resolver la instancia con el motor seleccionado y guardar la solución.
4. Ejecutar `render` para generar el mapa en `data/maps/` usando la solución y el grafo original.

Las opciones se consultan con `python -m src.cli --help` y con `--help` en cada
subcomando. Los scripts de `experiments/` verifican los casos sintéticos con y
sin reglas adicionales.

### 9.3. Calidad de la Solución y Uso de la Flota

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

### 9.4. Cumplimiento Horario y Capacidad del Depósito

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

### 9.5. Rendimiento y Alcance de las Conclusiones

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

---

## 10. Estructura del Repositorio

El repositorio contiene el núcleo MiniZinc, reglas modulares de zonas y
descansos, el pipeline geoespacial Python + OpenStreetMap y la visualización
operativa con Folium. El siguiente árbol refleja los archivos actuales; omite
el entorno virtual, los archivos temporales y las cachés generadas.

```text
routing-system/
├── README.md
├── .gitignore
├── pyproject.toml
├── models/
│   ├── hfvrptw_core.mzn
│   ├── hfvrptw_rules.mzn
│   └── rules/
│       ├── zone_restrictions.mzn
│       └── driver_breaks.mzn
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── osm_extractor.py
│   │   └── matrix_builder.py
│   ├── solver/
│   │   ├── __init__.py
│   │   ├── mzn_runner.py
│   │   └── routes.py
│   └── viz/
│       ├── __init__.py
│       └── map_renderer.py
├── data/
│   ├── raw/
│   │   └── guatemala_zona1_15.json
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
│       └── toy_rules_config.dzn
├── experiments/
│   ├── check_phase1.sh
│   └── check_phase2.sh
└── tests/
    ├── test_geospatial.py
    └── test_map_renderer.py
```

### 10.1. Archivos y Responsabilidades

| Ruta | Responsabilidad |
| :--- | :--- |
| `models/hfvrptw_core.mzn` | Rutas con `subcircuit`, capacidad de muelles con `cumulative`, capacidades de vehículos y ventanas de tiempo. |
| `models/hfvrptw_rules.mzn` | Componer el núcleo con las reglas opcionales de zonas y descansos. |
| `models/rules/zone_restrictions.mzn` | Restringir la asignación de vehículos según la capacidad máxima permitida por zona. |
| `models/rules/driver_breaks.mzn` | Incorporar pausas de conductores y su efecto en los horarios de ruta. |
| `pyproject.toml` | Dependencias de Python, configuración del paquete y comando `routing-system`. |
| `src/cli.py` | Comandos `build`, `solve` y `render` para construir instancias, resolverlas y generar mapas. |
| `src/geo/osm_extractor.py` | Descargar y almacenar en caché la red vial dirigida de OpenStreetMap. |
| `src/geo/matrix_builder.py` | Construir matrices asimétricas y exportar la instancia y sus metadatos geográficos. |
| `src/solver/mzn_runner.py` | Ejecutar MiniZinc y extraer soluciones, rutas y estadísticas de compilación y resolución. |
| `src/solver/routes.py` | Reconstruir y validar las rutas a partir de los sucesores del modelo. |
| `src/viz/map_renderer.py` | Validar la solución y representar rutas, horarios y ocupación de muelles en HTML con Folium. |
| `experiments/check_phase1.sh` | Verificar el núcleo sintético con Gecode, HiGHS y CP-SAT. |
| `experiments/check_phase2.sh` | Verificar las reglas de zonas y descansos y su compatibilidad con el núcleo. |
| `tests/test_geospatial.py` | Probar matrices viales, caché, validación de datos e integración con MiniZinc. |
| `tests/test_map_renderer.py` | Probar la reconstrucción de calles, validación de soluciones y generación del mapa. |

### 10.2. Organización de Datos

| Directorio | Contenido |
| :--- | :--- |
| `data/raw/` | Coordenadas, demandas, ventanas horarias y definición de la flota de entrada. |
| `data/cache/` | Grafos `.graphml` y respuestas de Overpass generados localmente, excluidos de Git salvo `.gitkeep`. |
| `data/instances/` | Instancias `.json` o `.dzn`, metadatos geográficos `.geo.json` y resultados `.solution.json`. |
| `data/maps/` | Mapas HTML operativos con calles, rutas y horarios. |

La caché conserva el grafo original necesario para regenerar el mapa de una
solución existente. El pipeline crea sus subdirectorios cuando los necesita.

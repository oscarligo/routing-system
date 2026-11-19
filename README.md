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
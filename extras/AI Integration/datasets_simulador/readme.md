# Ensayos completos del simulador

Aquí va una carpeta por cada ensayo del simulador, tal como la genera el simulador
(por ejemplo `decoupling_w2_150s/`). De cada ensayo, los scripts usan `config.json`,
`coord/rx_crd.csv`, `coord/uwb_crd.csv` y `coord/imu_crd.csv`.

El contenido de esta carpeta **no se sube a Git** (pesa mucho): solo este archivo.
Para procesar un ensayo, añádelo a `datasets_procesados/simulador/ensayos_simulador.json`
(ver `guia_exportacion.md`). Cómo generar un ensayo está en el repositorio del simulador
(`Simulador-CARLA`, `docs/guia_simulador.md`).

Solo se acepta el formato actual del simulador, con medidas al hijo y al nieto. Los ensayos del formato
antiguo (`rx_coord.csv`, `wagon_0/`…, distancias a la locomotora) se rechazan: hay que repetirlos.


## Estructura de los datasets

Cada ejecución genera una carpeta con la siguiente estructura. Cada vehículo tiene un solo nombre
(`crd` para la locomotora y `w1`…`w4` para los vagones), el mismo en carpetas, archivos e identificadores:

```
<ensayo>/
├── config.json              # Parámetros exactos usados en la simulación (incluye "test" -> "node_unresponsive")
├── coord/                   # Datos del nodo coordinador (locomotora)
│   ├── tx_crd.csv           # Mensajes enviados por la locomotora
│   ├── rx_crd.csv           # Mensajes recibidos por la locomotora (uno por vagón y ciclo)
│   ├── uwb_crd.csv          # Medidas UWB de la locomotora a w1 (hijo) y w2 (nieto)
│   ├── imu_crd.csv          # IMU de la locomotora
│   └── gnss_crd.csv         # Medidas GNSS de la locomotora
├── w1/                      # Datos del nodo del vagón w1
│   ├── imu_w1.csv           # Medidas IMU
│   ├── tx_w1.csv            # Mensajes enviados
│   ├── rx_w1.csv            # Mensajes recibidos
│   ├── gnss_w1.csv          # Medidas GNSS
│   └── uwb_w1.csv           # Medidas UWB a su hijo y a su nieto
├── w2/ ... w4/              # Idem para el resto de vagones
└── ltd_log/
    ├── dyn.csv              # Estado dinámico completo (s, v, a, jerk, fuerzas)
    └── couplers.csv         # Fuerzas de acoplamiento entre vagones (Coupler_k_k+1)
```

### Medidas UWB: hijo y nieto

Como en las placas, cada vehículo mide su distancia a los dos vehículos que lleva detrás: su **hijo** y su
**nieto**. Son fijos por posición, también cuando un nodo no responde. Cada pareja tiene su propio ruido y su
propio NLOS.

| Pareja del formato en crudo | Quién la mide | Columna | Archivo |
|---|---|---|---|
| `c_w1` | locomotora | `uwb_son` | `coord/uwb_crd.csv` |
| `c_w2` (dos saltos) | locomotora | `uwb_grandson` | `coord/uwb_crd.csv` |
| `w1_w2`, `w1_w3` | w1 | `uwb_son`, `uwb_grandson` | `coord/rx_crd.csv` |
| `w2_w3`, `w2_w4` | w2 | `uwb_son`, `uwb_grandson` | `coord/rx_crd.csv` |
| `w3_w4` | w3 | `uwb_son` (`uwb_grandson` vacía) | `coord/rx_crd.csv` |
| — | w4 (último vagón) | las dos vacías | — |

Las medidas de la locomotora no viajan en ningún mensaje: las toma el propio coordinador, y por eso están en
su archivo local.

### Evento de red `node_unresponsive`

Un vagón puede dejar de responder durante uno o varios episodios (`config.json` → `"test"` →
`"node_unresponsive"`, lista de `{"wagon": "w2", "t_start_s": …, "t_end_s": …}`). Durante el episodio su
mensaje no llega a `rx_crd.csv`, él no mide a nadie y quedan vacías las distancias que le miden su padre y
su abuelo. Con el tren íntegro, esos ciclos se etiquetan como OK.

### Formato de los ficheros CSV principales

**`dyn.csv`**: un registro por tick de simulación, por vehículo:

| Campo | Descripción |
|-------|-------------|
| `timestamp` | Tiempo de simulación (s) |
| `id` | Identificador (`crd` = locomotora, `w1`…`w4` = vagones) |
| `s` | Posición en el arco de vía (m) |
| `v` | Velocidad longitudinal (m/s) |
| `a` | Aceleración longitudinal (m/s²) |
| `jerk` | Derivada de la aceleración (m/s³) |
| `F_trac` | Fuerza de tracción (N) |
| `F_brake` | Fuerza de freno (N) |
| `F_coupler` | Fuerza neta de acoplamiento (N) |
| `F_res` | Resistencias totales (Davis + pendiente + curva) (N) |

**`imu_<id>.csv`**: medidas de la IMU sintética:

| Campo | Descripción |
|-------|-------------|
| `frame` | Frame de CARLA (el mismo contador que `tick` en los mensajes) |
| `timestamp` | Tiempo de simulación (s) |
| `ax_meas` / `ay_meas` / `az_meas` | Aceleración medida (m/s²) |
| `gx_meas` / `gy_meas` / `gz_meas` | Velocidad angular medida (rad/s) |

**`uwb_crd.csv`**: medidas UWB de la locomotora, una fila cada 50 frames (0,25 s):

| Campo | Descripción |
|-------|-------------|
| `frame` | Frame de CARLA (mismo contador que `tick` de `rx_crd.csv` y `frame` de `imu_crd.csv`) |
| `timestamp` | Tiempo de simulación (s) |
| `uwb_son` / `d_true_son` | Distancia medida y real a w1 (m); vacía si w1 no responde |
| `uwb_grandson` / `d_true_grandson` | Distancia medida y real a w2 (m); vacía si w2 no responde |

**`uwb_<wK>.csv`**: medidas UWB de cada vagón: `uwb_son`, `d_true_son`, `uwb_grandson`, `d_true_grandson`.

**`tx_<id>.csv`** / **`rx_<id>.csv`**: mensajes V2X enviados/recibidos:

| Campo | Descripción |
|-------|-------------|
| `source_id` / `dest_id` | Identificadores origen y destino (`crd`, `w1`…`w4`) |
| `msg_type` | Tipo de mensaje (`data` o `ACK`) |
| `seq` | Número de secuencia |
| `timestamp` | Tiempo de simulación al envío (s) |
| `ax`..`gz` | Datos IMU incluidos en el mensaje |
| `lat`, `lon`, `alt` | Datos GNSS incluidos en el mensaje |
| `uwb_son`, `uwb_grandson` | Distancias del emisor a su hijo y a su nieto (vacías si no tiene o no responde) |

---

## Datasets disponibles

> Los ensayos de esta lista son del formato antiguo y hay que repetirlos con el simulador actual.

Los datasets de la carpeta `Datasets/` siguen la convención de nombres `<fecha>_<índice>` o nombres descriptivos para sesiones especiales:

| Nombre | Descripción aproximada |
|--------|----------------------|
| Datasets_def/brake_300s | Simulación de frenado a los 300s  |
| Datasets_def/decoupling_w2_150s | Simulación con fallo instantáneo del acople 2 a los 150 s |
| Datasets_def/decoupling_prefail30s_t100s | Simulación con pre-fallo de acople a los 100 s (antes de llegar a la velocidad nominal)|


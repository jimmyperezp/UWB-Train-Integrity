# Registro de cambios del TFM

Registro de trabajo del TFM sobre este repositorio: qué se ha cambiado, por qué y cómo se ha comprobado. Sirve de base para redactar la memoria en Overleaf.

- **Este fichero:** el porqué de cada cambio, la verificación y el capítulo de la memoria al que afecta.
- **Readmes de cada ejemplo:** qué hace el código y cómo se usa (en inglés).
- **`releases.md`:** versiones publicadas de la librería.

### Cómo se actualiza

- Cada bloque de trabajo terminado añade una entrada al principio del **Registro**, con fecha, rama y commits.
- Cada entrada sigue la misma plantilla: **Qué**, **Por qué**, **Verificación**, **Commits** y **Memoria** (capítulo afectado).
- El **Estado actual** se reescribe cuando cambia algo de lo que describe; el registro no se reescribe, solo se añade.
- Los **Pendientes** son internos: no pasan a la memoria.

Plantilla:

```markdown
### AAAA-MM-DD · Título corto
Rama: `...` · Commits: `abc1234`, `def5678`
**Qué.** ...
**Por qué.** ...
**Verificación.** ...
**Memoria.** Capítulo N (sección ...). Hecho / pendiente de redactar.
```

---

## Estado actual

*Actualizado: 2026-11-24 · rama `clasificador-estados`*

**Firmware (ejemplo *Chain token passing*).** Estado congelado desde el 2026-11-19 y documentado en el capítulo 3 de la memoria.

- Testigo en cadena con mensajes *unicast*, reintentos y tiempos de espera. Todos los mensajes se envían con su longitud real.
- Informe `DATA_REPORT_MODEL` (tipo 17): un bloque por nodo, en el orden del tren, con su hijo, su nieto y `acc_x`/`acc_y`. Ocupa 50 B con 5 dispositivos y caben hasta 8. El tipo de informe viaja con el `TOKEN_HANDOFF`.
- El coordinador analiza la composición del tren (EQUAL / MISSING / NEW_DEVICES / REORDERED, ventana de 30 ciclos).
- Referencias por pareja de dispositivos: mediana provisional desde 3 medidas y fija a las 30; `unseen_cycles` con tope de 10.
- 25 entradas del modelo calculadas en el coordinador, idénticas a las de Python (diferencia máxima 3·10⁻⁵).
- Salidas configurables: `READABLE_OUTPUT`, `COMPOSITION_OUTPUT`, `RAW_DATA_OUTPUT`, `FEATURES_OUTPUT` y `AI_DEPLOYMENT`. Este último está desactivado hasta reentrenar el modelo con las 25 entradas.

**Procesado de datos (`extras/AI Integration/`).** Formato en crudo común al simulador y a las placas (27 columnas). En los dos, las distancias son medidas directas de cada pareja (hijo y nieto); el simulador marca además los ciclos con un nodo sin responder (`node_unresponsive`). Cálculo de las 25 entradas con la misma calibración que el coordinador. `grabador_serie.py` graba las placas.

**Hardware.** ESP32 UWB de MakerFabs (ESP32-WROOM-32 + DW1000), canal 5, modo 1 (110 kbps, PRF 16 MHz, preámbulo 2048).

---

## Correspondencia con la memoria

| Capítulo (Overleaf) | Entradas de este registro | Estado |
|---|---|---|
| 3 · Diseño del firmware | 2026-11-06, 2026-11-10/11, 2026-10-26/27 (firmware) | Redactado (2026-11-21) |
| 4 · Modelo de detección | 2026-11-10 (selección de variables, nieto) | Pendiente: metodología del análisis de variables |
| 5 · Datos del gemelo digital | 2026-11-09/11 y 2026-11-16/17 (procesado y simulador) | Pendiente (se redacta en la conversación del simulador) |
| 6 · Resultados | — | Pendiente: tiempo de ciclo, inferencia, ensayos en placas |

---

## Registro

*Lo más reciente primero.*

### 2026-11-24 · Adaptador del simulador: medidas directas al hijo y al nieto, y nodos sin responder
Rama: `clasificador-estados` · Simulador: `Simulador-CARLA`, rama `uwb-pairs`

**Qué.**
- **`adaptador_simulador.py`** lee el formato nuevo del simulador:
  - `coord/rx_crd.csv`, con `uwb_son` y `uwb_grandson` de cada vagón;
  - `coord/uwb_crd.csv`, con las medidas de la locomotora a w1 y w2. Se toma la fila más cercana por `frame` al mensaje de w1, o a su ranura; a más de media ranura no se usa.
- Cada pareja es una **medida directa**: ya no se resta nada. Una pareja cuenta como vista si llegó el mensaje y la medida no está vacía.
- **Un solo nombre por vehículo** (`crd`, `w1`…`w4`): `w1` es `w1`, sin traducir ids.
- **Solo se acepta el formato nuevo.** Un ensayo antiguo se rechaza con un aviso claro, también desde el exportador, que lo salta.
- **Nodos sin responder.** El adaptador lee los episodios `node_unresponsive` de `config.json` y marca cada ciclo según el instante de la ranura del vagón. El exportador añade la columna `unresponsive_nodes` al archivo de revisión, sin cambiar las etiquetas: con el tren íntegro, esos ciclos son OK. La composición guarda los episodios, los ciclos marcados y cuántos de ellos tienen mensaje del vagón, que debe ser 0.
- **Campo `nodos_sin_responder` en `ensayos_simulador.json`.** Es solo informativo y se rellena a mano; ningún script lo usa, porque mandan los episodios de `config.json`. Está documentado en el readme.
- **Documentación:**
  - readme de AI Integration, `datasets_simulador/readme.md`, `guia_exportacion.md` y cabecera de `formato_crudo.py`;
  - se borra `guia_simulador.md`, que ahora vive en el repositorio del simulador;
  - se arregla la referencia rota a `registro_cambios.md`.

**Por qué.**
- **Distancias.** La resta d(wk) − d(wk−1) tenía dos problemas. Duplicaba el ruido. Y en curva acortaba la distancia, porque solo coincide con la distancia real en recta. Además, el nieto no era una medida independiente, así que el simulador no podía enseñar la redundancia. Ahora el simulador mide igual que las placas.
- **Nodos sin responder.** Los episodios `node_unresponsive` etiquetados como OK son los ejemplos de enlaces perdidos con el tren íntegro que el modelo necesita para aprender la redundancia del nieto. La columna de revisión permite buscar falsas alarmas en esos ciclos.

**Verificación.** Se probó con un ensayo sintético en el formato nuevo: tren recto, w2 sin responder entre 20 y 30 s y un ciclo sin el mensaje de w1. La prueba pasa la cadena completa, del adaptador al exportador.
- **Con w2 sin responder,** se ven `c_w1`, `w1_w3` y `w3_w4`, y no se ven `w1_w2`, `w2_w3`, `c_w2` ni `w2_w4`. `hop2_w1_w3` mantiene su desviación ≈ 0.
- **Sin el mensaje de w1,** el coordinador usa la fila de su ranura.
- **Ciclos marcados:** se marcan 10 y ninguno tiene mensaje de w2.
- **Formato antiguo:** se rechaza con el aviso.
- **Pendiente:** verificar con los ensayos reales del laboratorio (nominal, desacople y `node_unresponsive`).

**Memoria.** Capítulo 5 (adaptación al formato común). Los ensayos del capítulo 5 hay que repetirlos con el simulador actual.

### 2026-11-21 · Memoria: proyecto de Overleaf y capítulo 3
Sin cambios en el código.

**Qué.** Se ha creado el proyecto de la memoria en Overleaf:
- `main.tex` y `preambulo.tex`, con las macros `\pendiente`, `\huecofigura` y `\cod`.
- Un fichero por capítulo con `subfiles`, para que cada capítulo compile también por separado.
- Una carpeta `entregas/` con las versiones que se envían.

Se ha redactado el capítulo 3 (Diseño del firmware): plataforma, protocolo, mensajes, informe, composición, entradas del modelo, procesado del ciclo y verificación.

**Por qué.** La memoria se escribe directamente en sus capítulos, en lugar de acumular documentos sueltos que luego haya que reescribir. Cada entrega es una compilación de los capítulos.

**Criterios de redacción acordados:**
- La memoria describe el diseño final y por qué es así, no el historial.
- No incluye sección de limitaciones.
- Los dispositivos son las ESP32.
- Las cifras de tiempo se marcan con `\pendiente` hasta medirlas.

**Memoria.** Capítulo 3 redactado. Pendiente de completar: foto de las placas, captura del monitor serie, tiempo de ciclo, tiempo de inferencia y validación en placas.

### 2026-11-18/19 · Documentación del firmware
Rama: `clasificador-estados` · Commits: `8238763`, `c4a48e0`, `2224878`, `92fd3de`

**Qué.** Se ha reescrito el readme de *Chain token passing*: informe de datos, composición, referencias, entradas del modelo, configuración y salidas. También se ha actualizado la documentación general.

**Por qué.** Que el readme describa el firmware tal como está, y sirva de referencia para la memoria.

**Memoria.** Fuente del capítulo 3.

### 2026-11-16/17 · Guía del simulador
Rama: `clasificador-estados` · Commits: `252314b` … `fe909e3`

**Qué.** Guía para generar un ensayo nuevo con CARLA: contenedor, `DISPLAY`, lanzamiento, conda, `ENABLE_RENDER`.

**Por qué.** Poder regenerar ensayos de forma reproducible.

**Memoria.** No entra en la memoria: es documentación de uso. *(Detalle en la conversación del simulador.)*

### 2026-11-10/11 · Redundancia del nieto, calibración por medidas y composición desde el informe
Rama: `clasificador-estados` · Commits: `6ec9cf6`, `d87e64b`, `95d7963`, `12feee0`, `9d93dcf`, `4d6ea0e`, `9c5c3b2`, `4c7f5a7`

**Qué.**
- **Modelo de 25 entradas.** Por cada enlace: `seen`, `unseen_cycles`, `deviation_m` y `acc_x_diff_ms2`. Por cada pareja a dos saltos (`c_w2`, `w1_w3`, `w2_w4`): las tres primeras.
- **Calibración dinámica.** La referencia de cada pareja cuenta medidas, no ciclos: mediana provisional desde 3 medidas y fija a las 30. Es la misma regla en el coordinador y en Python.
- **Composición desde el informe.** La cadena observada se toma del orden de los bloques del informe (`chain_order`), no de las medidas.
- **Fila en crudo.** Usa el formato del informe de modo modelo: 27 columnas, con las parejas a dos saltos.
- **Uso del modelo condicionado.** Las referencias, la fila en crudo, las entradas y la predicción solo existen con `USE_TINYML_MODEL`.
- **Columnas renombradas.** Nombres en inglés en el crudo, las entradas y las marcas.
- **Salida legible.** Un bloque por ciclo (`showCycle()`), sin medidas repetidas.
- Los datasets procesados dejan de seguirse en Git.

**Por qué.**
- **Nieto con distancia.** Sin el nieto, el modelo confundía un nodo apagado o un fallo de radio con una rotura. Con el nieto solo como "visto", un vagón que se aleja pero sigue al alcance se daba por bueno. Resultados (red 20-10, 5 semillas):

  | | Sin nieto | Solo "visto" | Desviación |
  |---|---|---|---|
  | Falsas alarmas con nodo apagado | 44,0 % | 24,1 % | 13,5 % |
  | Detección de la rotura | 50,2 % | 94,9 % | 95,9 % |
  | Detección con la medida directa perdida | 1,4 % | 3,6 % | 78,7 % |

- **Calibración por medidas.** Con la calibración por ciclos, un nieto que empieza a verse tarde (por ejemplo, en una curva) no tenía referencia en Python y sí en la placa.
- **Composición desde el informe.** Reconstruir la cadena desde las medidas creaba atajos con las medidas al nieto. Por ejemplo, con W2 caído al arrancar: `C1 > W1 > W3 > W4 > W2`.

**Verificación.**
- Los crudos del simulador, pasados por el código C del coordinador y por Python, dan las mismas 25 entradas (diferencia máxima 3·10⁻⁵).
- La composición se probó en PC con estos casos: informe completo, cortado, sin informe (con y sin hijo del coordinador) y dirección repetida.

**Memoria.** Capítulo 3 (secciones 3.5–3.7). La metodología de la comparación del nieto va en el capítulo 4.

### 2026-11-09 · Procesado de datos con nieto
Rama: `clasificador-estados` · Commits: `ba7ea71`, `309303e`, `6ec9cf6`

**Qué.** Nuevas carpetas de procesado y formato en crudo con las medidas al nieto. Paso intermedio de 16 columnas, antes de las 25. Readme con indicaciones de uso.

**Memoria.** Capítulo 5. *(Detalle en la conversación del simulador.)*

### 2026-11-06 · Mensajes con su longitud real e informe `DATA_REPORT_MODEL`
Rama: `clasificador-estados` · Commits: `f0a8296`, `4efa62f`, `3e67e17`, `6e3611c`, `1fd1bcb`, `34fb46b`, `a503643`, `d39e43d`, `6f1599a`, `a377821`, `1ece0ae`

**Qué.**
- **`transmit()` con la longitud real.** Cada mensaje se envía con su longitud (ACK 10 B, POLL 16 B, RANGE 28 B…), comentada campo a campo. La recepción usa la longitud de la trama.
- **Buffer limpio.** Se limpia el buffer en cada envío.
- **Orden de lectura.** El nodo y el coordinador leen el informe recibido antes de enviar su ACK, porque el ACK sobrescribe el buffer compartido.
- **Nuevo informe `DATA_REPORT_MODEL`.** Tiene un bloque por nodo (`NodeBlock`) con un byte de control (bits 0–1: número de medidas), el hijo, el nieto, `acc_x` y `acc_y`. Las distancias van en cm (`uint16`) y las aceleraciones en mm/s² (`int16`), saturadas.
- **Tipo de informe.** Es un campo obligatorio del `TOKEN_HANDOFF` (+1 B).
- **Informes antiguos eliminados.** Se quitan los informes local y agregado.

**Por qué.**
- **Longitud real.** Antes, todos los mensajes ocupaban 90 B en el aire. Con el modo 1, una trama de 90 B tarda unos 9,5 ms y una de 16 B unos 3,9 ms.
- **Informe ajustado.** Solo viaja lo que usa el modelo. El ahorro de la IMU (de 6 ejes a 2) y de la potencia RX paga la redundancia del nieto: 82 B → 50 B con 5 dispositivos.

**Verificación.**
- El informe se probó en PC con bloques de 0, 1 y 2 medidas, saturación, informes cortados y un informe que no cabe.
- Se corrigieron dos errores: un RANGE en broadcast con 5 o más dispositivos escribía fuera del buffer, y en recepción se leía el buffer entero en lugar de la trama.

**Memoria.** Capítulo 3 (secciones 3.3 y 3.4).

### 2026-10-26/27 · Primera versión del análisis en el coordinador y grabación con las placas
Rama: `clasificador-estados` · Commits: `bf6fbbe` … `4b57be4`

**Qué.**
- Composición del tren en el coordinador (`composition.h/.cpp`).
- Módulos de referencias por enlace y de entradas del modelo, en la versión de 37 columnas.
- Fila en crudo `RAW_DATA`.
- Modelo de 37 columnas ejecutándose en el coordinador.
- `grabador_serie.py` (reinicia el coordinador al empezar) y exportador de grabaciones de las ESP32: marcas, tramos y calibración con huecos.

**Por qué.** Primera integración de la composición y del modelo en el coordinador, y de la cadena de datos con las placas. La sustituyen las entradas del 2026-11-06 y del 2026-11-10/11.

**Memoria.** Solo como contexto. La memoria describe la versión final.

---

## Pendientes y problemas conocidos (interno)

*No pasan a la memoria. Se tachan o se mueven al registro cuando se resuelven.*

### Duración del ciclo (objetivo < 250 ms; antes, 400–500 ms en LOS)

Estimaciones a partir del código, sin medir:

- **Salida serie del coordinador.** Con `READABLE_OUTPUT` + `COMPOSITION_OUTPUT` + `RAW_DATA_OUTPUT` se imprimen unos 1300 caracteres por ciclo: unos 110 ms a 115200 baudios. Ese tiempo se suma a la duración del ciclo siguiente.
- **Depuración en los nodos.** `DEBUG_NODE` está a `true` en `Node.ino`, y los nodos imprimen mientras tienen el testigo.
- **`delay(10)` fijos.** Hay unos 120 ms por ciclo con 4 nodos: 2 en el coordinador, 3 por nodo intermedio y 1 en la cola.
- **Descubrimiento periódico.** Cada 6 ciclos: 500 ms en el coordinador + 300 ms por nodo, en serie. Añade unos 280 ms de media por ciclo y hace muy irregular `cycle_duration_ms`.
- **`DEFAULT_REPLY_DELAY_TIME` (8 ms).** Probablemente sobredimensionado.
- **Hipótesis por comprobar.** Los nodos hacen poll a los dispositivos anteriores de la cadena, que tienen el ranging apagado. `PollUnicastFailed()` no los marca como inactivos, así que cada uno podría costar 5 × 50 ms, salvo que los frene el borrado por inactividad de la librería (3 s).

**Plan propuesto:**
1. `TIMING_OUTPUT` con la duración y los reintentos de cada fase.
2. Medida de referencia con las salidas desactivadas.
3. Quitar los `delay(10)`.
4. Bajar el retardo de respuesta.
5. Decidir qué se hace con el descubrimiento.

### Protocolo
- **Cascada de timeouts.** Todos los nodos esperan el informe de su hijo con el mismo plazo (2500 ms), y el padre empieza a esperar antes que el hijo. Si falla un nodo profundo, vence antes el plazo del primer nodo, y al coordinador solo llega el bloque de W1: la línea se corta casi en la cabeza, no en el punto del fallo. Opciones: un plazo que dependa de la profundidad del nodo, o informes parciales.
- **Bits de estado en el byte de control.** Por ejemplo: cola por tiempo agotado, IMU no válida.

### Coordinador y modelo
- `MAX_LINK_REFS` → `2*MAX_DEVICES+4`: con 12 no basta a partir de 8 dispositivos.
- **Aviso de predicción provisional.** Contar solo las parejas en calibración (0 < `num_samples` < 30) e ignorar las que nunca se han visto.
- **`encodeDistance()` trunca en vez de redondear.** Sesgo medio de unos −0,5 cm. El simulador da las distancias sin cuantizar a cm.
- **Despliegue del modelo.** Desplegarlo cuando esté reentrenado (`AI_DEPLOYMENT`) y **medir el tiempo de inferencia en las placas** (encargo del tutor).
- **Grabación con el firmware nuevo.** Probar en las placas la grabación con `grabador_serie.py`.

### Procesado de datos
- Verificar el adaptador nuevo con los ensayos reales del laboratorio: nominal, desacople y `node_unresponsive`.
- Repetir los ensayos del simulador (desacople, prefallo, frenado) con el formato nuevo y actualizar la tabla de etiquetado del readme.

### Hardware y librería
- IMU en `readImu()` cuando llegue el hardware.
- Sacar el modelo de Edge Impulse de `src/`: pesa 24 MB y se compila con cualquier sketch.
- **Release v2.0.0:**
  - `library.properties`: nombre, URL del repositorio equivocada, `depends=ArduinoJson`.
  - Renombrar `example/` → `examples/`.
  - Añadir `LICENSE` (comprobar Apache 2.0 de la librería original).
  - Actualizar `releases.md`.

"""
Adaptador del simulador: datos del simulador -> CSV en crudo.

Lee la carpeta de un ensayo del simulador (en datasets_simulador/) y genera su CSV en crudo:
  - crudo_<ensayo>.csv        una fila por ciclo, en el formato común (formato_crudo.py)
  - composicion_<ensayo>.json qué dispositivo ocupa cada posición y cómo se generó el archivo

Normalmente no hace falta ejecutarlo: lo llama el exportador. Se puede ejecutar solo
(botón de Play) para obtener únicamente el crudo de un ensayo: ver CONFIGURACIÓN.

Solo traduce: no calcula columnas para el modelo, no etiqueta y no descarta
nada salvo el último ciclo si el registro termina a mitad de él.

Archivos del simulador que usa (solo el formato con medidas al hijo y al nieto):
  coord/rx_crd.csv     mensajes recibidos por el coordinador (uno por vagón y ciclo), con uwb_son y uwb_grandson
  coord/uwb_crd.csv    medidas UWB del propio coordinador a w1 (uwb_son) y a w2 (uwb_grandson), cada 0,25 s
  coord/imu_crd.csv    IMU del coordinador (locomotora), 200 Hz
  config.json          número de vagones, frecuencia de comunicación, periodo de la IMU y,
                       en "test" -> "node_unresponsive", los episodios en que un vagón no responde

Traducción (ver README):
  - Ciclo: una vuelta del round robin. Cada vagón tiene una ranura fija de
    1/comm_rate_hz (0,25 s) y la vuelta completa dura num_wagons ranuras (1 s).
  - Cada pareja es una medida directa, como en las placas. No se resta nada:
      c-w1 y c-w2 (dos saltos): uwb_son y uwb_grandson de la fila de uwb_crd.csv más cercana
                                al mensaje de w1 (o a su ranura, si no llegó). Si la fila más cercana
                                está a más de media ranura, la pareja cuenta como no vista.
      wk-w(k+1) y wk-w(k+2):    uwb_son y uwb_grandson del mensaje de wk en ese ciclo.
    Una pareja cuenta como vista si llegó el mensaje (o hay fila del coordinador) y la medida no está vacía.
    Así, un vagón que no responde deja sin ver sus propias medidas y las que le hacen su padre y su abuelo.
  - IMU: solo acc_x y acc_y (lo que viaja en el informe de las placas).
    La de cada vagón es la que viaja en su mensaje. La del coordinador, la muestra
    de imu_crd tomada en el mismo instante en que se recibe el mensaje de w1
    (o en su ranura, si no llegó).
  - Nodos sin responder: además del crudo, el adaptador devuelve, para cada ciclo, qué vagones estaban
    en un episodio de node_unresponsive en el instante de su ranura. El exportador lo añade al archivo de
    revisión (no entra al modelo ni cambia las etiquetas).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from formato_crudo import (VAGONES, ENLACES, PARES_SALTO2, EJES_IMU, nombre_enlace, nombre_salto2,
                           columnas_crudo, COL_CICLO, COL_TIEMPO, COL_DURACION, SUF_VISTO, SUF_DISTANCIA)


# ============================== CONFIGURACIÓN ==============================
# Solo se usa al ejecutar este script por sí solo (el exportador no la usa).

CARPETA_ENSAYO = 'decoupling_w2_150s'   # Carpeta del ensayo dentro de datasets_simulador/
NOMBRE = 'desacople'                    # Nombre del ensayo: el crudo va a datasets_procesados/simulador/<NOMBRE>/crudo/

# ===========================================================================

RAIZ = Path(__file__).resolve().parent.parent          # extras/AI Integration
CARPETA_DATASETS_SIMULADOR = RAIZ / 'datasets_simulador'
CARPETA_PROCESADOS_SIMULADOR = RAIZ / 'datasets_procesados' / 'simulador'

COLS_IMU_MENSAJE = ['ax', 'ay']             # en rx_crd.csv (en el mismo orden que EJES_IMU)
COLS_IMU_COORD = ['ax_meas', 'ay_meas']     # en imu_crd.csv
COL_UWB_HIJO = 'uwb_son'                    # en rx_crd.csv y uwb_crd.csv: distancia al vehículo de detrás
COL_UWB_NIETO = 'uwb_grandson'              # en rx_crd.csv y uwb_crd.csv: distancia al de dos posiciones detrás


class FormatoSimuladorError(ValueError):
    """El ensayo no tiene el formato del simulador que entiende este adaptador."""


def leer_ensayo(carpeta):
    carpeta = Path(carpeta)
    coord = carpeta / 'coord'
    if not (coord / 'rx_crd.csv').exists():
        if (coord / 'rx_coord.csv').exists():
            raise FormatoSimuladorError(
                f'{carpeta.name} tiene el formato antiguo del simulador (rx_coord.csv, distancias a la locomotora). '
                'Este adaptador solo acepta el formato nuevo (rx_crd.csv, uwb_crd.csv, medidas al hijo y al nieto): '
                'hay que repetir el ensayo con el simulador actual.')
        raise FormatoSimuladorError(f'{carpeta.name} no tiene coord/rx_crd.csv')
    for archivo in ('uwb_crd.csv', 'imu_crd.csv'):
        if not (coord / archivo).exists():
            raise FormatoSimuladorError(f'{carpeta.name} no tiene coord/{archivo}')

    cfg = json.loads((carpeta / 'config.json').read_text(encoding='utf-8'))
    rx = pd.read_csv(coord / 'rx_crd.csv')
    uwb = pd.read_csv(coord / 'uwb_crd.csv')
    imu = pd.read_csv(coord / 'imu_crd.csv')
    for nombre_archivo, tabla, columnas in (('rx_crd.csv', rx, [COL_UWB_HIJO, COL_UWB_NIETO] + COLS_IMU_MENSAJE),
                                            ('uwb_crd.csv', uwb, ['frame', COL_UWB_HIJO, COL_UWB_NIETO])):
        faltan = [c for c in columnas if c not in tabla.columns]
        if faltan:
            raise FormatoSimuladorError(f'a coord/{nombre_archivo} de {carpeta.name} le faltan las columnas {faltan}')
    return cfg, rx, uwb, imu


def episodios_sin_responder(cfg):
    """Episodios de node_unresponsive de config.json: lista de (vagón, t_start_s, t_end_s)."""
    episodios = []
    for e in (cfg.get('test') or {}).get('node_unresponsive') or []:
        if e['wagon'] not in VAGONES:
            raise FormatoSimuladorError(f"node_unresponsive: vagón desconocido {e['wagon']!r} (válidos: {VAGONES})")
        episodios.append((e['wagon'], float(e['t_start_s']), float(e['t_end_s'])))
    return episodios


def adaptar(cfg, rx, uwb, imu):
    """Devuelve (crudo, composicion, sin_responder): sin_responder es, por ciclo, los vagones sin responder ('w2', 'w1 w3'...)."""
    n_vagones = int(cfg['train']['num_wagons'])
    if n_vagones != len(VAGONES):
        raise FormatoSimuladorError(f'El formato en crudo es para {len(VAGONES)} vagones y el ensayo tiene {n_vagones}')
    dt_imu = float(cfg['cookie']['imu']['sensor_tick'])           # 0,005 s
    ranura_s = 1.0 / float(cfg['cookie']['comm_rate_hz'])          # 0,25 s
    ticks_ranura = int(round(ranura_s / dt_imu))                   # 50 ticks
    episodios = episodios_sin_responder(cfg)

    rx = rx[rx.msg_type == 'data'].copy()
    desconocidos = sorted(set(rx.source_id) - set(VAGONES))
    if desconocidos:
        raise FormatoSimuladorError(f'rx_crd.csv tiene mensajes de origen desconocido: {desconocidos} (válidos: {VAGONES})')
    # El identificador del simulador es ya el nombre de la posición (w1 es w1).
    # 'ranura_vagon' es solo el índice de su ranura dentro de la vuelta (w1 -> 0).
    rx['ranura_vagon'] = rx.source_id.map({v: k for k, v in enumerate(VAGONES)})

    # Reloj común. El "tick" de cada mensaje es el número de muestra de la IMU
    # en el instante de recepción, así que imu_crd sirve de tabla tick -> tiempo.
    # El tiempo cero es el inicio de la simulación: la primera muestra de la
    # IMU corresponde al primer paso (dt_imu).
    t_de_tick = pd.Series(imu.timestamp.values, index=imu.frame.values)
    t0 = imu.timestamp.iloc[0] - dt_imu
    imu_por_tick = imu.set_index('frame')[COLS_IMU_COORD]

    # Medidas del coordinador, ordenadas por frame para buscar la más cercana
    uwb = uwb.sort_values('frame').reset_index(drop=True)
    frames_uwb = uwb.frame.values

    def fila_uwb_coordinador(tick):
        """Fila de uwb_crd.csv más cercana a 'tick', o None si está a más de media ranura."""
        if len(frames_uwb) == 0:
            return None
        i = int(np.searchsorted(frames_uwb, tick))
        candidatas = [j for j in (i - 1, i) if 0 <= j < len(frames_uwb)]
        j = min(candidatas, key=lambda j: abs(frames_uwb[j] - tick))
        return uwb.iloc[j] if abs(frames_uwb[j] - tick) <= ticks_ranura / 2 else None

    # Ranura de cada mensaje y ciclo al que pertenece
    tick_base = int((rx.tick - rx.ranura_vagon * ticks_ranura).min())   # ranura 0 del ciclo 0
    rel = rx.tick - tick_base
    if (rel % ticks_ranura != 0).any():
        raise FormatoSimuladorError('Hay mensajes fuera de su ranura')
    rx['ranura'] = (rel // ticks_ranura).astype(int)
    if (rx.ranura % n_vagones != rx.ranura_vagon).any():
        raise FormatoSimuladorError('Algún vagón transmite en una ranura que no es la suya')
    rx['ciclo'] = rx.ranura // n_vagones
    if rx.duplicated(['ciclo', 'source_id']).any():
        raise FormatoSimuladorError('Mensajes duplicados en un mismo ciclo')
    rx['t'] = rx.reception_time - t0

    # El último ciclo se descarta si el registro termina antes de su última ranura
    ultimo = int(rx.ciclo.max())
    tick_ultima_ranura = tick_base + (ultimo * n_vagones + n_vagones - 1) * ticks_ranura
    if imu.frame.max() < tick_ultima_ranura:
        rx = rx[rx.ciclo < ultimo]
        ultimo -= 1

    por_ciclo = {k: g.set_index('source_id') for k, g in rx.groupby('ciclo')}
    filas, sin_responder = [], []
    for k in range(ultimo + 1):
        g = por_ciclo.get(k)
        recibidos = set() if g is None else set(g.index)
        tick_inicio = tick_base + k * n_vagones * ticks_ranura
        t_inicio = t_de_tick[tick_inicio] - t0
        fila = {COL_CICLO: k}

        # Tiempo y duración del ciclo
        if recibidos:
            t_ultimo = g.t.max()
        else:
            t_ultimo = t_inicio + (n_vagones - 1) * ranura_s
        fila[COL_TIEMPO] = int(round(t_ultimo * 1000))
        # Desde el inicio de la vuelta hasta el final de la última ranura con respuesta
        fila[COL_DURACION] = int(round((t_ultimo - t_inicio + ranura_s) * 1000))

        # Instante de referencia del coordinador: recepción del mensaje de w1 (o su ranura, si no llegó)
        tick_c = int(g.loc[VAGONES[0], 'tick']) if VAGONES[0] in recibidos else tick_inicio
        fila_c = fila_uwb_coordinador(tick_c)

        def medida(origen, columna):
            """Medida 'columna' (hijo o nieto) tomada por el vehículo 'origen' en este ciclo, o NaN."""
            if origen == 'c':
                valor = np.nan if fila_c is None else fila_c[columna]
            else:
                valor = g.loc[origen, columna] if origen in recibidos else np.nan
            return float(valor) if pd.notna(valor) else np.nan

        # Enlaces (medida al hijo) y pares a dos saltos (medida al nieto): directas, sin restas
        for parejas, nombre, columna in ((ENLACES, nombre_enlace, COL_UWB_HIJO),
                                         (PARES_SALTO2, nombre_salto2, COL_UWB_NIETO)):
            for a, b in parejas:
                d = medida(a, columna)
                fila[f'{nombre(a, b)}_{SUF_VISTO}'] = int(not np.isnan(d))
                fila[f'{nombre(a, b)}_{SUF_DISTANCIA}'] = d

        # IMU del coordinador: en el instante de recepción de w1 (o en su ranura)
        for eje, col in zip(EJES_IMU, COLS_IMU_COORD):
            fila[f'c_{eje}'] = imu_por_tick.at[tick_c, col]

        # IMU de los vagones: la de su mensaje
        for v in VAGONES:
            for eje, col in zip(EJES_IMU, COLS_IMU_MENSAJE):
                fila[f'{v}_{eje}'] = g.loc[v, col] if v in recibidos else np.nan
        filas.append(fila)

        # Vagones en un episodio de node_unresponsive en el instante de su ranura de este ciclo
        sin = []
        for p, v in enumerate(VAGONES):
            t_ranura = t_inicio + p * ranura_s
            if any(w == v and t_ini <= t_ranura < t_fin for w, t_ini, t_fin in episodios):
                sin.append(v)
        sin_responder.append(' '.join(sin))

    crudo = pd.DataFrame(filas)[columnas_crudo()]
    sin_responder = pd.Series(sin_responder, index=crudo.index, dtype=object)

    # Comprobación: un vagón marcado como sin responder no debería tener mensaje en ese ciclo
    contradicciones = sum(1 for k, s in enumerate(sin_responder) for v in s.split()
                          if v in (set() if por_ciclo.get(k) is None else set(por_ciclo[k].index)))

    composicion = {
        'origen': 'simulador',
        'vehiculos': [{'posicion': 'c', 'id': 'crd', 'papel': 'coordinador (locomotora)'}] +
                     [{'posicion': v, 'id': v, 'papel': 'vagón'} for v in VAGONES],
        'enlaces': [{'columna': nombre_enlace(a, b), 'id': f"{'crd' if a == 'c' else a}-{b}"} for a, b in ENLACES],
        'imu': 'simulada por el simulador (con ruido); solo acc_x y acc_y',
        'distancias': 'medidas directas: cada vehículo mide a su hijo (uwb_son) y a su nieto (uwb_grandson); '
                      'las del coordinador, de uwb_crd.csv',
        'nodos_sin_responder': {
            'episodios': [{'wagon': w, 't_start_s': a, 't_end_s': b} for w, a, b in episodios],
            'ciclos_marcados': int((sin_responder != '').sum()),
            'ciclos_marcados_con_mensaje': int(contradicciones),
        },
        'ciclos': int(len(crudo)),
        'periodo_nominal_ms': int(round(n_vagones * ranura_s * 1000)),
        'tiempo_cero': 'inicio de la simulación',
    }
    return crudo, composicion, sin_responder


def escribir(crudo, composicion, carpeta_crudo, nombre):
    """Escribe crudo_<nombre>.csv y composicion_<nombre>.json en carpeta_crudo."""
    carpeta_crudo = Path(carpeta_crudo)
    carpeta_crudo.mkdir(parents=True, exist_ok=True)
    crudo.to_csv(carpeta_crudo / f'crudo_{nombre}.csv', index=False, float_format='%.6f')
    (carpeta_crudo / f'composicion_{nombre}.json').write_text(
        json.dumps(composicion, indent=2, ensure_ascii=False), encoding='utf-8')


def procesar(carpeta_ensayo, nombre, carpeta_crudo):
    """Ensayo del simulador -> CSV en crudo (y su composición) en carpeta_crudo.

    Devuelve (crudo, sin_responder): sin_responder dice, por ciclo, qué vagones no respondían.
    """
    carpeta_ensayo = Path(carpeta_ensayo)
    cfg, rx, uwb, imu = leer_ensayo(carpeta_ensayo)
    crudo, comp, sin_responder = adaptar(cfg, rx, uwb, imu)
    comp['ensayo'] = nombre
    comp['carpeta_origen'] = carpeta_ensayo.name
    escribir(crudo, comp, carpeta_crudo, nombre)
    n = comp['nodos_sin_responder']
    if n['ciclos_marcados_con_mensaje']:
        print(f"     aviso: {n['ciclos_marcados_con_mensaje']} ciclo(s) marcados con un nodo sin responder tienen su "
              'mensaje; revisa los tiempos de node_unresponsive en config.json')
    return crudo, sin_responder


def main():
    carpeta = CARPETA_DATASETS_SIMULADOR / CARPETA_ENSAYO
    if not carpeta.exists():
        raise SystemExit(f'No existe el ensayo del simulador: {carpeta}')
    salida = CARPETA_PROCESADOS_SIMULADOR / NOMBRE / 'crudo'
    try:
        crudo, sin_responder = procesar(carpeta, NOMBRE, salida)
    except FormatoSimuladorError as e:
        raise SystemExit(str(e))
    extra = f', {int((sin_responder != "").sum())} con algún nodo sin responder' if (sin_responder != '').any() else ''
    print(f'{NOMBRE}: {len(crudo)} ciclos{extra} -> {salida / f"crudo_{NOMBRE}.csv"}')


if __name__ == '__main__':
    main()

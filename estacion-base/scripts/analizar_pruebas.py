#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Scripts auxiliares - Analizador de pruebas.

Analiza los logs de pruebas USB/WiFi en data/*.json.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-07

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Cada fichero = una prueba.
Calcula:
- PDR/Fiabilidad por huecos de `seq`.
- Jitter entre llegadas a partir de `t_mono`.
- RSSI medio/min a partir de `enlace.rssi_dbm`.
- Energía media del INA226 (v_bat/i_ma/p_mw) si usamos batería.

Uso:
    python3 scripts/analizar_pruebas.py [data/]
    python3 scripts/analizar_pruebas.py data/20260907T*.json
"""

import glob
import json
import os
import statistics
import sys

def _leer_registros_log(path):
    """Lee un fichero JSON Lines y devuelve la cabecera y los registros válidos."""
    cabecera = {}
    registros = []

    with open(path, encoding="utf-8") as fichero:
        for linea in fichero:
            linea = linea.strip()
            if not linea:
                continue
            try:
                obj = json.loads(linea)
            except json.JSONDecodeError:
                # Hay líneas vacías o no JSON en los logs, se ignoran.
                continue

            # Los metadatos iniciales van en una cabecera y las muestras van en
            # "dato" dentro del propio registro.
            if "dato" not in obj and "inicio" in obj:
                cabecera = obj
            elif "dato" in obj:
                registros.append(obj)

    return cabecera, registros

def _calcular_pdr(secuencias):
    """Calcula PDR y número de paquetes perdidos/duplicados a partir de seq."""
    if len(secuencias) < 2:
        return None, None, 0

    esperado = max(secuencias) - min(secuencias) + 1
    unicos = set(secuencias)
    perdidos = esperado - len(unicos)
    duplicados = len(secuencias) - len(unicos)
    pdr = round(100 * len(unicos) / esperado, 1) if esperado else None
    return pdr, perdidos, duplicados

def _calcular_jitter(registros):
    """Calcula estadísticas de jitter usando tiempos monotónicos del sistema."""
    # Extraemos los tiempos de recepción en una lista ordenada por llegada.
    tiempos_mono = [
        r.get("t_mono")
        for r in registros
        if isinstance(r.get("t_mono"), (int, float))
    ]

    # Para cada par de tiempos consecutivos, calculamos la diferencia entre ambos.
    # Esto nos da los intervalos de llegada entre paquetes.
    if len(tiempos_mono) < 2:
        intervalos = []
    else:
        intervalos = [
            siguiente - actual
            for actual, siguiente in zip(tiempos_mono, tiempos_mono[1:])
        ]

    return {
        "n": len(intervalos),
        "media": round(statistics.mean(intervalos), 2) if intervalos else None,
        "p50": round(statistics.median(intervalos), 2) if intervalos else None,
        "p95": round(sorted(intervalos)[int(len(intervalos) * 0.95)], 2) if intervalos else None,
        "max": round(max(intervalos), 2) if intervalos else None,
    }

def _calcular_rssi(registros):
    """Estadísticas del nivel de señal recibido en dBm."""
    rssis = [
        r.get("enlace", {}).get("rssi_dbm")
        for r in registros
    ]
    # Solo nos quedamos con valores válidos
    rssis = [valor for valor in rssis if isinstance(valor, (int, float))]

    return {
        "n": len(rssis),
        "media": round(statistics.mean(rssis), 1) if rssis else None,
        "min": min(rssis) if rssis else None,
        "max": max(rssis) if rssis else None,
    }

def _media_energia(registros, clave):
    """Devuelve la media de una magnitud eléctrica de la batería para una clave dada."""
    valores = [
        r["dato"].get(clave)
        for r in registros
    ]
    valores = [valor for valor in valores if isinstance(valor, (int, float))]
    return round(statistics.mean(valores), 2) if valores else None

def analizar_fichero(path):
    """Procesa un fichero de log de prueba y devuelve un resumen de métricas."""
    cabecera, registros = _leer_registros_log(path)
    if not registros:
        return None

    # Los valores de seq sirven para calcular fiabilidad y pérdida de paquetes.
    secuencias = [
        r["dato"].get("seq")
        for r in registros
        if isinstance(r["dato"].get("seq"), int)
    ]
    pdr, perdidos, duplicados = _calcular_pdr(secuencias)

    # El jitter se calcula con t_mono porque no cambia con ajustes del sistema 
    # ni con NTP.
    jitter = _calcular_jitter(registros)
    rssi = _calcular_rssi(registros)

    return {
        "fichero": os.path.basename(path),
        "test_id": cabecera.get("test_id", ""),
        "distancia": cabecera.get("test_distancia_m", ""),
        "nota": cabecera.get("test_nota", ""),
        "n_rx": len(registros),
        "pdr_pct": pdr,
        "perdidos": perdidos,
        "duplicados": duplicados,
        "dt_s": jitter,
        "rssi_dbm": rssi,
        "v_bat": _media_energia(registros, "v_bat"),
        "i_ma": _media_energia(registros, "i_ma"),
        "p_mw": _media_energia(registros, "p_mw"),
    }

def _listar_ficheros(args):
    """Expande argumentos de entrada en una lista de ficheros JSON."""
    rutas = []
    for argumento in args:
        if os.path.isdir(argumento):
            rutas.extend(sorted(glob.glob(os.path.join(argumento, "*.json"))))
        else:
            rutas.extend(sorted(glob.glob(argumento)))
    return rutas

def main():
    """Analiza todos los logs de prueba disponibles en data/"""
    argumentos = sys.argv[1:] or ["data"]
    paths = _listar_ficheros(argumentos)

    if not paths:
        print("Sin ficheros. Uso: analizar_pruebas.py [data/ | data/*.json]")
        sys.exit(1)

    filas = [resultado for path in paths if (resultado := analizar_fichero(path)) is not None]
    if not filas:
        print("Sin registros con datos en esos ficheros.")
        sys.exit(1)

    print("| prueba | dist | n_rx | PDR% | perd | dupl | dt_med/p95/max s | RSSI med/min (n) | Vbat | I mA |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")

    for fila in filas:
        dt = fila["dt_s"]
        rssi = fila["rssi_dbm"]
        print(
            f"| {fila['test_id'] or fila['fichero']} | {fila['distancia']} | {fila['n_rx']} "
            f"| {fila['pdr_pct']} | {fila['perdidos']} | {fila['duplicados']} "
            f"| {dt['media']}/{dt['p95']}/{dt['max']} (n={dt['n']}) "
            f"| {rssi['media']}/{rssi['min']} (n={rssi['n']}) "
            f"| {fila['v_bat']} | {fila['i_ma']} |"
        )

    print()
    for fila in filas:
        if fila["nota"]:
            print(f"- {fila['test_id'] or fila['fichero']}: {fila['nota']}")

if __name__ == "__main__":
    main()

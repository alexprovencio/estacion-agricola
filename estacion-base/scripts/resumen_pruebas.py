#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Scripts auxiliares - Resumen de pruebas.

Resumen conjunto de una prueba de enlace.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-01

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Combina en una sola tabla:
- Telemetría (data/*.json): PDR por seq, jitter, RSSI medio/min, energía INA226.
- Ping (data/ping-<test_id>.txt): RTT min/avg/max/mdev y pérdida de paquetes.
- Scan (data/scan-<test_id>.txt): nº de APs y canales (entorno WiFi).

Empareja ping/scan con la telemetría por TEST_ID exacto: los ficheros ping-*
y scan-* llevan el mismo TEST_ID en el nombre que el de la cabecera del JSON.

Uso:
    python3 scripts/resumen_pruebas.py data/
"""

import glob
import os
import re
import sys

import analizar_pruebas as ap

def parse_ping(path):
    """Extrae pérdida y RTT (min/avg/max/mdev) de un log de ping."""
    res = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"(\d+) packets transmitted, (\d+) received, ([0-9.]+)% packet loss", line)
            if m:
                res["tx"] = int(m.group(1))
                res["rx"] = int(m.group(2))
                res["loss_pct"] = float(m.group(3))
            m = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+) ms", line)
            if m:
                res["rtt_min"] = float(m.group(1))
                res["rtt_avg"] = float(m.group(2))
                res["rtt_max"] = float(m.group(3))
                res["rtt_mdev"] = float(m.group(4))
    return res

def parse_scan(path):
    """Extrae nº de APs y canales de un scan de iw."""
    aps = 0
    canales = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "SSID:" in line:
                aps += 1
            m = re.search(r"primary channel:\s*(\d+)", line)
            if m:
                canales.add(int(m.group(1)))
    return {"aps": aps, "canales": sorted(canales)}

def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "data"
    json_files = sorted(glob.glob(os.path.join(base, "*.json")))
    tele = [r for p in json_files if (r := ap.analizar_fichero(p)) is not None]

    pings = {}
    for p in glob.glob(os.path.join(base, "ping-*.txt")):
        tid = os.path.basename(p)[5:-4]
        pings[tid] = parse_ping(p)
    scans = {}
    for p in glob.glob(os.path.join(base, "scan-*.txt")):
        tid = os.path.basename(p)[5:-4]
        scans[tid] = parse_scan(p)

    print("| prueba | dist | n_rx | PDR% | perd | dt med/p95 s | RSSI med/min (n) | "
          "ping loss% | RTT min/avg/max/mdev ms | Vbat | I mA | APs | canales |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in tele:
        tid = r["test_id"]
        dt = r["dt_s"]
        rs = r["rssi_dbm"]
        pg = pings.get(tid, {})
        sc = scans.get(tid, {})
        print(f"| {tid} | {r['distancia']} | {r['n_rx']} | {r['pdr_pct']} | "
              f"{r['perdidos']} | {dt['media']}/{dt['p95']} | "
              f"{rs['media']}/{rs['min']} (n={rs['n']}) | "
              f"{pg.get('loss_pct', '-')} | "
              f"{pg.get('rtt_min', '-')}/{pg.get('rtt_avg', '-')}/{pg.get('rtt_max', '-')}/{pg.get('rtt_mdev', '-')} | "
              f"{r['v_bat']} | {r['i_ma']} | {sc.get('aps', '-')} | {sc.get('canales', '-')} |")
    print()
    print("Notas:")
    for r in tele:
        if r["nota"]:
            print(f"- {r['test_id']}: {r['nota']}")


if __name__ == "__main__":
    main()

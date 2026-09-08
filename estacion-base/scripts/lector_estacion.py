#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Scripts auxiliares - Lector USB.

Lector de la estación base para las pruebas por USB.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-27

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Recibe de la estación el flujo de lecturas JSON (una por línea) que emite el
nodo autónomo por su UART y las muestra de forma legible en pantalla y las 
guarda en un archivo JSON.

Uso:
    python lector_estacion.py [/dev/ttyxxx] [--log]
    Con --log guarda en data/<timestamp>.json el mismo formato JSON Lines
    que la base para analizarlo con analizar_pruebas.py.
    TEST_ID/DISTANCIA/NOTA por entorno.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
import serial

def _nuevo_log(puerto):
    """Abre un nuevo fichero JSON para guardar los registros de la prueba."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(base, exist_ok=True)
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S")
    path = os.path.join(base, f"{ts}.json")
    # Nueva cabecera con metadatos
    cabecera = {
        "inicio": datetime.now(timezone.utc).isoformat(),
        "origen": "usb",
        "puerto": puerto,
        "test_id": os.getenv("TEST_ID", ""),
        "test_distancia_m": os.getenv("TEST_DISTANCIA_M", ""),
        "test_nota": os.getenv("TEST_NOTA", ""),
    }
    f = open(path, "a", encoding="utf-8")
    f.write(json.dumps(cabecera, ensure_ascii=False) + "\n")
    f.flush()
    return f, path

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    guardar = "--log" in sys.argv or "--guardar" in sys.argv
    puerto = args[0] if args else "/dev/ttyAMA0"
    try:
        ser = serial.Serial(puerto, 115200, timeout=1)
    except serial.SerialException as e:
        print(f"No se puede abrir {puerto}: {e}")
        sys.exit(1)

    print(f"Leyendo del puerto {puerto}. Ctrl+C para salir.\n")
    flog = None
    pathlog = None
    if guardar:
        flog, pathlog = _nuevo_log(puerto)
        print(f"Guardando en {pathlog}\n")
    try:
        while True:
            t_rx_mono = time.monotonic()
            linea = ser.readline().decode("utf-8", errors="replace").strip()
            if not linea:
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError:
                # Línea no JSON, se omite
                continue
            # Agregamos marcas de tiempo de recepción para poder calcular jitter y PDR
            dato["t_rx_mono"] = t_rx_mono
            dato["t_rx_wall"] = time.time()
            print(muestra(dato), flush=True)
            if flog is not None:
                reg = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "t_mono": t_rx_mono,
                    "dato": dato,
                    "enlace": {"origen": "usb"},
                }
                flog.write(json.dumps(reg, ensure_ascii=False) + "\n")
                flog.flush()
    except KeyboardInterrupt:
        print("\nParando...")
    finally:
        if flog is not None:
            flog.flush()
            flog.close()
        try:
            ser.close()
        except Exception:
            pass

def muestra(dato):
    """Devuelve por serie los datos de una línea del log."""
    amb = dato.get("amb", {})
    suelo = dato.get("suelo", {})
    energia = dato.get("energia", {})
    rayos = dato.get("rayos", {})
    return (
        f"[{dato.get('t', '?'):>6}s] "
        f"amb {amb.get('temp_amb', 0):.1f}C "
        f"{amb.get('hum_amb', 0):.0f}% "
        f"{amb.get('presion_hpa', 0):.1f}hPa "
        f"luz {amb.get('luz_lux', 0):.0f}lx | "
        f"suelo {suelo.get('temp_suelo', 0):.1f}C "
        f"hum {suelo.get('hum_suelo', '?')} uv {amb.get('uv', '?')} | "
        f"bat {energia.get('v_bat', 0):.2f}V "
        f"{energia.get('i_ma', 0):.0f}mA | "
        f"rayos {rayos.get('estado', rayos.get('rayos_id', '?'))}"
        + (f" {rayos['dist_km']}km" if "dist_km" in rayos else "")
    )

if __name__ == "__main__":
    main()

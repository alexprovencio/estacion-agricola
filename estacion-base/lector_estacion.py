#!/usr/bin/env python3
"""Lector de la estación base para las pruebas.

Recibe de la estación el flujo de lecturas JSON (una por línea) que emite el
nodo autónomo por su UART y las muestra de forma legible en pantalla.

Uso:
    python lector_estacion.py [/dev/ttyUSB0]
"""

import json
import sys
import time

import serial


def main():
    puerto = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    try:
        ser = serial.Serial(puerto, 115200, timeout=1)
    except serial.SerialException as e:
        print(f"No se puede abrir {puerto}: {e}")
        sys.exit(1)

    print(f"Leyendo del puerto {puerto}. Ctrl+C para salir.\n")
    while True:
        linea = ser.readline().decode("utf-8", errors="replace").strip()
        if not linea:
            continue
        try:
            dato = json.loads(linea)
        except json.JSONDecodeError:
            # Línea no JSON, se omite
            continue
        print(muestra(dato), flush=True)


def muestra(dato):
    amb = dato.get("amb", {})
    energia = dato.get("energia", {})
    rayos = dato.get("rayos", {})
    return (
        f"[{dato.get('t', '?'):>6}s] "
        f"amb {amb.get('temp_amb', 0):.1f}C "
        f"{amb.get('hum_amb', 0):.0f}% "
        f"{amb.get('presion_hpa', 0):.1f}hPa "
        f"luz {amb.get('luz_lux', 0):.0f}lx | "
        f"suelo {dato.get('temp_suelo', 0):.1f}C "
        f"hum {dato.get('hum_suelo', '?')} uv {dato.get('uv', '?')} | "
        f"bat {energia.get('v_bat', 0):.2f}V "
        f"{energia.get('i_ma', 0):.0f}mA | "
        f"rayos {rayos.get('estado', rayos.get('rayos_id', '?'))}"
        + (f" {rayos['dist_km']}km" if "dist_km" in rayos else "")
    )


if __name__ == "__main__":
    main()

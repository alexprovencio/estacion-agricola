#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Inyector de enlace por serie.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-03

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Lee la telemetría que llega por un puerto serie (USB del nodo o el puente
ESP-NOW/Meshtastic) y la publica en el broker local, para que el consumidor
común (_al_recibir_telemetria) la procese.
"""

import json
import time

import serial

from . import config
from . import estado
from . import mqtt_local


def hilo():
    """Lee el puerto serie y publica en el broker local."""
    try:
        ser = serial.Serial(config.PUERTO_SERIAL, config.BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"Puerto {config.PUERTO_SERIAL}: {e}")
        return
    print(f"Inyector serie en {config.PUERTO_SERIAL}@{config.BAUD}")
    while estado.running:
        try:
            linea = ser.readline().decode("utf-8", errors="replace").strip()
        except Exception:
            if not estado.running:
                break
            continue
        if not linea:
            continue
        try:
            obj = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "dato" in obj:
            mqtt_local.publicar_telemetria(obj)
        time.sleep(0.01)

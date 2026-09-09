#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Inyector de enlace por serie.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-03

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Lee la telemetría que llega por un puerto serie (USB del nodo, el puente
ESP-NOW o el Faketec Meshtastic) y la publica en el broker local, para que el
consumidor común (_al_recibir_telemetria) la procese. No procesa nada, solo
inyecta.

El puerto emite:
- Un wrapper {"enlace":{...}, "dato":{...}} (USB directo / puente ESP-NOW):
  se reenvía tal cual.
- JSON crudo del nodo (Meshtastic no puede llevar el wrapper por el tamaño):
  se envuelve con {"enlace":{"origen":"meshtastic"}}.
- Con el modo TEXTMSG de Meshtastic el mensaje llega prefijado con "sender: ",
  que se recorta hasta el primer '{'.

Así el mismo módulo sirve para USB, ESP-NOW y Meshtastic: solo cambia qué
dispositivo hay al otro lado del puerto.
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
        # El módulo serial de Meshtastic en modo TEXTMSG antepone "sender: "
        # al JSON. Recortamos hasta el primer '{' para quedarnos con el payload.
        idx = linea.find("{")
        if idx > 0:
            linea = linea[idx:]
        try:
            obj = json.loads(linea)
        except json.JSONDecodeError:
            continue
        # Detecta que ya tiene wrapper (USB directo/puente ESP-NOW)
        if isinstance(obj, dict) and "dato" in obj:
            mqtt_local.publicar_telemetria(obj)
        # Es Meshtastic. Se envuelve.
        else:
            # JSON crudo, muy pesado para Meshtastic el otro.
            mqtt_local.publicar_telemetria(
                {"enlace": {"origen": "meshtastic"}, "dato": obj})
        time.sleep(0.01)

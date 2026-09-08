#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Persistencia local en disco.

Persistencia local en disco (un JSON por arranque).


Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-01

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

Guarda cada lectura del nodo y el estado de los relés con su timestamp 
en config.DATA_DIR en un nuevo fichero con el timestamp en su nombre. 
Para no castigar la SD volcamos cada  config.INTERVALO_DISCO segundos. 
Al cerrar se hace flush + fsync.
"""

import json
import os
import time
from datetime import datetime, timezone

from . import config

_BASE_DIR = config.DATA_DIR

_buffer = []
_ultimo_flush = 0
_fichero = None

def _asegurar_directorio():
    """Asegura que el directorio base para los logs exista."""
    os.makedirs(_BASE_DIR, exist_ok=True)

def _nombre_fichero():
    """Genera el nombre del fichero de log basado en la fecha y hora actual."""
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S")
    return os.path.join(_BASE_DIR, f"{ts}.json")

def inicializar():
    """Crea el fichero del arranque actual."""
    global _fichero, _buffer, _ultimo_flush
    _asegurar_directorio()
    _fichero = _nombre_fichero()
    _buffer = []
    _ultimo_flush = time.time()
    # Cabecera con metadatos del arranque + identificación de la prueba
    # Cada prueba = un arranque = un fichero. Usar con:
    #    sudo TEST_ID=T1_10m_VLOS TEST_DISTANCIA_M=10 TEST_NOTA="VLOS" 
    #       ~/venvs/estacion/bin/python -m estacion_base
    cabecera = {
        "inicio": datetime.now(timezone.utc).isoformat(),
        "device_nodo": config.UBI_DEVICE_NODO,
        "device_estacion": config.UBI_DEVICE_ESTACION,
        "test_id": config.TEST_ID,
        "test_distancia_m": config.TEST_DISTANCIA_M,
        "test_nota": config.TEST_NOTA,
    }
    _buffer.append(cabecera)
    _volcar(force=True)

def _volcar(force=False):
    """Vuelca el buffer a disco si ha pasado el intervalo configurado o si se fuerza."""
    global _buffer, _ultimo_flush
    if not _buffer or _fichero is None:
        return
    ahora = time.time()
    if not force and ahora - _ultimo_flush < config.INTERVALO_DISCO:
        return
    _asegurar_directorio()
    # Append en formato JSON Lines
    with open(_fichero, "a", encoding="utf-8") as f:
        for registro in _buffer:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    _buffer = []
    _ultimo_flush = ahora

def guardar(dato, extra=None):
    """Añade una lectura al buffer. No escribe a disco hasta INTERVALO_DISCO.

    `dato` ya con t_rx_* y seq, `extra` permite añadir la muestra del enlace WiFi 
    y la presencia MQTT.
    """
    from . import estado

    registro = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "t_mono": time.monotonic(),
        "dato": dato,
        "reles": list(estado.rele_manual),
        "enlace": (extra or {}).get("enlace", {}),
        "presencia": dict(estado.nodos_online),
    }
    _buffer.append(registro)
    _volcar(force=False)

def flush():
    """Vuelca lo pendiente y sincroniza. Lo llamamos al salir."""
    _volcar(force=True)
    # sync del sistema por si queda algo en cache del SO, mejor prevenir
    try:
        os.sync()
    except AttributeError:
        pass

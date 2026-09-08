#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - WiFi mide nivel de señal.

Mide el nivel de conexión con el AP del nodo.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-07

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

- Interfaz usada, SSID, RSSI (dBm), bitrate TX/RX y frecuencia.
- Autodetección de la interfaz conectada.
"""
import re
import shutil
import subprocess

from . import config

_IW = shutil.which("iw")
_cache_iface = None

def _ifs_disponibles():
    """Lista de interfaces wifi según `iw dev`"""
    try:
        out = subprocess.run(["iw", "dev"], capture_output=True, text=True,
                             timeout=2).stdout
    except Exception:
        return []
    return re.findall(r"Interface\s+(\S+)", out)

def iface_conectada():
    """Devuelve la interfaz conectada al AP del nodo, o '' si no hay"""
    global _cache_iface
    if config.WIFI_IFACE:
        return config.WIFI_IFACE
    if _IW is None:
        return ""
    # Si sigue conectada la reutilizamos
    if _cache_iface and _leer_link(_cache_iface).get("conectada"):
        return _cache_iface
    for iface in _ifs_disponibles():
        if _leer_link(iface).get("conectada"):
            _cache_iface = iface
            return iface
    return ""

def _leer_link(iface):
    """Parsea `iw dev <iface> link`. {} si no conectado / error"""
    if _IW is None or not iface:
        return {}
    try:
        out = subprocess.run(["iw", "dev", iface, "link"],
                             capture_output=True, text=True,
                             timeout=2).stdout
    except Exception:
        return {}
    if "Not connected" in out:
        return {"iface": iface, "conectada": False}
    if "Connected to" not in out:
        return {"iface": iface, "conectada": False}
    d = {"iface": iface, "conectada": True}
    m = re.search(r"SSID:\s*(.+)", out)
    if m:
        d["ssid"] = m.group(1).strip()
    m = re.search(r"freq:\s*(\S+)", out)
    if m:
        d["freq"] = m.group(1).strip()
    m = re.search(r"signal:\s*(-?\d+)\s*dBm", out)
    if m:
        d["rssi_dbm"] = int(m.group(1))
    m = re.search(r"tx bitrate:\s*(.+)", out)
    if m:
        d["tx_bitrate"] = m.group(1).strip()
    m = re.search(r"rx bitrate:\s*(.+)", out)
    if m:
        d["rx_bitrate"] = m.group(1).strip()
    return d

def muestra():
    """Muestra actual del enlace. {} si no se puede medir"""
    return _leer_link(iface_conectada())

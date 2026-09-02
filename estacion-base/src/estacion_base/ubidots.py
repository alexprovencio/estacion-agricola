#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Integración con Ubidots.

Integración con Ubidots.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-01

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

enviar(dato) sube las lecturas: sensores del nodo -> device nodo-1,
estado de relés -> device estacion-base.

aplicar_comandos() lee las variables rele_1..rele_4 del device
estacion-base y devuelve los cambios.
"""

import json
import time

import requests

from . import config
from . import estado

_URL_NODO = f"https://industrial.api.ubidots.com/api/v1.6/devices/{config.UBI_DEVICE_NODO}"
_URL_ESTACION = f"https://industrial.api.ubidots.com/api/v1.6/devices/{config.UBI_DEVICE_ESTACION}"
_HEADERS_NODO = {"X-Auth-Token": config.UBI_TOKEN_NODO, "Content-Type": "application/json"}
_HEADERS_ESTACION = {"X-Auth-Token": config.UBI_TOKEN_ESTACION, "Content-Type": "application/json"}

_ultimo_comando = {}

def _estado_rayos_num(estado):
    """Convierte el estado de rayos del nodo a un número.

    Ubidots no guarda texto...
    """
    return config.UBI_ESTADO_RAYOS.get(estado, 0)

def _payload_nodo(dato):
    """Variables del nodo autónomo."""
    amb = dato.get("amb", {})
    suelo = dato.get("suelo", {})
    energia = dato.get("energia", {})
    rayos = dato.get("rayos", {})
    d = {}
    d["temp_amb"] = amb.get("temp_amb")
    d["hum_amb"] = amb.get("hum_amb")
    d["presion_hpa"] = amb.get("presion_hpa")
    d["luz_lux"] = amb.get("luz_lux")
    d["uv_index"] = dato.get("uv_index")
    d["temp_suelo"] = suelo.get("temp_suelo")
    d["hum_suelo"] = suelo.get("hum_suelo")
    d["hum_suelo_pct"] = dato.get("hum_suelo_pct")
    d["v_bat"] = energia.get("v_bat")
    d["i_ma"] = energia.get("i_ma")
    d["p_mw"] = energia.get("p_mw")
    d["estado_rayos"] = _estado_rayos_num(rayos.get("estado")) #  Cómo número
    d["dist_km"] = rayos.get("dist_km")
    return {k: v for k, v in d.items() if v is not None}

def _payload_estacion():
    """Variables de la estación base (relés)."""
    d = {}
    for n in range(len(config.PIN_RELES)):
        d[f"rele_{n+1}"] = 1 if estado.rele_manual[n] else 0
    return d

def enviar(dato):
    """Sube datos del nodo y estación a sus respectivos devices."""
    # Nodo
    if config.UBI_TOKEN_NODO:
        try:
            r = requests.post(_URL_NODO, headers=_HEADERS_NODO,
                              data=json.dumps(_payload_nodo(dato)), timeout=5)
            if r.status_code not in (200, 201):
                print(f"Ubidots nodo: {r.status_code} {r.text[:200]}")
        except requests.RequestException as e:
            print(f"Ubidots nodo sin conexión ({e})")
    # Estación
    if config.UBI_TOKEN_ESTACION:
        try:
            r = requests.post(_URL_ESTACION, headers=_HEADERS_ESTACION,
                              data=json.dumps(_payload_estacion()), timeout=5)
            if r.status_code not in (200, 201):
                print(f"Ubidots estacion: {r.status_code} {r.text[:200]}")
            else:
                # Evita que el propio estado se reinterprete como comando
                for n in range(len(config.PIN_RELES)):
                    try:
                        rr = requests.get(f"{_URL_ESTACION}/rele_{n+1}",
                                          headers=_HEADERS_ESTACION, timeout=5)
                        # Too many requests, mal
                        if rr.status_code == 429:
                            time.sleep(1)
                            continue
                        if rr.status_code == 200:
                            ts = rr.json().get("last_value", {}).get("timestamp")
                            if ts is not None:
                                _ultimo_comando[n] = ts
                    except (requests.RequestException, ValueError):
                        pass
                    time.sleep(0.2)
        except requests.RequestException as e:
            print(f"Ubidots estacion sin conexión ({e})")

def aplicar_comandos():
    """Lee rele_1..4 de estacion-base y devuelve [(n, on)] con cambios.

    Hace un GET por variable (/devices/estacion-base/rele_N) porque el
    endpoint del device no devuelve last_value por variable.
    """
    if not config.UBI_TOKEN_ESTACION:
        return []
    comandos = []
    for n in range(len(config.PIN_RELES)):
        var_label = f"rele_{n+1}"
        url = f"{_URL_ESTACION}/{var_label}"
        try:
            r = requests.get(url, headers=_HEADERS_ESTACION, timeout=5)
            # Too many requests, mal
            if r.status_code == 429:
                print("Ubidots: rate limit, esperando")
                time.sleep(2)
                continue
            # Esto no debería ocurrir, pero...
            if r.status_code == 404:
                continue
            data = r.json()
            last = data.get("last_value")
            if not last:
                continue
            ts = last.get("timestamp")
            val = last.get("value")
            if ts is None or _ultimo_comando.get(n) == ts:
                continue
            _ultimo_comando[n] = ts
            comandos.append((n, int(val or 0) == 1))
        except (requests.RequestException, ValueError) as e:
            print(f"Ubidots {var_label}: {e}")
            continue
        time.sleep(0.25)  # no saturar la API, revisar si hay problemas
    return comandos

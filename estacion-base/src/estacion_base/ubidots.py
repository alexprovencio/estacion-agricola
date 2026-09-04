#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Integración con Ubidots.

Cliente MQTT para comunicarse con Ubidots

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-04

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

- Publica la telemetría en /v1.6/devices/nodo-1 y el estado de los
  relés en /v1.6/devices/estacion-base (cada uno con su propio token).
- Se suscribe a /v1.6/devices/estacion-base/rele_N/lv: al mover un
  interruptor en el dashboard, Ubidots avisa al instante y se reenvía
  la orden al tema local esagrau/base/control, que es donde la base
  activa los relés. Sin polling.
"""

import json
import time

import paho.mqtt.client as mqtt

from . import config
from . import estado
from . import mqtt_local

# Habría que usar conexión segura...
UBI_HOST = "industrial.api.ubidots.com"
UBI_PORT = 1883

_cliente_nodo = None
_cliente_estacion = None
_ultimo_reintento = 0

def _top_var(device, var):
    return f"/v1.6/devices/{device}/{var}"

def _on_connect_nodo(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Ubidots MQTT (nodo): conexión rechazada ({reason_code})")
    else:
        print("Ubidots MQTT (nodo) conectado")

def _on_connect_estacion(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Ubidots MQTT (estacion): conexión rechazada ({reason_code})")
    else:
        print("Ubidots MQTT (estacion) conectado")
        for n in range(len(config.PIN_RELES)):
            client.subscribe((_top_var(config.UBI_DEVICE_ESTACION, f"rele_{n+1}") + "/lv", 1))


def _on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"Ubidots MQTT desconectado ({reason_code}), reintentando...")


def _on_rele(client, userdata, msg):
    # /v1.6/devices/estacion-base/rele_N/lv -> {"rele_N": 0/1} al control local
    var = msg.topic.rsplit("/", 2)[-2]  # "rele_N"
    try:
        valor = int(float(msg.payload.decode("utf-8", errors="replace").strip()))
    except (ValueError, AttributeError):
        return
    if not var.startswith("rele_"):
        return
    try:
        n = int(var.split("_")[1]) - 1
    except (ValueError, IndexError):
        return
    if 0 <= n < len(config.PIN_RELES):
        on = (valor == 1)
        # Solo reenvía si cambia: evita rebotes de nuestros propios envíos
        if estado.rele_manual[n] != on:
            mqtt_local.publicar_control({f"rele_{n+1}": 1 if on else 0})

def _nuevo_cliente(token, on_connect):
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    cliente.username_pw_set(token, "")
    cliente.on_connect = on_connect
    cliente.on_disconnect = _on_disconnect
    cliente.reconnect_delay_set(min_delay=1, max_delay=30)
    return cliente

def iniciar():
    """Crea los dos clientes Ubidots y los deja conectados en segundo plano."""
    global _cliente_nodo, _cliente_estacion
    if config.UBI_TOKEN_NODO:
        _cliente_nodo = _nuevo_cliente(config.UBI_TOKEN_NODO, _on_connect_nodo)
        try:
            _cliente_nodo.connect(UBI_HOST, UBI_PORT, keepalive=60)
        except Exception as e:
            print(f"Ubidots MQTT (nodo): sin conexión ({e})")
        _cliente_nodo.loop_start()
    if config.UBI_TOKEN_ESTACION:
        _cliente_estacion = _nuevo_cliente(config.UBI_TOKEN_ESTACION, _on_connect_estacion)
        _cliente_estacion.on_message = _on_rele
        try:
            _cliente_estacion.connect(UBI_HOST, UBI_PORT, keepalive=60)
        except Exception as e:
            print(f"Ubidots MQTT (estacion): sin conexión ({e})")
        _cliente_estacion.loop_start()

def _asegurar(cliente):
    """True si hay conexión, si no, reintenta como mucho cada 10 s."""
    global _ultimo_reintento
    if cliente is None:
        return False
    try:
        if cliente.is_connected():
            return True
    except Exception:
        return False
    ahora = time.monotonic()
    if ahora - _ultimo_reintento < 10:
        return False
    _ultimo_reintento = ahora
    try:
        cliente.reconnect()
    except Exception as e:
        print(f"Ubidots MQTT: sin conexión ({e})")
    return False

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
    """Sube nodo y estación a Ubidots por MQTT."""
    if config.UBI_TOKEN_NODO and _asegurar(_cliente_nodo):
        try:
            _cliente_nodo.publish(f"/v1.6/devices/{config.UBI_DEVICE_NODO}",
                                  json.dumps(_payload_nodo(dato)), qos=1)
        except Exception as e:
            print(f"Ubidots MQTT (nodo): no se pudo publicar ({e})")
    if config.UBI_TOKEN_ESTACION and _asegurar(_cliente_estacion):
        try:
            _cliente_estacion.publish(f"/v1.6/devices/{config.UBI_DEVICE_ESTACION}",
                                      json.dumps(_payload_estacion()), qos=1)
        except Exception as e:
            print(f"Ubidots MQTT (estacion): no se pudo publicar ({e})")

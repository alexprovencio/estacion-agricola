#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Cliente MQTT local.

Cliente del broker Mosquitto que corre en lolcal.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-03

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Recibe:

- telemetría de los nodos (esagrau/nodos/+/telemetria),
- presencia de los nodos (esagrau/nodos/+/estado),
- órdenes de relés (esagrau/base/control),

Y publica el estado real de los relés (esagrau/base/estado, con retain).

"""

import json

import paho.mqtt.client as mqtt

from . import config
from . import estado

# Temas
TOP_TELEMETRIA = "esagrau/nodos/+/telemetria"
TOP_ESTADO = "esagrau/nodos/+/estado"
TOP_CONTROL = "esagrau/base/control"
TOP_BASE_ESTADO = "esagrau/base/estado"

_cliente = None
_cb_telemetria = None
_cb_estado = None
_cb_control = None


def _id_nodo(topic):
    # "esagrau/nodos/nodo-1/telemetria" -> "nodo-1"
    partes = topic.split("/")
    return partes[2] if len(partes) > 3 else "?"


def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT local: conexión rechazada ({reason_code})")
    else:
        print("MQTT local conectado")
        client.subscribe([(TOP_TELEMETRIA, 1), (TOP_ESTADO, 1), (TOP_CONTROL, 1)])


def _on_disconnect(client, userdata, flags, reason_code, properties):
    # paho reintenta solo gracias a reconnect_delay_set
    print(f"MQTT local desconectado ({reason_code}), reintentando...")


def _on_message(client, userdata, msg):
    try:
        texto = msg.payload.decode("utf-8", errors="replace")
    except Exception:
        return
    if msg.topic.endswith("/telemetria"):
        if _cb_telemetria:
            _cb_telemetria(texto)
    elif msg.topic.endswith("/estado"):
        if _cb_estado:
            _cb_estado(_id_nodo(msg.topic), texto)
    elif msg.topic == TOP_CONTROL:
        if _cb_control:
            _cb_control(texto)


def iniciar(on_telemetria=None, on_estado=None, on_control=None):
    """Conecta al broker local y deja la recepción en segundo plano."""
    global _cliente, _cb_telemetria, _cb_estado, _cb_control
    _cb_telemetria, _cb_estado, _cb_control = on_telemetria, on_estado, on_control
    _cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    _cliente.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
    _cliente.on_connect = _on_connect
    _cliente.on_disconnect = _on_disconnect
    _cliente.on_message = _on_message
    _cliente.reconnect_delay_set(min_delay=1, max_delay=30)
    _cliente.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
    _cliente.loop_start()
    return _cliente


def publicar_control(orden):
    """Publica una orden {"rele_N": 0/1} en esagrau/base/control.

    Es la única vía de entrada de órdenes: la base las aplica desde ahí,
    venga la orden de donde venga.
    """
    if _cliente is None:
        return
    try:
        _cliente.publish(TOP_CONTROL, json.dumps(orden), qos=1)
    except Exception as e:
        print(f"MQTT local: no se pudo publicar control ({e})")


def publicar_estado():
    """Publica el estado real de los relés (con retain)."""
    if _cliente is None:
        return
    estado_reles = {f"rele_{n+1}": 1 if estado.rele_manual[n] else 0
                    for n in range(len(config.PIN_RELES))}
    try:
        _cliente.publish(TOP_BASE_ESTADO, json.dumps(estado_reles),
                         qos=0, retain=True)
    except Exception as e:
        print(f"MQTT local: no se pudo publicar estado ({e})")

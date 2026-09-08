#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Nodo autónomo.

Hilo principal de la estación base.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-09-03

Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.

Recibe la telemetría del nodo (por MQTT WiFi o por el inyector serie 
USB/ESP-NOW/Meshtastic), la procesa con_procesar_telemetria, ejecuta 
los automatismos, sube a Ubidots y aplica los comandos de relé.

Los datos entran siempre por el broker local esagrau/nodos/+/telemetria y se
procesan en _al_recibir_telemetria. En modo "serial" el inyector
gateway_serial publica en el broker lo que llega por el puerto serie.
"""

import json
import threading
import time

from . import config
from . import enlace
from . import estado
from . import gateway_serial
from . import mqtt_local
from . import perifericos
from . import storage
from . import ubidots

def _hum_pct(raw):
    """Convierte la lectura raw del higómetro en porcentaje según la 
    calibración definida en config.HUM_ADC_SECO y config.HUM_ADC_SATURADO.
    """
    try:
        rango = config.HUM_ADC_SECO - config.HUM_ADC_SATURADO
        pct = (config.HUM_ADC_SECO - raw) / rango * 100
    except ZeroDivisionError:
        pct = 0
    return int(max(0, min(100, pct)))

def _uv_indice(raw):
    """Convierte la lectura raw del GUVA en índice UV según la 
    calibración definida en config.UV_MV_POR_INDICE y config.UV_INDICE_MAX.
    """
    mv = raw * 3300 / 4095 # 1V máximo, 3V3 y ADC de 12 bits
    # 100 mV por índice; el GUVA se satura en índice 10 (1 V)
    return round(min(mv / config.UV_MV_POR_INDICE, config.UV_INDICE_MAX), 1)

def _leer_dato(linea):
    """Parsea una línea JSON del nodo autónomo y 
    actualiza el estado compartido.
    """
    try:
        dato = json.loads(linea)
    except json.JSONDecodeError:
        return None
    # Datos del suelo y UV vienen anidados, los extraemos
    suelo = dato.get("suelo", {})
    amb = dato.get("amb", {})
    if "hum_suelo" in suelo:
        dato["hum_suelo"] = suelo["hum_suelo"]
        dato["hum_suelo_pct"] = _hum_pct(suelo["hum_suelo"])
    if "temp_suelo" in suelo:
        dato["temp_suelo"] = suelo["temp_suelo"]
    if "uv" in amb:
        dato["uv_index"] = _uv_indice(amb["uv"])
    estado.ultimo_dato = dato
    return dato

def _estado_led(dato):
    """Determina el estado del LED según los datos y la prioridad.

    La tabla de colores y el orden de prioridad están en config.LED_COLORS y
    config.LED_PRIORIDAD.
    """
    hum = dato.get("hum_suelo", 0)
    ray = dato.get("rayos", {})
    candidatos = {"ok"}
    if ray.get("estado") == "rayo" and ray.get("dist_km", 40) < config.DIST_ALERTA:
        # Rayo cercano
        candidatos.add("rayo")
    if ray.get("estado") == "disturber":
        candidatos.add("disturber")
    if estado.rele_manual[config.RELE_RIEGO]:
        candidatos.add("riego")
    if hum > config.HUM_SECO:
        # Suelo seco
        candidatos.add("seco")
    # Devolvemos el primer estado de la lista de prioridades que esté 
    # en los candidatos
    for estado_led in config.LED_PRIORIDAD:
        if estado_led in candidatos:
            return estado_led
    return "ok"

def _automatismos(dato):
    """Ejecuta los automatismos del nodo según los datos recibidos.

    Actualmente incluye:
    - Riego automático por humedad de suelo con histéresis.
    - Alerta de tormenta por rayos cercanos.
    - Actualización del LED según la prioridad de estados.
    """
    # Riego automático por humedad de suelo con histéresis
    hum = dato.get("hum_suelo", 0)
    ahora = time.time()
    if hum > config.HUM_SECO and ahora - estado.ultimo_riego > config.TIEMPO_ENTRE_RIEGOS:
        perifericos.set_rele(config.RELE_RIEGO, True)
        estado.ultimo_riego = ahora
        threading.Timer(config.TIEMPO_RIEGO,
                        lambda: perifericos.set_rele(config.RELE_RIEGO, False)).start()

    # Alerta de tormenta por rayo cercano
    ray = dato.get("rayos", {})
    if ray.get("estado") == "rayo" and ray.get("dist_km", 40) < config.DIST_ALERTA:
        if not estado.aviso_activo:
            estado.aviso_activo = True
            perifericos.decir("Alerta, tormenta cerca")
            perifericos.set_rele(config.RELE_ALERTA, True)

    # Estado del LED según la prioridad de estados
    perifericos.actualizar_led(_estado_led(dato))

def hilo_nube():
    """Hilo aparte para la comunicación con Ubidots y el estado local.
    Inicialmente compartido con el otro pero bloqueaba comunicación con el nodo.
    Los comandos de relé llegan por MQTT (callback), sin polling.
    """
    while estado.running:
        try:
            if estado.ultimo_dato:
                ubidots.enviar(estado.ultimo_dato)
            # Estado real de relés para la estación auxiliar (con retain)
            mqtt_local.publicar_estado()
        except Exception as e:
            print(f"Ubidots hilo: {e}")
        for _ in range(config.INTERVALO_CLOUD * 10):
            # Espera en intervalos cortos para poder salir rápidamente si cerramos
            if not estado.running:
                break
            time.sleep(0.1)

def _procesar_telemetria(dato, enlace_extra):
    """Procesa un dato ya parseado. Código común a todos los enlaces.

    Actualiza el estado, ejecuta los automatismos y guarda en el log con la
    información del enlace (RSSI/SNR según de dónde venga el dato).
    """
    estado.ultimo_dato_mono = time.monotonic()
    # Si llega telemetría el nodo está vivo: limpia el aviso de nodo caído.
    if estado.aviso_nodo:
        estado.aviso_nodo = False
        estado.nodo_id_caido = ""
        perifericos.decir("Nodo conectado")
    _automatismos(dato)
    try:
        storage.guardar(dato, extra={"enlace": enlace_extra})
    except Exception as e:
        print(f"Storage: {e}")


def _al_recibir_telemetria(payload):
    """Callback de esagrau/nodos/+/telemetria.

    El payload puede ser:
    - JSON crudo del nodo (enlace WiFi-MQTT): el RSSI se toma con enlace.muestra().
    - Wrapper de un inyector serie (USB/ESP-NOW/Meshtastic):
        {"enlace":{...}, "dato":{...}}.

    Se procesa con _procesar_telemetria.
    """
    t_rx_mono = time.monotonic()  # Tiempo desde arranque de la Pi
    t_rx_wall = time.time()       # Hora real
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return
    if isinstance(obj, dict) and "dato" in obj:
        # Inyector serie (gateway): lleva su propia info de enlace.
        enlace_extra = obj.get("enlace", {})
        dato = _leer_dato(json.dumps(obj["dato"]))
    else:
        # Nodo WiFi (MQTT): medimos el enlace con iw.
        try:
            enlace_extra = enlace.muestra()
        except Exception:
            enlace_extra = {}
        dato = _leer_dato(payload)
    if dato is None:
        return
    dato["t_rx_mono"] = t_rx_mono
    dato["t_rx_wall"] = t_rx_wall
    _procesar_telemetria(dato, enlace_extra)

def _al_recibir_estado(nodo_id, payload):
    """Callback de esagrau/nodos/+/estado: guarda la presencia del nodo.

    El nodo publica {"estado":"online"} con retain al conectar y el broker
    publica {"estado":"offline"} como LWT si se cae.
    """
    try:
        info = json.loads(payload)
    except json.JSONDecodeError:
        info = {"estado": payload}
    estado.nodos_online[nodo_id] = info
    print(f"Nodo {nodo_id}: {info.get('estado', '?')}")
    est = str(info.get("estado", "")).lower()
    if est == "offline":
        # No se avisa aquí
        # El aviso lo decide _comprobar_offline() por tiempo sin telemetría.
        pass
    elif est == "online":
        if estado.aviso_nodo:
            perifericos.decir("Nodo conectado")
        estado.aviso_nodo = False
        estado.nodo_id_caido = ""

def _comprobar_offline():
    """Considera el nodo desconectado si no llega telemetría en NODO_TIMEOUT_S.

    Es la única fuente del aviso de nodo caído.
    Conserva los campos extra que pueda poner _al_recibir_estado.
    No avisa si aún no ha llegado ningún dato.
    """
    if estado.ultimo_dato_mono == 0.0:
        return
    offline = time.monotonic() - estado.ultimo_dato_mono > config.NODO_TIMEOUT_S
    info = estado.nodos_online.setdefault("nodo-1", {})
    info["estado"] = "offline" if offline else "online"
    if offline:
        if not estado.aviso_nodo:
            estado.aviso_nodo = True
            estado.nodo_id_caido = "nodo-1"
            perifericos.decir("Alerta, nodo desconectado")
            perifericos.actualizar_led("rayo")

def _al_recibir_control(payload):
    """Callback de esagrau/base/control: {"rele_N": 0/1} -> conmuta relés."""
    try:
        orden = json.loads(payload)
    except json.JSONDecodeError:
        return
    for n in range(len(config.PIN_RELES)):
        # Aquí numerados desde 0, en la placa desde 1
        clave = f"rele_{n+1}"
        if clave in orden:
            perifericos.set_rele(n, bool(orden[clave]))

def hilo():
    """Bucle principal: recibe del broker local, ejecuta automatismos,
    guarda localmente y sube a la nube. Lectura serie por USB  solo para 
    depuración.
    """

    storage.inicializar()
    threading.Thread(target=hilo_nube, daemon=True).start()
    mqtt_local.iniciar(
        on_telemetria=_al_recibir_telemetria,
        on_estado=_al_recibir_estado,
        on_control=_al_recibir_control,
    )
    # En modo serie (USB/ESP-NOW/Meshtastic) arranca el inyector que
    # publica en el broker lo que llega por el puerto serie.
    if config.ENLACE_NODO == "serial":
        threading.Thread(target=gateway_serial.hilo, daemon=True).start()
    ubidots.iniciar()
    while estado.running:
        _comprobar_offline()
        time.sleep(0.5)

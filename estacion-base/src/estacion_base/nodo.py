#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Nodo autónomo.

Hilo de lectura del nodo autónomo por el puerto USB.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

Recibe las líneas JSON del ESP32, las guarda en el estado compartido, ejecuta
los automatismos (riego, alerta de rayos), sube los datos a Ubidots (cada
config.INTERVALO_CLOUD segundos) y aplica los comandos de relé recibidos 
desde Ubidots. También guardamos los datos en un fichero de log.
"""

import json
import threading
import time

import serial

from . import config
from . import estado
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
    """Hilo aparte para la comunicación con Ubidots.
    Inicialmente compartido con el otro pero bloqueaba comunicación con el nodo.
    """
    while estado.running:
        try:
            if estado.ultimo_dato:
                ubidots.enviar(estado.ultimo_dato)
            for n, on in ubidots.aplicar_comandos():
                perifericos.set_rele(n, on)
        except Exception as e:
            print(f"Ubidots hilo: {e}")
        for _ in range(config.INTERVALO_CLOUD * 10):
            # Espera en intervalos cortos para poder salir rápidamente si cerramos
            if not estado.running:
                break
            time.sleep(0.1)

def hilo():
    """Bucle principal que lee datos del nodo, ejecuta los automatismos, 
    guarda los datos localmente y los envía a la nube.
    """

    storage.inicializar()
    threading.Thread(target=hilo_nube, daemon=True).start()
    while estado.running:
        try:
            ser = serial.Serial(config.PUERTO_NODO, config.BAUD, timeout=2)
            print(f"Conectado a {config.PUERTO_NODO}")
            while estado.running:
                linea = ser.readline().decode(errors="replace").strip()
                if not linea:
                    continue
                dato = _leer_dato(linea)
                if dato is None:
                    continue

                _automatismos(dato)
                storage.guardar(dato)
        except serial.SerialException as e:
            print(f"Serie no disponible {e}, reintento en 3s")
            time.sleep(3)
        except Exception as e:
            print(f"Error lectura: {e}")
            time.sleep(1)

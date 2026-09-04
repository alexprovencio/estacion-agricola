#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Configuración.

Pines, umbrales y configuración.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.

Mapa de conexiones (Raspberry Pi 1 BCM 26 pines):

  ST7789: VDD->3V3, SCL=11, SDA=10, RES=24, DC=25, CS=8, BLK->3V3.
  EC11 y botón KEY0: TRA=17, TRB=4, PSH=22, K0=23.
  Relés (4): VCC->3V3, IN1=0, IN2=1, IN7=7, IN8=9, JD-VCC->5V.
  WS2812B: +5V->5V, Din=21.
  PAM8302A: Vin->3V3, A+ al tip del jack de 3,5mm, A- a su cubierta.
      La salida del amplificador se conecta a un altavoz de 8Ω y 0,5W.
      El jack de 3,5mm se conecta a la salida de audio de la RPi.
"""

import os
from dotenv import load_dotenv

# Carga .env con los secretos desde la raíz del proyecto estacion-base
# y desde el directorio actual por si se ejecuta desde otro sitio
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=env_path)
load_dotenv()  # fallback

# Pantalla SPI
PIN_DC = 25
PIN_RES = 24

# Relés (activo LOW)
PIN_RELES = [0, 1, 7, 9]

# Encoder EC11 y botón K0
PIN_EC_TRA = 17
PIN_EC_TRB = 4
PIN_EC_PSH = 22
PIN_K0 = 23

# LED WS2812B Usando PCM
PIN_LED_WS = 21
LED_COLORS = {
    "ok":        (0, 255, 0),    # Verde
    "seco":      (255, 255, 0),  # Amarillo
    "disturber": (255, 0, 255),  # Violeta
    "riego":     (0, 150, 255),  # Azul
    "rayo":      (255, 0, 0),    # Rojo
}
LED_PRIORIDAD = ["rayo", "disturber", "riego", "seco", "ok"]

# Enlace con el Nodo Autónomo para depuración
PUERTO_NODO = os.getenv("PUERTO_NODO", "/dev/ttyACM0")
BAUD = int(os.getenv("BAUD", "115200"))

# Broker MQTT Mosquitto local
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "estacion-base")
MQTT_PASS = os.getenv("MQTT_PASS", "")

# Ubidots
# Cada dispositivo tiene su propio token y label. Se leen del .env 
# para no subir secretos a git.
UBI_TOKEN_ESTACION = os.getenv("UBI_TOKEN_ESTACION", "")
UBI_DEVICE_ESTACION = os.getenv("UBI_DEVICE_ESTACION", "estacion-base")
UBI_TOKEN_NODO = os.getenv("UBI_TOKEN_NODO", "")
UBI_DEVICE_NODO = os.getenv("UBI_DEVICE_NODO", "nodo-1")
# Fijamos el tiempo de actualización en la nube para no saturarla.
INTERVALO_CLOUD = int(os.getenv("INTERVALO_CLOUD", "30"))

# Mapa para convertir estados de rayos a código numérico para Ubidots.
UBI_ESTADO_RAYOS = {"ok": 0, "disturber": 1, "rayo": 2, "ruido": 3}

# Calibración higrómetro
# 4095 = seco al aire, 1800 = saturado.
# Ajustar tras probar en tierra real!
HUM_ADC_SECO = int(os.getenv("HUM_ADC_SECO", "4095"))
HUM_ADC_SATURADO = int(os.getenv("HUM_ADC_SATURADO", "1800"))

# Índice UV dado por el GUVA-S12SD
# 0.1 V por índice (1 V = índice 10).
UV_MV_POR_INDICE = int(os.getenv("UV_MV_POR_INDICE", "100"))
UV_INDICE_MAX = int(os.getenv("UV_INDICE_MAX", "10"))

# Automatismos de prueba
HUM_SECO = int(os.getenv("HUM_SECO", "3800"))
HUM_HUMEDO = int(os.getenv("HUM_HUMEDO", "3000"))
# Distancia mínima en km del rayo detectado para emitir la alerta
DIST_ALERTA = int(os.getenv("DIST_ALERTA", "15"))
# Tiempo de riego cuando la tierra está seca en segundos
TIEMPO_RIEGO = int(os.getenv("TIEMPO_RIEGO", "10"))
# Tiempo mínimo entre riegos cuando la tierra está seca
TIEMPO_ENTRE_RIEGOS = int(os.getenv("TIEMPO_ENTRE_RIEGOS", "600"))
RELE_RIEGO = 0      # índice del relé usado para la bomba de riego
RELE_ALERTA = 1     # índice del relé usado para la alerta de tormenta

# Duraciones configurables para la activación manual de los relés
DURACIONES = [5, 10, 30]

# Tipografía
FONT_BIG = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MID = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Persistencia local en disco
# Directorio donde se almacenan los logs
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
# Intervalo en segundos entre volcados a disco en segundos
INTERVALO_DISCO = int(os.getenv("INTERVALO_DISCO", "30"))

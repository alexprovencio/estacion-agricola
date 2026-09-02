#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Periféricos.

Relés, LED WS2812B y audio.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

El audio usa eSpeak NG en español (py-espeak-ng) con un beep de respaldo por
si la síntesis falla. Uso hilos y una cola de mensajes para reproducirlos en orden.
"""

import queue
import subprocess
import threading
import time

import board
import neopixel
import RPi.GPIO as GPIO
from espeakng import ESpeakNG

from . import config
from . import estado

# GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for p in config.PIN_RELES:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.HIGH)   # relé OFF (activo LOW)
for p in (config.PIN_EC_TRA, config.PIN_EC_TRB, config.PIN_EC_PSH, config.PIN_K0):
    GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Botones con pull-up interno

# LED WS2812B
pixels = neopixel.NeoPixel(board.D21, 1)
pixels.brightness = 0.1  # Es extremadamente brillante!

# Voz robótica por síntesis de texto
_voz = ESpeakNG()
_voz.voice = "es"
_voz.speed = 160

# Cola para la voz y así no se mezclan
_cola_voz = queue.Queue()

def _worker_voz():
    """Procesa la cola de mensajes de voz."""
    while True:
        mensaje = _cola_voz.get()
        try:
            _voz.say(mensaje, sync=True)
        except Exception:
            _beep(880)

def _beep(freq, duracion=0.15):
    """Tono corto usado como respaldo del audio."""
    def _reproduce():
        p = subprocess.Popen(
            ["speaker-test", "-t", "sine", "-f", str(freq), "-c", "1", "-l", "1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(duracion)
        p.terminate()
    threading.Thread(target=_reproduce, daemon=True).start()

def decir(mensaje):
    """Encola un mensaje de voz."""
    _cola_voz.put(mensaje)

def set_rele(n, on):
    """Activa o desactiva el relé n. ON a LOW."""
    if n >= len(config.PIN_RELES):
        return # No hay tantos relés!
    # Comprobamos el estado real para no repetir el aviso sonoro
    actual = GPIO.input(config.PIN_RELES[n]) == GPIO.LOW
    if actual == on:
        return
    GPIO.output(config.PIN_RELES[n], GPIO.LOW if on else GPIO.HIGH)
    estado.rele_manual[n] = on
    decir(f"Relé {n + 1} " + ("encendido" if on else "apagado"))

def apagar_reles():
    """Apaga todos los relés."""
    for n in range(len(config.PIN_RELES)):
        GPIO.output(config.PIN_RELES[n], GPIO.HIGH)
        estado.rele_manual[n] = False

def apagar_rele_alerta():
    """Apaga el relé de la alerta de tormenta sin emitir aviso."""
    n = config.RELE_ALERTA
    GPIO.output(config.PIN_RELES[n], GPIO.HIGH)
    estado.rele_manual[n] = False

def actualizar_led(estado_led):
    """Cambia el color del WS2812B según el estado."""
    color = config.LED_COLORS.get(estado_led, (0, 0, 0))
    pixels[0] = color

def apagar_led():
    """Apaga el LED"""
    pixels[0] = (0, 0, 0)

# Arranca el hilo que reproduce los mensajes de voz en orden
_thread_voz = threading.Thread(target=_worker_voz, daemon=True)
_thread_voz.start()

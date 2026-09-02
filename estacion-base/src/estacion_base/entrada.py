#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Entradas.

Hilo de entrada: encoder EC11 (giro y botón) y botón externo KEY0.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

- Giro: cambia la selección dentro de los menús de relés/duración.
- Botón del encoder: pulsación corta, entra en los menús y confirma 
  la duración de activación del relé.
- Botón externo KEY0: corta retrocede en el menú y silencia las alertas,
  larga apaga además todos los relés y vuelve a la pantalla principal.
"""

import threading
import time

import RPi.GPIO as GPIO

from . import config
from . import estado
from . import perifericos

def _mover(delta):
    """Para moverse dentro de los menús de relés o duración."""
    if estado.estado_ui == estado.ESTADO_RELES:
        estado.rele_sel = (estado.rele_sel + delta) % len(config.PIN_RELES)
    elif estado.estado_ui == estado.ESTADO_DURACION:
        estado.dur_sel = (estado.dur_sel + delta) % len(config.DURACIONES)

def _push():
    """Pulsación corta del encoder.
    Entre en el menú de relés o de duración según corresponda 
    y confirma la selección de la duración de activación.
    """
    if estado.estado_ui == estado.ESTADO_PRINCIPAL:
        estado.estado_ui = estado.ESTADO_RELES
        estado.rele_sel = 0
    elif estado.estado_ui == estado.ESTADO_RELES:
        estado.estado_ui = estado.ESTADO_DURACION
        estado.dur_sel = 0
    elif estado.estado_ui == estado.ESTADO_DURACION:
        # Activa el relé seleccionado durante la duración elegida.
        d = config.DURACIONES[estado.dur_sel]
        perifericos.set_rele(estado.rele_sel, True)
        # Programa el apagado automático del relé tras la duración seleccionada.
        threading.Timer(d, lambda n=estado.rele_sel: perifericos.set_rele(n, False)).start()
        estado.estado_ui = estado.ESTADO_PRINCIPAL

def _push_largo():
    """Pulsación larga del botón externo KEY0.
    Apaga todos los relés y alertas y vuelve a la pantalla principal.
    """
    perifericos.apagar_reles()
    estado.aviso_activo = False
    perifericos.actualizar_led("ok")
    estado.estado_ui = estado.ESTADO_PRINCIPAL

def _extra():
    """Silencia la alerta y apaga el relé que la activó
    También retrocede en el menú si se está dentro de él.
    """
    estado.aviso_activo = False
    perifericos.apagar_rele_alerta()
    perifericos.actualizar_led("ok")
    if estado.estado_ui == estado.ESTADO_DURACION:
        estado.estado_ui = estado.ESTADO_RELES
    elif estado.estado_ui == estado.ESTADO_RELES:
        estado.estado_ui = estado.ESTADO_PRINCIPAL

def hilo():
    """Hilo de entrada: gestiona el encoder EC11 y el botón externo KEY0."""
    last_tra = GPIO.input(config.PIN_EC_TRA)
    while estado.running:
        tra = GPIO.input(config.PIN_EC_TRA)
        trb = GPIO.input(config.PIN_EC_TRB)

        # Giro (solo dentro de los menús)
        if tra != last_tra and tra == 0:
            if estado.estado_ui != estado.ESTADO_PRINCIPAL:
                _mover(-1 if trb == 0 else 1)
            time.sleep(0.05)
        last_tra = tra

        # Botón del encoder
        if GPIO.input(config.PIN_EC_PSH) == 0:
            while estado.running and GPIO.input(config.PIN_EC_PSH) == 0:
                time.sleep(0.02)
            _push()
            time.sleep(0.2)

        # Botón externo KEY0: corta = menú/silenciar, larga = apagar todo
        if GPIO.input(config.PIN_K0) == 0:
            tiempo_presion = time.time()
            tiempo_largo = 1.0
            while estado.running and GPIO.input(config.PIN_K0) == 0:
                time.sleep(0.02)
                if time.time() - tiempo_presion > tiempo_largo:
                    break
            duracion = time.time() - tiempo_presion
            if duracion > tiempo_largo:
                _push_largo()
            else:
                _extra()
            time.sleep(0.2)

        time.sleep(0.01)

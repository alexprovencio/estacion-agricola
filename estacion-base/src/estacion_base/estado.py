#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Estado global.

Estado global compartido entre los distintos hilos de la estación base.

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

Se importa como módulo para que todos los hilos lean y modifiquen los mismos
valores sin necesidad de pasarlos por parámetros.
"""

from . import config

# Indica si el programa sigue en marcha
running = True

# Última lectura recibida del nodo (JSON)
ultimo_dato = {}

# Alerta de tormenta activa
aviso_activo = False

# Interfaz
ESTADO_PRINCIPAL = "principal"  # Info del nodo
ESTADO_RELES = "reles"          # Selección de relés
ESTADO_DURACION = "duracion"    # Duración de la activación de los relés
estado_ui = ESTADO_PRINCIPAL
rele_sel = 0
dur_sel = 0

# Estado de los relés
rele_manual = [False] * len(config.PIN_RELES)

# Instante del último riego automático
ultimo_riego = 0

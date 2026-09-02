#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Punto de entrada.
   
Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.

Arranca los hilos de lectura del nodo y de entrada (encoder/botones) 
y dibuja la pantalla en bucle. Al salir apaga relés, LED y pantalla y 
limpia los GPIO.
"""

import signal
import sys
import threading
import time

from . import estado
from . import nodo
from . import entrada
from . import pantalla
from . import perifericos
from . import storage


def cleanup(signum=None, frame=None):
    """Apaga todo, limpia GPIOS y guarda el log actual."""
    print("\nApagando...")
    estado.running = False
    time.sleep(0.1)
    perifericos.apagar_reles()
    perifericos.apagar_led()
    pantalla.apagar()
    try:
        storage.flush()
    except Exception:
        pass
    perifericos.GPIO.cleanup()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup)  # Apagado o kill

    perifericos.actualizar_led("ok")
    threading.Thread(target=nodo.hilo, daemon=True).start()
    threading.Thread(target=entrada.hilo, daemon=True).start()

    while estado.running:
        pantalla.dibujar()
        time.sleep(0.3)  # Respuesta más o menos decente

    cleanup()

if __name__ == "__main__":
    main()

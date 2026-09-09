#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estación Agrícola - Estación base - Pantalla.

Dibuja en el TFT ST7789 (320x240).

Autor: Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
Fecha: 2026-08-31

Práctica final de Sistemas Digitales para el Internet de las Cosas.   

Tres vistas: principal (todos los datos del nodo + estado de relés), 
selección de relé y selección de duración. 
Todo se dibuja en un solo bucle.
"""

from PIL import Image, ImageDraw, ImageFont
from luma.core.interface.serial import spi
from luma.lcd.device import st7789

from . import config
from . import estado
from . import perifericos

device = spi(port=0, device=0, gpio_DC=config.PIN_DC,
             gpio_RST=config.PIN_RES, bus_speed_hz=16000000)
display = st7789(device, width=320, height=240, rotate=3)

# Retocar para adaptar a la pantalla pero jodería todo
font_big = ImageFont.truetype(config.FONT_BIG, 22)
font_mid = ImageFont.truetype(config.FONT_MID, 16)
font_small = ImageFont.truetype(config.FONT_MID, 12)

def _pinta_reles(draw):
    """Estado de los relés con fondo verde si están encendidos."""
    for i in range(len(config.PIN_RELES)):
        row = i // 2
        col = i % 2
        x = 10 + col * 160
        y = 110 + row * 35
        on = perifericos.GPIO.input(config.PIN_RELES[i]) == perifericos.GPIO.LOW
        draw.rectangle((x, y, x + 68, y + 24),
                       fill="#00AA00" if on else "#333333")
        draw.text((x + 22, y + 4), f"R{i+1}", font=font_mid, fill="white")

def _banner(draw, linea1, linea2, x1=50, x2=38):
    """Banner rojo de aviso a pantalla completa inferior.

    Para tormenta y para nodo caído.
    """
    draw.rectangle((0, 175, 320, 240), fill="red")
    draw.text((x1, 180), linea1, font=font_big, fill="white")
    draw.text((x2, 210), linea2, font=font_big, fill="white")


def dibujar():
    """Dibuja la interfaz de usuario en la pantalla."""
    img = Image.new("RGB", display.size, "black")
    draw = ImageDraw.Draw(img)

    # Arrancando
    if not estado.ultimo_dato:
        draw.text((10, 110), "Esperando nodo...", font=font_big, fill="white")
        display.display(img)
        return

    u = estado.ultimo_dato

    if estado.estado_ui == estado.ESTADO_PRINCIPAL:
        draw.text((10, 8),
                  f"{u.get('temp_amb', 0):.1f}°C  {u.get('hum_amb', 0):.0f}%  "
                  f"{u.get('presion_hpa', 0):.0f}hPa",
                  font=font_mid, fill="white")
        draw.text((10, 32),
                  f"Luz {u.get('luz_lux', 0):.0f} lux  UV {u.get('uv_index', 0):.1f}",
                  font=font_mid, fill="white")
        hum_pct = u.get("hum_suelo_pct", 0)
        draw.text((10, 56),
                  f"Suelo {u.get('temp_suelo', 0):.1f}°C  Hum {hum_pct}%",
                  font=font_mid, fill="white")
        draw.text((10, 80), f"Bat {u.get('v_bat', 0):.2f}V", font=font_small,
                  fill="#AAAAAA")
        estado_r = u.get("estado_rayos", "-")
        color = "red" if estado_r == "rayo" else "yellow" if estado_r == "disturber" else "white"
        draw.text((120, 80), f"Rayos: {estado_r}", font=font_small, fill=color)
        if "dist_km" in u:
            draw.text((200, 80), f"{u['dist_km']}km", font=font_small, fill="white")

        _pinta_reles(draw)

        if estado.aviso_nodo:
            _banner(draw, "¡AVISO!", "¡NODO CAÍDO!", x1=50, x2=15)
        elif estado.aviso_activo:
            _banner(draw, "¡ALERTA!", "¡TORMENTA!")

    elif estado.estado_ui == estado.ESTADO_RELES:
        draw.text((10, 10), "Selecciona rele:", font=font_mid, fill="#88CCFF")
        for i in range(len(config.PIN_RELES)):
            y = 40 + i * 35
            sel = i == estado.rele_sel
            on = perifericos.GPIO.input(config.PIN_RELES[i]) == perifericos.GPIO.LOW
            bg = "#00AA00" if on else "#333333"
            if sel:
                draw.rectangle((5, y - 2, 315, y + 28), fill="#444444")
            draw.rectangle((10, y, 78, y + 24), fill=bg)
            draw.text((22, y + 4), f"R{i+1}", font=font_small, fill="white")
            draw.text((100, y + 4), "ON" if on else "OFF",
                      font=font_small, fill="white")

    elif estado.estado_ui == estado.ESTADO_DURACION:
        draw.text((10, 10), f"R{estado.rele_sel+1} - duracion:",
                  font=font_mid, fill="#88CCFF")
        for i, d in enumerate(config.DURACIONES):
            y = 50 + i * 35
            if i == estado.dur_sel:
                draw.rectangle((5, y - 2, 315, y + 28), fill="#444444")
            draw.text((20, y + 4), f"{d} segundos", font=font_mid, fill="white")

    display.display(img)

def apagar():
    img = Image.new("RGB", display.size, "black")
    display.display(img)

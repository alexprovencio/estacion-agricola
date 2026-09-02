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

def dibujar():
    """Dibuja la interfaz de usuario en la pantalla."""
    img = Image.new("RGB", display.size, "black")
    draw = ImageDraw.Draw(img)

    # Arrancando
    if not estado.ultimo_dato:
        draw.text((10, 110), "Esperando nodo...", font=font_big, fill="white")
        display.display(img)
        return

    amb = estado.ultimo_dato.get("amb", {})
    ray = estado.ultimo_dato.get("rayos", {})

    if estado.estado_ui == estado.ESTADO_PRINCIPAL:
        draw.text((10, 8),
                  f"{amb.get('temp_amb', 0):.1f}°C  {amb.get('hum_amb', 0):.0f}%  "
                  f"{amb.get('presion_hpa', 0):.0f}hPa",
                  font=font_mid, fill="white")
        draw.text((10, 32),
                  f"Luz {amb.get('luz_lux', 0):.0f} lux  UV {estado.ultimo_dato.get('uv_index', 0):.1f}",
                  font=font_mid, fill="white")
        hum_pct = estado.ultimo_dato.get("hum_suelo_pct", 0)
        draw.text((10, 56),
                  f"Suelo {estado.ultimo_dato.get('temp_suelo', 0):.1f}°C  Hum {hum_pct}%",
                  font=font_mid, fill="white")
        ene = estado.ultimo_dato.get("energia", {})
        draw.text((10, 80), f"Bat {ene.get('v_bat', 0):.2f}V", font=font_small,
                  fill="#AAAAAA")
        estado_r = ray.get("estado", "-")
        color = "red" if estado_r == "rayo" else "yellow" if estado_r == "disturber" else "white"
        draw.text((120, 80), f"Rayos: {estado_r}", font=font_small, fill=color)
        if "dist_km" in ray:
            draw.text((200, 80), f"{ray['dist_km']}km", font=font_small, fill="white")

        _pinta_reles(draw)

        if estado.aviso_activo:
            draw.rectangle((0, 175, 320, 240), fill="red")
            draw.text((50, 180), "¡ALERTA!", font=font_big, fill="white")
            draw.text((38, 210), "¡TORMENTA!", font=font_big, fill="white")

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

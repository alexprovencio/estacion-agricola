# Estación Agrícola Autónoma

Sistema de medición ambiental y del suelo para huertas al aire libre, construido como práctica final de **Sistemas Digitales para el Internet de las Cosas** y continuado en **Comunicaciones Inalámbricas y Protocolos para el Internet de las Cosas** (micromáster IoT, UNED, curso 2025/2026).

![Sistema completo con el panel de control de Ubidots](docs/static/sistema-completo.jpg)

## Qué hace

Un **nodo autónomo** (ESP32-C3 SuperMini) mide *in situ* temperatura y humedad ambientales, presión atmosférica, iluminación, índice UV, humedad y temperatura del suelo, y proximidad de tormentas. Envía sus lecturas en JSON por USB a una **estación base** (Raspberry Pi 1 Model B) que las muestra en una pantalla, acciona relés, emite avisos de voz y las publica en la nube (Ubidots).

## Estructura del repositorio

```
├── nodo-autonomo/      Firmware del ESP32-C3 (PlatformIO / Arduino)
├── estacion-base/      Programa de la estación base (Python, paquete instalable)
└── docs/               Memoria y material de referencia
```

## Documentación

Todo el detalle está en la memoria:

- [Memoria de la práctica (Sistemas Digitales)](docs/memoria-sistemas.md) - arquitectura del sistema, sensores, conexiones, código, instalación y configuración.
- [Diagrama de arquitectura](docs/arquitectura.md) - flujo de datos entre el nodo y la estación base.

## Nodo autónomo (firmware)

Proyecto [PlatformIO](https://platformio.org/) para el ESP32-C3 SuperMini con el framework Arduino. Se compila y flashea con la extensión *PlatformIO* de Visual Studio Code, o desde terminal:

```bash
cd nodo-autonomo
pio run --target upload
```

El nodo se alimenta por USB y cada 5 s emite una línea JSON por la consola serie (`monitor_speed` = 115200 en `platformio.ini`). Los sensores empleados, librerías y formato de datos está en la [memoria](docs/memoria-sistemas.md).

## Estación base

Requisitos: Raspberry Pi con sistema con SPI y audio habilitados, las dependencias del sistema indicadas en la memoria y Python 3.9 o superior.

```bash
cd estacion-base
python3 -m venv ~/venvs/estacion
source ~/venvs/estacion/bin/activate
pip install --upgrade pip
pip install -e .
cp .env.example .env          # rellenar tokens de Ubidots
sudo ~/venvs/estacion/bin/python -m estacion_base
```

Se ejecuta con como `root` por el uso de DMA de la librería *neopixel* (ver memoria). El programa lee el nodo por el puerto USB (/dev/ttyACM0), dibuja en la pantalla, gestiona relés, encoder y avisos de voz, y comunica con Ubidots cada 30 s.

## Conexiones

Los esquemas completos se generaron con Cirkit Designer y se citan en la [memoria](docs/memoria-sistemas.md), junto con la lista de pines del nodo (entradas analógicas, bus I2C, OneWire e interrupciones) y de la estación base (SPI para la pantalla, pines de relés, LED y botones).

## Configuración de Ubidots

La estación base publica en dos dispositivos separados: `nodo-1` con las lecturas de los sensores y `estacion-base` con el estado de los relés, que además pueden activarse a distancia desde el panel. Más detalle en la [memoria](docs/memoria-sistemas.md#4-plataforma-iot-en-la-nube-ubidots).

## Mejoras previstas

Las líneas de trabajo futuras (enlace inalámbrico, alimentación solar, escalabilidad a varios nodos, MQTT, carcasas 3D...) están recogidas en la [memoria](docs/memoria-sistemas.md#5-conclusiones-y-mejoras-futuras).
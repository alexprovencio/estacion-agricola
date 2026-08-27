# Introducción

La idea para este trabajo es realizar un sistema completo de mediciones ambientales y del suelo para usarlo en agricultura, más orientada a horticultura o a regadío que a cultivos de cereales, aunque también sería aplicable. El sistema en principio lo he diseñado para usarlo en huertas al aire libre (no en invernadero) y realizará las siguientes mediciones in situ:

- Temperatura y humedad ambientes.
- Iluminación.
- Índice UV.
- Proximidad de tormentas.
- Humedad y temperatura del suelo.

Todas estas mediciones serán efectuadas por un nodo autónomo equipado con una batería y un panel solar que se instalaría en la propia huerta y cuyos datos se enviarán a una estación base para su posterior procesamiento.

[Esquema del sistema]

Esta estación base dispondrá a su vez de una pantalla para visualización de los datos y/o alertas del sistema, botones para el control del mismo, un altavoz para emitir alertas (por ejemplo ante la proximidad de una tormenta) y controlorá una serie de relés que, hipotéticamente, podrían controlar bombas de riego, luces... 

El sistema se diseñará, en esta primera etapa, con una conexión simple por UART entre el nodo autónomo y la estación base, con la idea de mejorar el sistema de comunicaciones entre ambos en la práctica final de la asignatura Comunicaciones Inalámbricas y Protocolos para el Internet de las Cosas y hacerlo escalable para que una sola estación base pueda gestionar múltiples nodos autónomos.

Cabe señalar que he decidido aprovechar buena parte del hardware que ya tenía para realizar esta práctica para ponerla en funcionamiento y realizar pruebas con hardware real, lo cual me parece imprescindible.

[Foto del sistema]

# Nodo solar autónomo

El nodo solar autónomo está compuesto de un ESP32-C3 Supermini de TENSTAR ROBOT[^3] como unidad de procesamiento. Este microcontrolador tiene las siguientes características:

- Procesador: CPU de 32 bits RISC-V con núclo único, operando a una frecuencia de hasta 160 MHz.
- Memoria: 4 MB de memoria Flash integrada, 400 KB de SRAM y 384 KB de ROM.
- Conectividad: Soporte integrado para Wi-Fi (protocolo 802.11 b/g/n en banda de 2.4 GHz) y Bluetooth 5.0 (BLE), con antena cerámica incorporada.
- Interfaces y Pines: 11 GPIOs digitales configurables (usables como PWM) y 4 entradas analógicas (ADC), además de interfaces UART, I2C, SPI e I2S.
- Alimentación y Consumo: Se alimenta mediante puerto USB Tipo C (5V) o pines de 3.3V, destacando por un consumo ultra bajo en modo deep sleep de aproximadamente 43 µA.
- Seguridad: Incluye aceleradores de hardware para cifrado (AES-128/256), hashing, arranque seguro (Secure Boot) y cifrado de flash.
- Indicadores y botones: LED azul integrado conectado al pin GPIO8 y botones físicos para reinicio y arranque.

[Foto del TENSTAR ROBOT]

Usaré para programar la extensión PlatformIO de VSCode con el framework Arduino que dispone de muchas librerías ya probados para los sensores que emplearé.

Los datos se envían por UART en formato JSON usando [la librería ArduinoJSON](https://github.com/bblanchon/ArduinoJson).

## Sensores ambientales

A este microcontrolador conectamos los siguientes sensores:

- AHT20+BMP280: mide temperatura, humedad relativa y presión atmosférica ambientales. El módulo que tengo combina ambos sensores y funciona por I2C. Uso las [librerías de Adafruit para los AHTTX0](https://github.com/adafruit/Adafruit_AHTX0) y para el [BMP280](https://github.com/adafruit/adafruit_bmp280_library).
- VEML7700: mide la luz ambiental real de forma lineal y con alta precisión y funciona por I2C. Rango de medición de 0 a 167.000 lux, detecta luz visible e IR. Uso la [librería de Adafruit](https://github.com/adafruit/Adafruit_VEML7700) para el VEML7700
- GUVA-S12SD: Índice UV / 240-370nm, predecir el estrés fotoquímico de las plantas, el riesgo de quemaduras en hojas/frutos y el momento óptimo para la aplicación de ciertos tratamientos agrícolas. Cúpula o ventana de acrílico/policarbonato 100% transparente sellada con silicona neutra de exterior. Ojo con el vidrio común o plásticos de mala calidad, ya que bloquean los rayos UV (240-370nm). Sensor analógico, opera de 3,3 a 5V, ver qué valores entrega y cómo interpretarlos.
- Sensor de Rayos (AS3935): Configurar una interrupción por GPIO en el ESP32-C3 para capturar descargas en tiempo real. Sensible a las interferencias electromagnéticas (EMI) de los convertidores DC-DC, pantallas y el propio WiFi/Bluetooth del ESP32-C3. Puede ir dentro de la caja estanca plástica IP65 principales (las ondas RF de los rayos atraviesan el plástico sin problema), pero aléjalo al menos 10-15 cm del ESP32-C3 (esto determina que tendrá que ir fuera de la caja), del módulo CN3791 y de los cables de alimentación. [Ejemplo de uso](https://garrysblog.com/2025/07/23/ben-franklin-and-diy-lightning-detection-using-a-as3935-lightning-sensor/), [como conectarlo](https://tasmota.github.io/docs/AS3935/), [evitar interferencias](https://www.improwis.com/projects/sw_chip_AS3935/#Resonatormodificationyellowfaultyboard), [ejemplo de uso](https://github.com/raupulus/rpi-pico-sensor-lightning-cjmcu-3935) con una Raspberry Pi Pico y Micropython, [ejemplo de uso](https://cmheong.blogspot.com/2020/11/as3935-lightning-detector-with-i2c-and.html) con un ESP8266 usando 
[esta](https://github.com/cmheong/AS3935_I2C) librería que está basada en [esta](https://github.com/stevemarple/AS3935) librería. Cablear usando cable Ethernet y dejar espacio, PROBAR. Uso la [librería de SparkFun](https://github.com/sparkfun/SparkFun_AS3935_Lightning_Detector_Arduino_Library) al menos para las pruebas iniciales.

![Conexión I2C del sensor AS3935](image.png)

## Sensores de suelo

- Higómetro de suelo: enterrado en el suelo, máximo a 1,5-3m del suelo, o colocar la placa del LM393 cerca del sensor del suelo dentro de una caja estanca (mirar si hay alguna para imprimir). Pon un pequeño condensador cerámico de 100nF entre la entrada ADC y GND en el ESP32 para filtrar el ruido eléctrico. Ver qué valores entrega y cómo interpretarlos.
- DS18B20 (Sonda Sumergible / Cableada): enterrado en la tierra, usa una resistencia de pull-up entre VCC y DATA. One wire parece. [Librería usada](https://www.pjrc.com/teensy/td_libs_OneWire.html), tiene también info de OneWire y valores de resistencias y [esta](https://github.com/milesburton/Arduino-Temperature-Control-Library) para leer los valores. For DS18B20: Ground pins 1 and 3 (the centre pin is the data line) ??? esto es así? necesito comprobar bien la resistencia que debo usar.


## Alimentación
- INA226: Conectado por I2C entre el CN3791, la batería y el ESP32, permite medir con extrema precisión (16 bits) el voltaje de la batería, la corriente de carga/descarga y el consumo en vatios. Uso la [librería de RobTillaart](https://github.com/RobTillaart/INA226) para el INA226.
- CN3791: para mejorar el rendimiento del panel solar.
- Panel solar pendiente de elegir.
- Batería: 18650, mirar si uso una o dos. Ver la necesidad de conectar BMS o algún regulador de tensión, tengo XL6019, LM2596, MP1584EN, CARGADOR BATERIA 1S CON ELEVADOR DC 4.2-28V 18650 TP4056 LX-LCBST, MH-CD42 CD42 DC 5V 2.1A módulo Diy de energía móvil 3,7/4,2 V carga/descarga (impulso)/protección de batería/placa indicadora, LTC4054, 

[Esquema de conexión de todo al ESP32]

# Estación base

Usaré mi viaja y fiable Raspberry Pi 1 Model b Rev1.0 que emplee para la práctica de la asignatura Comunicaciones Inalámbricas y Protocolos para el Internet de las Cosas. Esta versión tiene las siguientes características relevantes:
- Procesador: Broadcom BCM2835 con núcleo único ARM1176JZF-S a 700 MHz.
- Memoria: 256 MB SDRAM (compartida entre CPU y GPU).
- Red: Puerto Ethernet RJ45 10/100 Mbps. Conectado a mi red local.
- USB: 2 puertos USB 2.0. Puentee los fusibles poliméricos integrados para no limitar la corriente con la que se alimentan los dispositivos USB.
- Almacenamiento: Tarjeta MicroSD de 64GB.
- GPIO: Cabecera de 26 pines (8 pines GPIO, más pines para I2C, SPI y UART).
- Alimentación: Entrada Micro USB, uso una fuente de 5V 2A.



![Mi Raspberry Pi 1 Model B Rev1.0](raspberry.jpg)

Usar la Pantalla 2" pulgadas ST7789 con 320x240px con codificador rotatorio EC11 SPI. Librería Tft_espi by bodmer. con el encoder conectada a la raspberry pi para mostrar los datos recibidos de los nodos autónomos y un pequeño menú de control, también para parar las alertas y controlar manualmente los relés.

Conectar un amplificador (MAX98357 I2S 3W Class D Amplifier Module) con un altavoz también a GPIO para las alertas de tormenta y otras posibles alertas

Usaré también un módulo con 8 relés a 5V Relay Module With Optocoupler para simular la apertura de válvulas de riego (podemos usar LEDs inicialmente para probar que funcione correctamente).

Puedo usar también algún LED WS2812B que ya tengo para reflejar el estado del sistema y alertar si no es demasiado y no me da problemas para alimentarlo directamente desde la RPi.

El sistema de la estación base será en el futuro, con las nuevas comunicaciones, ampliable para soportar más nodos autónomos. Lo tengo que diseñar pensando en ello.

La estación base estará alimentada desde la red eléctrica a 5V.

## Configuración inicial

Uso *DietPi*[^1] como imagen para la Raspberry Pi dado que es una imagen mínima y tendrá mejor rendimiento que una imagen de Raspbian completa.

Por defecto I2C y SPI están deshabilitados, se pueden activar desde dietpi software (hacerlo y probarlos).

### Configuración del broker MQTT Mosquitto

Quito la contraseña del broker MQTT
Broker probado y funcionando en la Raspberry Pi.
Realizar el diseño de los temas en el broker de la estación base

## Programa de monitorización y control

No detallar el código aquí, solo cómo lo hago y qué hace y el diseño, quizás incluir algún gráfico.

### Controles externos

Mapa de conexiones.
Pantalla, botones, menús, altavoz, relé, posible LED o LEDs.

# Comunicaciones

Empaquetar las lecturas en una cadena de texto/JSON y enviarlas periódicamente por el puerto serie (UART) a la raspberry pi. Lo ideal es que la forma de transmitir la información esté ya preparada para mejorarla en la práctica de Comunicaciones Inalámbricas.

# Plataforma IoT en la nube: ThingsBoard

Plataforma orientada a telemetría masiva, open source, con opción de autoalojarla o usarla en la nube. La autoalojaré en mi servidor proxmox en mi red local y será donde la estación base envíe los datos para una mejor visualización y almacenamiento, pero los automatismos en princpio se ejecutarán en la estación base.

Enlace [^2]
Hay un [script](https://community-scripts.org/scripts/thingsboard) que automatiza la instalación de ThingsBoard CE en un contenedor LXC que me valdría
```
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/thingsboard.sh)"
```

Usar el broker MQTT Mosquitto que ya tengo en Home Assistant compartido con ThingsBoard, no necesito instalar otro.

# Mejoras futuras

Carcasa digna que no voy a diseñar para esta práctica
Uso de mosfet, como el Si2312 para apagar sensores cuando no se utilizan en el ESP32
Uso de otro protocolo de comunicaciones
Sensor de pluviometría con sensor de efecto hall o reed switch, con plato con balancín e imán de neodimio que vuelca el agua cuando alcanza determinado volumen, impreso en 3D.
Anemómetro y veleta para registrar velocidad y dirección del viento.
Usar ESP32-C6 que tienen mejor conectividad, aunque en nuestro caso nos da igual si no usamos WiFi
Firmware actualizable via OTA, uso de secure boot
Si el INA226 detecta que la batería cae por debajo del 20%, puedo hacer que el ESP32-C3 entra en un modo de ultra-bajo consumo (Deep Sleep prolongado) o desactiva lecturas secundarias para garantizar que la alerta de tormenta (AS3935) siga funcionando.
Asegurar bien la conexión MQTT.
Integrar los datos recibidos por la estación base en mi Home Assistant aprovechando que ThingsBoard usará el mismo broker que HA.

# Conclusiones

[^1]: DietPi - Lightweight justice for your SBC!. Disponible en:  <https://dietpi.com/>. Accedido el 12/8/2026.
[^2]: ThingsBoard - Open-source IoT Platform. Disponible en:  <https://thingsboard.io/>. Accedido el 23/8/2026.
[^3]: TENSTAR ROBOT - Placa de desarrollo TENSTAR ROBOT ESP32 C3 SuperMini, WiFi Bluetooth. Disponible en:  <https://tenstar.pro/robot-esp32-c3-supermini/>. Accedido el 24/8/2026.


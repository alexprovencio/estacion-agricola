# 0. Notas

Probar a conectar el nodo autónomo y la estación base por WiFi directo, para hacer pruebas de alcance, velocidad, latencia, robustez... Hacer lo mismo también conectándolos por ESP-NOW usando un ESP32 auxiliar conectado a la estación base. 

Finalmente la comunicación se realizará con un nodo meshtastic conectado por uart al nodo autónomo y otro a la estación base que estará conectada por ethernet con mi red de casa. Usaré mis Faketec V4 con nRF52840 y firmware Meshtastic. Idealmente debería transmitir también a la red mehstastic los datos ambientales y del INA226 que soporte el protocolo nativamente.
	- Posibilidad de mandar comandos desde la estación base, reinicios aunque sea (esto se puede hacer con la administración normal de meshtastic, no hace mucha falta).
	- Posibilidad de difundir los mensajes en un canal normal bajo petición expresa, en el canal Bots por ejemplo
	- Estudiar si uso el modo SIMPLE de meshtastic o el PROTO con el puedo enviar paquetes de telemetría nativa de meshtastic, también mensajes a un nodo en concreto.
	- Para recibir conectar un Faketec con meshtastic a la estación base, conectarlo al broker Mosquitto que ejecutamos en la estación base para que envíe los datos al tema que designemos.

Quiero usar un Cheap Yellow Display (Estación Auxiliar) para mostrar tambíen los datos que muestra la pantalla de la estación base y el menú, tenerlo en cuenta a la hora de programar la versión inicial de la visualizacion para ver si podemos compartir el código entre la pantalla de la estación base y la auxiliar. El CYD se conectará por WiFi a la misma red local donde está conectada la estación base y accederá a su broker Mosquitto para recibir y enviar datos. Ver si puedo conectar fácilmente un altavoz a la estación auxiliar.

Para la memoria incluir una comparativa de rendimiento entre los diferentes enlaces utilizados en la práctica: UART en bus directo, ESP-NOW, LoRa Mesh (Meshtastic) y MQTT sobre WiFi (evaluando aspectos como cobertura, robustez y latencia).

Hay que prestar atención a controlar los posibles errores de conexión que se produzcan entre los nodos que usan el server MQTT y asegurar bien los servidores MQTT y clientes que usemos.
# 1. Introducción

# 2. Nodo solar autónomo

## 2.2. Comunicación con la estación base

Paso a usar el broker MQTT de la estación base. Uso la librería <https://registry.platformio.org/libraries/marvinroger/AsyncMqttClient> para comunicarme con él. Uso el ejemplo disponible para el ESP32 para realizar mi implementación <https://registry.platformio.org/libraries/marvinroger/AsyncMqttClient/examples/FullyFeatured-ESP32/FullyFeatured-ESP32.ino>. Iba a usar los *timers* de *FreeRTOS* invocados expresamente para realizar reconexiones sin bloquear el *loop* principal y no tener que crear hilos tal como se hace en el ejemplo, pero me acabo de enterar de que el núcleo de ESP32 para Arduino ya corre de forma nativa sobre FreeRTOS <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos.html>. Yo he usado FreeRTOS antes en microcontroladores STM32, por lo que la integración nativa en los ESP32 es una buena noticia, le sacaré partido de aquí en adelante.

### UART por USB

Inicialmente usé la conexión por USB que ya tenía en la práctica de Sistemas y comprobé que funcionaba bien el cambio a MQTT tanto en la estación base como en Ubidots.

### WiFi

Para las pruebas con el WiFi uso la librería integrada en el núcleo del ESP32 <https://espressif-docs.readthedocs-hosted.com/projects/arduino-esp32/en/latest/api/wifi.html> y creo un AP en el nodo autónomo al que se conectará la estación base. OJO, no poner gateway o nos quedamos sin internet!

Para empezar la Raspberry Pi da problemas de alimentación con el WiFi USB, lo tenemos que conectar con ella apagada y aun así hay veces que no lo reconoce o que no conecta si el nodo no estaba encendido antes, no es muy fiable. Cuando conecta funciona bien, se nota poco lag. No nos avisa por pantalla cuando el nodo se desconecta, lo cambio usando un dibujo similar al de tormenta y un aviso sonoro, uso el LWT del broker MQTT para detectar el estado desconectado del nodo autónomo.

Pongo un hub USB alimentando tanto a la RPi como al USB WiFi y a todo lo que conecte por USB. Para que conecte bien con el hub USB usar el puerto 2 y desenchufarlo y enchufarlo con la RPi funcionando.

### ESP-NOW

Necesitamos que los paquetes sean de como mucho 250 bytes en la v1.0, pero admite 1470 bytes en la v2.0 <https://docs.espressif.com/projects/esp-faq/en/latest/application-solution/esp-now.html> y <https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/network/esp_now.html>, <https://randomnerdtutorials.com/esp-now-esp32-arduino-ide/>

Incluidas por defecto, ver versión:
`#include <esp_now.h>`

Usamos el core Arduino del ESP32 ojo <https://github.com/espressif/arduino-esp32>, la versión por defecto es la v3.0 (ESP-IDF 5.1 o mayor con soporte v2.0 ESP-NOW) donde cambian algunas cosas, tenerlo en cuenta para los ejemplos. NO LA TRAE POR DEFECTO PLATFORMIO! <https://github.com/platformio/platform-espressif32/issues/1225#issuecomment-4216264938> hay soporte de la comunidad si lo necesitamos <https://github.com/pioarduino/platform-espressif32>:

Migro a piarduino deshabilitando PlatformIO, instalando la extensión y usando:

```
platform = https://github.com/pioarduino/platform-espressif32/releases/download/stable/platform-espressif32.zip
framework = arduino
```

ESP-NOW no es un protocolo IP, es enlace punto a punto connectionless ejemplos para el framework arduino <https://espressif-docs.readthedocs-hosted.com/projects/arduino-esp32/en/latest/api/espnow.html>, por lo que necesitamos un gateway que traduzca a IP para mandar la info al broker. Podemos usar el propio puente (ESP32-C3 idéntico al del nodo) mediante WiFi o mejor, la propia estación y así nos vale para republicar lo que recibamos en el futuro del Faketec con enlace usando Meshtastic. Usamos modo one-way communication <https://docs.arduino.cc/tutorials/nano-esp32/esp-now/>, 

![alt text](image.png)

Creo un inyector para que procese lo que llega por el puerto serie (USB/ESP-NOW/Meshtastic) y lo mande al broker, luego se procesa casi igual, la información de enlace para el WiFi la calculamos nosotros, la de serie nos llega del puente.

Creo un firmware puente para el ESP32-C3 conectado a la RPi por USB.

Como ahora no hay sesión MQTT para los nodos que usan el gateway no usamos estado para esos nodos ni LWT, aunque ya no lo usábamos antes porque era demasiado exigente.

Funciona! después de sacar las MACs de cada ESP32, es rapidísimo! al ser un protocolo P2P sin conexión es inmmediato. La reconexión es inmediata!

### Meshtastic

## 2.1 Alimentación

- INA226: Conectado por I2C entre el CN3791, la batería y el ESP32, permite medir con extrema precisión (16 bits) el voltaje de la batería, la corriente de carga/descarga y el consumo en vatios. Uso la [librería de RobTillaart](https://github.com/RobTillaart/INA226) para el INA226.
- CN3791: para mejorar el rendimiento del panel solar.
- Panel solar pendiente de elegir.
- Batería: batería de litio con protección integrada.
- Hay que usar un regulador de voltaje para alimentar directamente el ESP32, lo puedo hacer a 3,3V <https://zbotic.in/solar-power-for-esp32-mppt-and-battery-charging-circuit/>

Al hacer pruebas veo que el INA226 no me devuelve datos de corriente, no había iniciado bien la librería con el registro de calibración, lo soluciono, tengo que darle la resistencia del shunt que en mi módulo es 0.1 Ω

# 3. Estación base

## 3.1. Configuración del broker MQTT

Broker *mosquitto* probado y funcionando en la Raspberry Pi, instalado usando el gestor de software de DietPi. El proceso de instalación se detalló en la Práctica 1 de la asignatura. Agrego mi propia configuración en `/etc/mosquitto/conf.d/local.conf` para hacerlo más seguro:

```bash
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Creo usuarios y contraseñas para `nodo-1` y `estacion-base` usando `mosquitto_passwd`. Destacar que el programa me avisa de que el fichero de contraseñas por defecto no pertenece al grupo `root`, si no al grupo `mosquitto`, pero lo dejo puesto que este broker corre con el usuario `mosquitto` y no le voy a dar al fichero permisos de lectura universales. A continuación reinicio el broker usando `sudo dietpi-services restart mosquitto`

A continuación paso a diseñar los temas que usaré para todos los dispositivos que se conectan a este broker. Uso *ESAGRAU* como prefijo diferenciador, significando las siglas EStación AGRícola AUtónoma:

| Tema | Dirección | QoS | Retain | Payload (ejemplo) | Descripción |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `esagrau/nodos/{id}/telemetria` | Nodo → Base | 1 | No | `{"t":14107,"amb":{...},"suelo":{...},"energia":{...},"rayos":{...}}` | Medida periódica cada 5 s. Las estaciones base y auxiliar son las suscriptoras (`esagrau/nodos/+/telemetria`). |
| `esagrau/nodos/{id}/estado` | Nodo → Base | 1 | Sí | `{"estado":"online","rssi":-42,"snr":3.5,"bateria":4.08}` o con LWT `{"estado":"offline"}` | Presencia. Con `retain` la estación sabe si el nodo está vivo al reconectar. Se usa como *Last Will* de MQTT. |
| `esagrau/nodos/{id}/control` | Base → Nodo | 1 | No | `{"accion":"reboot"}` / `{"accion":"set","param":"interval","valor":10}` | Control puntual de los nodos. Para uso futuro |
| `esagrau/base/estado` | Base → Auxiliar, Ubidot y Base | 0 | Sí | `{"rele_1":1,"rele_2":0,...}` | Estado de la estación base para la estación auxiliar, Ubidots y la propia estación base  |
| `esagrau/base/control` | Auxiliar, Ubidots y Base → Base | 1 | No | `{"rele_1":0/1}` deseado | Solo la base, que es la que activa los relés, se suscribe.
| `esagrau/nodos/+/telemetria` | — | — | — | — | Comodín al que se suscribirán las estación base y auxialiares cuando haya varios nodos. |

De esta forma evitamos rebotes ya que la única que lee de `esagrau/base/control` para activar los relés es la propia estación base, y la única que actualiza el estado real de los relés en `esagrau/base/estado` también es la propia estación base.


## 3.2. Programa de monitorización y control

Uso la versión 2.x de la librería `paho-mqtt` <https://pypi.org/project/paho-mqtt/> para comunicarme con mi broker local Mosquitto, no hay demasiados cambios en el programa, los de `nodo.py`

# 3.3 Comunicación con Ubidots

Usar MQTT, mandar cambios de relés al momento, también las alertas de rayos

# 4. Comparación entre métodos de comunicación

PDR es Packet Delivery Ratio, usamos `seq` con números secuenciales para saber si perdemos paquetes.
Log modificado, añadida cabecera y más valores de conexión para las inalámbricas\
Modificado script de lectura por USB para pruebas de rendimiento.
Script de análisis de log hecho!

Distancias pruebas:
- a 30cm
- a 10m sin obstáculos
- a 10m con la puerta cerrada
- USB conectado
- Todo en un entorno con bastantes WiFis

`Bus 001 Device 011: ID 0bda:8176 Realtek Semiconductor Corp. RTL8188CUS 802.11n WLAN Adapter`

Todas las pruebas se ejecutan durante 10 minutos.

| prueba | dist | n_rx | PDR% | perd | dt med/p95 s | RSSI med/min (n) | ping loss% | RTT min/avg/max/mdev ms | Vbat | I mA | APs | canales |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T0_0m | 0.3 | 115 | 100.0 | 0 | 5.17/5.19 | -39.0/-42 (n=115) | 0.0 | 1.665/3.222/61.454/3.531 | 3.81 | 182.25 | 25 | [1, 2, 4, 6, 10, 11] |
| T1_10m_LOS | 10 | 116 | 100.0 | 0 | 5.17/5.21 | -69.8/-78 (n=116) | 0.0 | 4.067/15.569/93.774/10.148 | 3.8 | 183.94 | 11 | [1, 2, 4, 6, 10, 11] |
| T2_10m_VLOS | 10 | 115 | 100.0 | 0 | 5.17/5.2 | -73.3/-76 (n=115) | 0.333333 | 2.577/7.344/212.359/11.513 | 3.75 | 186.22 | 11 | [1, 2, 4, 6, 10, 11] |
| T5_usb | 0.3 | 116 | 100.0 | 0 | 5.17/5.18 | -/- (n=-) | - | -/-/-/- | - | - | - | - |

Notas:
- T0_0m: WiFi lado a lado
- T1_10m_LOS: WiFi línea con visión directa
- T2_10m_VLOS: WiFi línea con una puerta cerrada en medio
- T5_usb: usb directo

## USB

Usamos un script y no el programa principal de la estación base, porque este último ya usa MQTT, para probar el rendimiento de la conexión usando USB.

`TEST_ID=T5_usb TEST_DISTANCIA_M=0.3 TEST_NOTA="usb directo" python3 scripts/lector_estacion.py /dev/ttyACM0 --log`

Repetirlas bien con el nuevo programa

## WiFi

Saturación de la WiFi:
`sudo iw dev wlan0 scan | grep -E "SSID|signal|primary channel"`

Estado del enlace:
`sudo iw dev wlan0 link`

Ejecución de cada prueba:
`udo TEST_ID=Tx_xm_x TEST_DISTANCIA_M=x TEST_NOTA="..." ~/venvs/estacion/bin/python -m estacion_base`

A la vez en otra cosola hacemos:
`ping -c 600 -i 1 192.168.4.1 > data/ping-T2_10m_VLOS.txt`

Prueba T0_0m:
```bash
        signal: -40 dBm
        rx bitrate: 121.5 MBit/s MCS 6 40MHz
        tx bitrate: 150.0 MBit/s MCS 7 40MHz short GI
```

Prueba T1_10m_LOS:
```bash
        signal: -70 dBm
        rx bitrate: 6.0 MBit/s
        tx bitrate: 150.0 MBit/s MCS 7 40MHz short GI
```

Prueba T1_10m_VLOS:
Casi no puedo conectar, hubo que cambiar el timeout para detectar el nodo desconectado, luego misteriosamente fue bien!
```bash
        signal: -74 dBm
        rx bitrate: 1.0 MBit/s
        tx bitrate: 150.0 MBit/s MCS 7 40MHz short GI
```

## ESP-NOW

`sudo ENLACE_NODO=serial TEST_ID=Tx_xm_ESP-NOW TEST_DISTANCIA_M=x TEST_NOTA="..." ~/venvs/estacion/bin/python -m estacion_base`
Prueba T0_0m: enlace rápido y estable como una roca.
Prueba T1_10m_LOS:
Prueba T1_10m_VLOS:

## Meshtastic



# 5. Estación auxiliar

Cheap Yellow Display (CYD) <https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display>

pioarduino, librerías:
- <https://github.com/PaulStoffregen/XPT2046_Touchscreen>
- <https://github.com/Bodmer/TFT_eSPI>

Sigo este tutorial <https://randomnerdtutorials.com/programming-esp32-cyd-cheap-yellow-display-vs-code/>
Tutorial para LVGL <https://randomnerdtutorials.com/lvgl-cheap-yellow-display-esp32-2432s028r/> y documentación <https://lvgl.io/docs/open/integration/frameworks/platformio>


# 6. Conclusiones y mejoras futuras

Hay muchas mejoras que se pueden implementar en el sistema, entre ellas destaco:

- Emplear MQTT con *Ubidots*?
- Mejorar la UI de la estación base, incluir RSSI del enlace si es relevante
- Hacer el sistema realmente escalable para que una sola estación base pueda soportar múltiples nodos autónomos que se conectarían fácilmente sin tocar el código? si no es fácil de implementar lo dejamos
- Modificar el programa de la estación base para que sea instalable como un servicio para que se inicie automáticamente cada vez que lo alimentemos y además podamos monitorizar su estado. Igualmente, cambiar la ubicación del log.
- Realizar cajas impresas en 3D diseñadas a medida tanto para el nodo autónomo, separando los sensores que necesitan estar en el exterior con sus propias carcasas, como para la estación base.
- Usar *mosfets*, como el Si2312, para apagar los sensores cuando no se utilizan en el nodo autónomo y así ahorrar energía.
- Añadir al nodo autónomo un sensor de pluviometría para registrar el nivel de lluvia y un anemómetro y veleta para registrar la velocidad y dirección del viento.
- Usar un ESP32-C6 reemplazando al ESP32-C3 empleado por ser la última versión de esta gama y tener mejor conectividad, aunque en principio nosotros no emplearemos ni WiFi ni Bluetooth para comunicarnos sí que se podría hacer algo usando la conexión Matter (IEEExxxx) integrada.
- Firmware del nodo autónomo actualizable vía *OTA*, uso de *secure boot*.
- Usar mejores sensores de suelo ya que los empleados se corroen fácilmente como he comprobado.
- Crear PCBs para todo el sistema, especialmente para el nodo autónomo, y así reducir su tamaño y coste.
- Mejorar la estación auxiliar para incluir el accionamiento de los relés, la UI e integrar algún sensor que podmeos mandar al broker MQTT de la estación base.
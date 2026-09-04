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

Para las pruebas con el WiFi uso la librería integrada en el núcleo del ESP32 <https://espressif-docs.readthedocs-hosted.com/projects/arduino-esp32/en/latest/api/wifi.html> y creo un AP en el nodo autónomo al que se conectará la estación base. OJO, no poner gateway o nos quedamos sin internet!



## 2.1 Alimentación

- INA226: Conectado por I2C entre el CN3791, la batería y el ESP32, permite medir con extrema precisión (16 bits) el voltaje de la batería, la corriente de carga/descarga y el consumo en vatios. Uso la [librería de RobTillaart](https://github.com/RobTillaart/INA226) para el INA226.
- CN3791: para mejorar el rendimiento del panel solar.
- Panel solar pendiente de elegir.
- Batería: batería de litio con protección integrada.
- Hay que usar un regulador de voltaje para alimentar directamente el ESP32, lo puedo hacer a 3,3V <https://zbotic.in/solar-power-for-esp32-mppt-and-battery-charging-circuit/>


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

# 4. Estación auxiliar

Cheap Yellow Display (CYD), puedo conectarle un sensor de temperatura y enviarlo también al MQTT de la estación base e incluso mostrarlo por la pantalla, no sé si se puede conectar mucho más porque las entradas son muy limitadas. Probablemente no usarlo para controlar relés porque complicaría las cosas, no?

# 5. Conclusiones y mejoras futuras

Hay muchas mejoras que se pueden implementar en el sistema, entre ellas destaco:

- Emplear MQTT con *Ubidots*?
- Hacer el sistema realmente escalable para que una sola estación base pueda soportar múltiples nodos autónomos que se conectarían fácilmente sin tocar el código? si no es fácil de implementar lo dejamos
- Realizar cajas impresas en 3D diseñadas a medida tanto para el nodo autónomo, separando los sensores que necesitan estar en el exterior con sus propias carcasas, como para la estación base.
- Usar *mosfets*, como el Si2312, para apagar los sensores cuando no se utilizan en el nodo autónomo y así ahorrar energía.
- Añadir al nodo autónomo un sensor de pluviometría para registrar el nivel de lluvia y un anemómetro y veleta para registrar la velocidad y dirección del viento.
- Usar un ESP32-C6 reemplazando al ESP32-C3 empleado por ser la última versión de esta gama y tener mejor conectividad, aunque en principio nosotros no emplearemos ni WiFi ni Bluetooth para comunicarnos.
- Firmware del nodo autónomo actualizable vía *OTA*, uso de *secure boot*.
- Usar mejores sensores de suelo ya que los empleados se corroen fácilmente como he comprobado.
- Crear PCBs para todo el sistema, especialmente para el nodo autónomo, y así reducir su tamaño y coste.
# Notas

Probar a conectar el nodo autónomo y la estación base por WiFi directo, para hacer pruebas de alcance, velocidad, latencia, robustez... Hacer lo mismo también conectándolos por ESP-NOW usando un ESP32 auxiliar conectado a la estación base. 

Finalmente la comunicación se realizará con un nodo meshtastic conectado por uart al nodo autónomo y otro a la estación base que estará conectada por ethernet con mi red de casa. Usaré mis Faketec V4 con nRF52840 y firmware Meshtastic. Idealmente debería transmitir también a la red mehstastic los datos ambientales y del INA226 que soporte el protocolo nativamente.
	- Posibilidad de mandar comandos desde la estación base, reinicios aunque sea (esto se puede hacer con la administración normal de meshtastic, no hace mucha falta).
	- Posibilidad de difundir los mensajes en un canal normal bajo petición expresa, en el canal Bots por ejemplo
	- Estudiar si uso el modo SIMPLE de meshtastic o el PROTO con el puedo enviar paquetes de telemetría nativa de meshtastic, también mensajes a un nodo en concreto.
	- Para recibir conectar un Faketec con meshtastic a la estación base, conectarlo al broker Mosquitto que ejecutamos en la estación base para que envíe los datos al tema que designemos.

Quiero usar un Cheap Yellow Display (Estación Auxiliar) para mostrar tambíen los datos que muestra la pantalla de la estación base y el menú, tenerlo en cuenta a la hora de programar la versión inicial de la visualizacion para ver si podemos compartir el código entre la pantalla de la estación base y la auxiliar. El CYD se conectará por WiFi a la misma red local donde está conectada la estación base y accederá a su broker Mosquitto para recibir y enviar datos. Ver si puedo conectar fácilmente un altavoz a la estación auxiliar.

Para la memoria incluir una comparativa de rendimiento entre los diferentes enlaces utilizados en la práctica: UART en bus directo, ESP-NOW, LoRa Mesh (Meshtastic) y MQTT sobre WiFi (evaluando aspectos como cobertura, robustez y latencia).

Hay que prestar atención a controlar los posibles errores de conexión que se produzcan entre los nodos que usan el server MQTT y asegurar bien los servidores MQTT y clientes que usemos.

# Introducción
# Nodo solar autónomo

## Alimentación

- INA226: Conectado por I2C entre el CN3791, la batería y el ESP32, permite medir con extrema precisión (16 bits) el voltaje de la batería, la corriente de carga/descarga y el consumo en vatios. Uso la [librería de RobTillaart](https://github.com/RobTillaart/INA226) para el INA226.
- CN3791: para mejorar el rendimiento del panel solar.
- Panel solar pendiente de elegir.
- Batería: batería de litio con protección integrada.
- Hay que usar un regulador de voltaje para alimentar directamente el ESP32, lo puedo hacer a 3,3V <https://zbotic.in/solar-power-for-esp32-mppt-and-battery-charging-circuit/>

# Comunicaciones
# Estación base

## Configuración del broker MQTT Mosquitto

Quito la contraseña del broker MQTT
Broker probado y funcionando en la Raspberry Pi.
Realizar el diseño de los temas en el broker de la estación base

# Estación auxiliar
# Mejoras futuras
# Conclusiones

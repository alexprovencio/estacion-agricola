/**
 * @file
 * @brief Estación Agrícola - Nodo solar autónomo
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-03
 *
 * Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.
 *
 * Lee todos los sensores del nodo y envía las lecturas por el USB
 * en formato JSON para que la estación base las procese.
 *
 * @details
 * Mapa de conexiones (ESP32-C3 Supermini y módulos):
 * @code
 *   Todos los módulos van alimentados a 3V3 y con GND común para todo.
 *   I2C SDA          <- GPIO0  AHT20+BMP280, VEML7700, INA226 y AS3935
 *   I2C SCL          <- GPIO1  AHT20+BMP280, VEML7700, INA226 y AS3935
 *   AS3935 IRQ       <- GPIO5  Interrupción de detección de rayos
 *   GUVA-S12SD ADC   <- GPIO3  Índice UV, entrada analógica
 *   Higrómetro ADC   <- GPIO4  Humedad de suelo, entrada analógica
 *   DS18B20 Data     <- GPIO6  Temperatura de suelo, OneWire, pull-up de 4,7 kΩ
 *   INA226 IN+       <- CN3791 BAT+
 *   INA226 IN-       <- MH-CD41 BAT+
 *   INA226 VBS       <- CN3791 BAT+
 *   MH-CD41 BAT+     <- CN3791 BAT-
 *   MH-CD41 BAT-     <- GND
 *   MH-CD41 OUT+     <- ESP32-C3 5V
 *   MH-CD41 OUT-     <- GND
 *   CN3791 BAT+      <- +Batería de 3,7V y MH-CD41 BAT+
 *   CN3791 BAT-      <- -Batería de 3,7V y GND
 *   CN3791 SOLAR IN+ <- + Panel Solar hasta 6V
 *   CN3791 SOLAR IN- <- - Panel Solar hasta 6V
 *   Para el AS3935 además:
 *      SI a 3V3
*       MISO a GND
*       CS a GND
 * @endcode
 */

#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>

#include <Adafruit_AHTX0.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_VEML7700.h>
#include <INA226.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <SparkFun_AS3935.h>
#include <WiFi.h>
#include "esp_mac.h"

#if defined(TRANSPORTE_WIFI)
#include <AsyncMqttClient.h>
#include <Ticker.h>
#include "wifi_manager.h"
#endif
#if defined(TRANSPORTE_ESP_NOW)
#include <esp_now.h>
#include <esp_wifi.h>
#endif
#include "secrets.h"

// Pines
#define PIN_I2C_SDA        0
#define PIN_I2C_SCL        1
#define PIN_AS3935_IRQ     5
#define PIN_ADC_GUVA       3
#define PIN_ADC_HIGROMETRO 4
#define PIN_DS18B20        6
// LED integrado (GPIO8)
#define PIN_LED             8

// UART al Faketec con Meshtastic
// GPIO21 = TX (al RX del Faketec), GPIO20 = RX (al TX del Faketec)
// No son D3 y D4 marcados en la placa!!!!
#define SERIAL1_RX         20
#define SERIAL1_TX         21
#define MESHTASTIC_BAUD    38400

#define UART_BAUD          115200
// Tiempo entre lecturas de los sensores y envío de los datos
#define INTERVALO_MS       29920 // 30s para Meshtastic

// Dirección I2C de los módulos
#define AS3935_ADDR        0x03 // A0 y A1 a VCC
#define INA226_ADDR        0x40 // A0 y A1 a GND
#define BMP280_ADDR        0x77
// Dirección de backup del BMP280
#define BMP280_B_ADDR      0x76

// Códigos de evento que devuelve el AS3935 al leer la interrupción
#define RAYO_INT           0x08
#define DISTURBER_INT      0x04
#define RUIDO_INT          0x01

// INA226: ajusta al valor real del shunt del módulo y la corriente 
// máxima que puede medir sin saturarse (sacado de aliexpress).
#define INA_SHUNT_OHM     0.1
#define INA_MAX_CURRENT_A 0.8

Adafruit_AHTX0 aht;
Adafruit_BMP280 bmp;
Adafruit_VEML7700 veml;
INA226 ina(INA226_ADDR);
SparkFun_AS3935 rayos(AS3935_ADDR);
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

// Interrupción del sensor de rayos
volatile bool as3935_interrupt = false;
// Estado latcheado por la tarea (prioridad): 0=ok, 1=ruido, 2=disturber, 3=rayo
volatile uint8_t rayo_evento = 0;
volatile uint8_t rayo_dist_km = 0;

void IRAM_ATTR onAs3935() {
  as3935_interrupt = true;
}

// Código de prioridad de un evento del AS3935 (rayo > disturber > ruido).
uint8_t _codigoEvento(int ev) {
  switch (ev) {
    case RAYO_INT:    return 3;
    case DISTURBER_INT: return 2;
    case RUIDO_INT:   return 1;
    default:          return 1;
  }
}

// Tarea: atiende la interrupción y latchea el evento por prioridad, para no
// perder un rayo si después llega un disturber/ruido antes del siguiente envío.
// Lee por I2C el registro.
void tareaRayos(void*) {
  for (;;) {
    if (as3935_interrupt) {
      as3935_interrupt = false;
      int ev = rayos.readInterruptReg();
      uint8_t cod = _codigoEvento(ev);
      if (cod >= rayo_evento) {  // no pisar un rayo con algo menor
        rayo_evento = cod;
        if (ev == RAYO_INT) rayo_dist_km = rayos.distanceToStorm();
      }
    }
    vTaskDelay(100 / portTICK_PERIOD_MS); // 100 ms, PROBAR 
  }
}

// Imprime la MAC real del dispositivo (leída de efuse, no depende del estado WiFi).
void printMac(const char* label) {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  Serial.printf("%s: %02X:%02X:%02X:%02X:%02X:%02X\n",
                label, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

#if defined(TRANSPORTE_WIFI)
WiFiManager wifiManager;
AsyncMqttClient mqttClient;
Ticker mqttReconnectTimer;
// Último intento de conexión MQTT desde loop() (reintento periódico)
unsigned long lastMqttAttempt = 0;
#endif
// Contador incremental para medir pérdida de paquetes
uint32_t seq = 0;

// Sensores ambientales: temperatura, humedad, presión, luz y UV (analógico)
void leerAmbientales(JsonObject d) {
  sensors_event_t hum, temp;
  if (aht.getEvent(&hum, &temp)) {
    d["ta"] = temp.temperature;
    d["ha"] = hum.relative_humidity;
  }
  if (bmp.takeForcedMeasurement()) {
    d["pa"] = bmp.readPressure() / 100.0;
  }
  d["lx"] = veml.readLux();
  d["uv"] = analogRead(PIN_ADC_GUVA);  // índice UV, valor ADC crudo
}

// Sensores de suelo: temperatura y humedad (analógico)
void leerSuelo(JsonObject d) {
  ds18b20.requestTemperatures();
  d["ts"] = ds18b20.getTempCByIndex(0);
  d["hs"] = analogRead(PIN_ADC_HIGROMETRO);
}

// Módulo de energía INA226: tensión, corriente y potencia de la batería
void leerEnergia(JsonObject d) {
  d["vb"] = ina.getBusVoltage();
  d["ia"] = ina.getCurrent_mA();
  d["pw"] = ina.getPower_mW();
}

// Detector de rayos AS3935: usa el estado latcheado por tareaRayos (por prioridad).
// Se manda como int (0=ok, 1=ruido, 2=disturber, 3=rayo). Tras reportar se resetea.
void leerRayos(JsonObject d) {
  uint8_t ev = rayo_evento;
  d["re"] = ev;                          // int
  if (ev == 3) d["rd"] = rayo_dist_km;   // distancia solo si hay rayo
  rayo_evento = 0;
  rayo_dist_km = 0;
}

#if defined(TRANSPORTE_WIFI)
void connectToMqtt() {
  Serial.println("Conectando a MQTT...");
  mqttClient.connect();
}

void WiFiEvent(WiFiEvent_t event) {
  Serial.printf("[WiFi-event] %d\n", event);
  switch(event) {
    case ARDUINO_EVENT_WIFI_AP_START:
      Serial.print("AP iniciado IP: ");
      Serial.println(WiFi.softAPIP());
      break;
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      Serial.println("Cliente conectado al AP");
      connectToMqtt();
      break;
    case ARDUINO_EVENT_WIFI_AP_STADISCONNECTED:
      Serial.println("Cliente desconectado del AP");
      break;
    case ARDUINO_EVENT_WIFI_AP_STAIPASSIGNED:
      Serial.println("IP asignada a cliente, conectando MQTT...");
      connectToMqtt();
      break;
    default: break;
  }
}

void onMqttConnect(bool sessionPresent) {
  Serial.println("MQTT conectado");
  mqttClient.publish(MQTT_TOPIC_ESTADO, 1, true, "{\"estado\":\"online\"}");
}

void onMqttDisconnect(AsyncMqttClientDisconnectReason reason) {
  Serial.printf("MQTT desconectado %d\n", (int)reason);
  if (WiFi.softAPgetStationNum() > 0 || WiFi.isConnected()) {
    mqttReconnectTimer.once(2, connectToMqtt);
  }
}
#elif defined(TRANSPORTE_ESP_NOW)
esp_now_peer_info_t peerInfo = {};

void iniciarEspNow() {
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error: no se pudo iniciar ESP-NOW");
    return;
  }
  // Nodo y puente deben estar en el mismo canal.
  esp_wifi_set_channel(ESP_NOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  memcpy(peerInfo.peer_addr, BRIDGE_MAC, 6);
  peerInfo.channel = ESP_NOW_CHANNEL;
  peerInfo.ifidx = WIFI_IF_STA;
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Error: añadiendo peer (puente)");
  }
}
#endif

void setup() {
  // Consola de depuración por USB (Serial)
  Serial.begin(UART_BAUD);
  delay(500);

  // MAC del nodo: cópiala a secrets.h del puente (NODE_MAC)
  printMac("MAC del nodo");

#if defined(TRANSPORTE_WIFI)
  WiFi.onEvent(WiFiEvent);
  Serial.println("Iniciando WiFi...");
  wifiManager.begin();

  mqttClient.onConnect(onMqttConnect);
  mqttClient.onDisconnect(onMqttDisconnect);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCredentials(MQTT_USER, MQTT_PASS);
  mqttClient.setClientId(MQTT_CLIENT_ID);
  mqttClient.setWill(MQTT_TOPIC_ESTADO, 1, true, "{\"estado\":\"offline\"}");
#elif defined(TRANSPORTE_ESP_NOW)
  iniciarEspNow();
#elif defined(TRANSPORTE_MESHTASTIC)
  Serial1.begin(MESHTASTIC_BAUD, SERIAL_8N1, SERIAL1_RX, SERIAL1_TX);
#endif

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  pinMode(PIN_AS3935_IRQ, INPUT);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, HIGH);
  attachInterrupt(digitalPinToInterrupt(PIN_AS3935_IRQ), onAs3935, RISING);

  aht.begin();
  // El BMP280 puede tener dos direcciones
  if (!bmp.begin(BMP280_ADDR)) bmp.begin(BMP280_B_ADDR);
  bmp.setSampling(Adafruit_BMP280::MODE_FORCED);
  veml.begin();
  ina.begin();
  // Calibración del INA226 NECESARIA
  ina.setMaxCurrentShunt(INA_MAX_CURRENT_A, INA_SHUNT_OHM);
  ds18b20.begin();

  if (rayos.begin()) {
    rayos.setIndoorOutdoor(OUTDOOR);
    // Ajustar esto para usarlo realmente
    //rayos.setNoiseLevel(2-4)
    //rayos.watchdogThreshold(2)
    //rayos.spikeRejection(2-3)
    delay(50);

  } else {
    Serial.println("Error: AS3935 no responde");
  }

  // Tarea que latchea los eventos de rayo por prioridad para que no se pierdan.
  xTaskCreate(tareaRayos, "rayos", 4096, NULL, 1, NULL);

  Serial.println("Nodo listo, enviando lecturas");
}

void loop() {
#if defined(TRANSPORTE_WIFI)
  wifiManager.loop();

  // Si hay clientes en el AP y MQTT sigue caído reintenta cada 5 s
  if (!mqttClient.connected() && WiFi.softAPgetStationNum() > 0 &&
      millis() - lastMqttAttempt > 5000) {
    lastMqttAttempt = millis();
    connectToMqtt();
  }
#endif

  JsonDocument doc;
  doc["nid"] = NODE_ID;
  doc["seq"] = seq++;
  doc["t"] = millis() / 1000;
  leerAmbientales(doc.as<JsonObject>());
  leerSuelo(doc.as<JsonObject>());
  leerEnergia(doc.as<JsonObject>());
  leerRayos(doc.as<JsonObject>());

  // Reducir la precisión de los flotantes a 1 decimal: cabe en un paquete LoRa.
  doc["ta"] = roundf((float)doc["ta"] * 10) / 10;
  doc["ha"] = roundf((float)doc["ha"] * 10) / 10;
  doc["pa"] = roundf((float)doc["pa"] * 10) / 10;
  doc["lx"] = roundf((float)doc["lx"] * 10) / 10;
  doc["ts"] = roundf((float)doc["ts"] * 10) / 10;
  // La batería necesita 2 decimales.
  doc["vb"] = roundf((float)doc["vb"] * 100) / 100;
  doc["ia"] = roundf((float)doc["ia"] * 10) / 10;
  doc["pw"] = roundf((float)doc["pw"] * 10) / 10;


#if defined(TRANSPORTE_WIFI)
  // Depuración por USB + MQTT a la estación base
  serializeJson(doc, Serial);
  Serial.println();
  char buffer[600];
  serializeJson(doc, buffer, sizeof(buffer));
  if (mqttClient.connected()) {
    mqttClient.publish(MQTT_TOPIC_TELEMETRIA, 1, false, buffer);
  }
#elif defined(TRANSPORTE_USB)
  // Enlace directo a la base: wrapper {"enlace":{"origen":"usb"},"dato":...}
  char inner[600];
  size_t n = serializeJson(doc, inner, sizeof(inner));
  Serial.printf("{\"enlace\":{\"origen\":\"usb\"},\"dato\":");
  Serial.write(inner, n);
  Serial.println("}");
#elif defined(TRANSPORTE_ESP_NOW)
  // Envío por ESP-NOW al puente (el puente añade el enlace y el RSSI)
  char buffer[600];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  esp_now_send(BRIDGE_MAC, (const uint8_t*)buffer, n);
  // Depuración por USB
  serializeJson(doc, Serial);
  Serial.println();
#elif defined(TRANSPORTE_MESHTASTIC)
  // El JSON ya cabe en un paquete LoRa .
  serializeJson(doc, Serial1);
  Serial1.println();
  // Depuración por USB
  serializeJson(doc, Serial);
  Serial.println();
  // Depuración por USB de lo que se recibe del Faketec (malla LoRa)
  if (Serial1.available()) Serial.write(Serial1.read());
#endif

  // Parpadeo del LED integrado para indicar envío
  digitalWrite(PIN_LED, LOW);
  delay(80);
  digitalWrite(PIN_LED, HIGH);

  delay(INTERVALO_MS);
}

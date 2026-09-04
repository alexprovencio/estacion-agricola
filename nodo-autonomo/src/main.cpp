/**
 * @file
 * @brief Estación Agrícola - Nodo solar autónomo
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-03
 *
 * Práctica final de Sistemas Digitales para el Internet de las Cosas.
 *
 * Lee todos los sensores del nodo y envía las lecturas por el USB
 * en formato JSON para que la estación base las procese.
 *
 * @details
 * Mapa de conexiones (ESP32-C3 Supermini):
 * @code
 *   Todos los módulos van alimentados a 3V3 y con GND común
 *   I2C SDA        <- GPIO0  AHT20+BMP280, VEML7700, INA226 y AS3935
 *   I2C SCL        <- GPIO1  AHT20+BMP280, VEML7700, INA226 y AS3935
 *   AS3935 IRQ     <- GPIO5  Interrupción de detección de rayos
 *   GUVA-S12SD ADC <- GPIO3  Índice UV, entrada analógica
 *   Higrómetro ADC <- GPIO4  Humedad de suelo, entrada analógica
 *   DS18B20 Data   <- GPIO6  Temperatura de suelo, OneWire, pull-up de 4,7 kΩ
 *   INA226 IN+     <- CN3791 BAT+
 *   INA226 IN-     <- 
 *   INA226 VBS     <- 
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
#include <AsyncMqttClient.h>
#include <Ticker.h>
#include "wifi_manager.h"
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

#define UART_BAUD          115200
// Tiempo entre lecturas de los sensores y envío de los datos
#define INTERVALO_MS       4920

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

Adafruit_AHTX0 aht;
Adafruit_BMP280 bmp;
Adafruit_VEML7700 veml;
INA226 ina(INA226_ADDR);
SparkFun_AS3935 rayos(AS3935_ADDR);
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

WiFiManager wifiManager;
AsyncMqttClient mqttClient;
Ticker mqttReconnectTimer;
// Último intento de conexión MQTT desde loop() (reintento periódico)
unsigned long lastMqttAttempt = 0;

// Interrupción del sensor de rayos
volatile bool as3935_interrupt = false;
volatile uint32_t as3935_pulsos = 0;

void IRAM_ATTR onAs3935() {
  as3935_interrupt = true;
  as3935_pulsos++;
}

// Sensores ambientales: temperatura, humedad, presión, luz y UV (analógico)
void leerAmbientales(JsonObject d) {
  sensors_event_t hum, temp;
  if (aht.getEvent(&hum, &temp)) {
    d["temp_amb"] = temp.temperature;
    d["hum_amb"]  = hum.relative_humidity;
  }
  if (bmp.takeForcedMeasurement()) {
    d["presion_hpa"] = bmp.readPressure() / 100.0;
  }
  d["luz_lux"] = veml.readLux();
  d["uv"]     = analogRead(PIN_ADC_GUVA);  // índice UV, valor ADC crudo
}

// Sensores de suelo: temperatura y humedad (analógico)
void leerSuelo(JsonObject d) {
  ds18b20.requestTemperatures();
  d["temp_suelo"] = ds18b20.getTempCByIndex(0);
  d["hum_suelo"]  = analogRead(PIN_ADC_HIGROMETRO);
}

// Módulo de energía INA226: tensión, corriente y potencia de la batería
// No usado de momento porque no tenemos batería PROBARLO
void leerEnergia(JsonObject d) {
  d["v_bat"] = ina.getBusVoltage();
  d["i_ma"]  = ina.getCurrent_mA();
  d["p_mw"]  = ina.getPower_mW();
}

// Detector de rayos AS3935
void leerRayos(JsonObject d) {
  // Ha habido algún evento
  if (as3935_interrupt) {
    as3935_interrupt = false;
    int evento = rayos.readInterruptReg();
    switch (evento) {
      // Es un rayo!
      case RAYO_INT:
        d["estado"] = "rayo";
        d["dist_km"] = rayos.distanceToStorm();
        break;
      // interferencias eléctricas
      case DISTURBER_INT:
        d["estado"] = "disturber";
        break;
      // Nivel de ruido ambiental demasiado alto
      case RUIDO_INT:
        d["estado"] = "ruido";
        break;
      // Esto ocurría cuando estaba mal conectado el pin de interrupción
      default:
        d["estado"] = "desconocido";
        break;
    }
  // Nada detectado
  } else {
    d["estado"] = "ok";
  }
}

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

void setup() {
  // Consola de depuración por USB (Serial)
  Serial.begin(UART_BAUD);
  delay(500);

  WiFi.onEvent(WiFiEvent);
  Serial.println("Iniciando WiFi...");
  wifiManager.begin();

  mqttClient.onConnect(onMqttConnect);
  mqttClient.onDisconnect(onMqttDisconnect);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCredentials(MQTT_USER, MQTT_PASS);
  mqttClient.setClientId(MQTT_CLIENT_ID);
  mqttClient.setWill(MQTT_TOPIC_ESTADO, 1, true, "{\"estado\":\"offline\"}");

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

  Serial.println("Nodo listo, enviando lecturas");
}

void loop() {
  wifiManager.loop();

  // Si hay clientes en el AP y MQTT sigue caído reintenta cada 5 s
  if (!mqttClient.connected() && WiFi.softAPgetStationNum() > 0 &&
      millis() - lastMqttAttempt > 5000) {
    lastMqttAttempt = millis();
    connectToMqtt();
  }

  JsonDocument doc;
  doc["t"] = millis() / 1000;
  leerAmbientales(doc["amb"].to<JsonObject>());
  leerSuelo(doc["suelo"].to<JsonObject>());
  leerEnergia(doc["energia"].to<JsonObject>());
  leerRayos(doc["rayos"].to<JsonObject>());

  // USB para depuración
  serializeJson(doc, Serial);
  // MQTT a la estación base
  char buffer[512];
  serializeJson(doc, buffer, sizeof(buffer));
  if (mqttClient.connected()) {
    mqttClient.publish(MQTT_TOPIC_TELEMETRIA, 1, false, buffer);
  }

  // Parpadeo del LED integrado para indicar envío
  digitalWrite(PIN_LED, LOW);
  Serial.println();
  delay(80);
  digitalWrite(PIN_LED, HIGH);

  delay(INTERVALO_MS);
}

/**
 * @file
 * @brief Estación Agrícola - Nodo solar autónomo
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-08-27
 *
 * Práctica final de Sistemas Digitales para el Internet de las Cosas.
 *
 * Lee todos los sensores del nodo y envía las lecturas por el UART físico
 * (Serial1) hacia la estación base en formato JSON, una lectura por línea.
 * La consola de depuración sale por el USB (Serial) mientras se desarrolla.
 *
 * @details
 * Mapa de conexiones (ESP32-C3 Supermini):
 * @code
 *   I2C SDA      <- GPIO0      AHT20+BMP280, VEML7700, INA226 y AS3935
 *   I2C SCL      <- GPIO1
 *   AS3935 IRQ   <- GPIO5      (interrupción de detección de rayos)
 *   ADC GUVA     GPIO3         (índice UV, entrada analógica)
 *   ADC Higrómetro GPIO4       (humedad de suelo, entrada analógica)
 *   DS18B20 data GPIO6         (temperatura de suelo, OneWire)
 *   UART TX      -> GPIO21     (hacia la estación base)
 *   UART RX      <- GPIO20     (desde la estación base)
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
#include <SparkFun_AS3935.h> // Probar si esta rula

// Pines
#define PIN_I2C_SDA      0
#define PIN_I2C_SCL      1
#define PIN_AS3935_IRQ   5
#define PIN_ADC_GUVA     3
#define PIN_ADC_HIGROMETRO 4
#define PIN_DS18B20      6
#define PIN_UART_RX      20
#define PIN_UART_TX      21

#define UART_BAUD        115200
#define INTERVALO_MS     5000

// Dirección I2C del AS3935
#define AS3935_ADDR      0x03

// Códigos de evento que devuelve el AS3935 al leer su registro de interrupción
#define RAYO_INT         0x08
#define DISTURBER_INT    0x04
#define RUIDO_INT        0x01

Adafruit_AHTX0 aht;
Adafruit_BMP280 bmp;
Adafruit_VEML7700 veml;
// La dirección del INA226 es 0x40 por defecto
INA226 ina(0x40);
SparkFun_AS3935 rayos(AS3935_ADDR);
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

// Interrupción del sensor de rayos
volatile bool as3935_interrupt = false;
volatile uint32_t as3935_pulsos = 0;

void IRAM_ATTR onAs3935() {
  as3935_interrupt = true;
  as3935_pulsos++;
}

// Sensores ambientales: temperatura, humedad, presión y luz
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
}

// Módulo de energía INA226: tensión, corriente y potencia de la batería
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
      // Es un rayo
      case RAYO_INT:
        d["estado"] = "rayo";
        d["dist_km"] = rayos.distanceToStorm();
        break;
      // Es una falsa detección
      case DISTURBER_INT:
        d["estado"] = "disturber";
        break;
      // Es ruido
      case RUIDO_INT:
        d["estado"] = "ruido";
        break;
      default:
        d["estado"] = "desconocido";
        break;
    }
  // Nada detectado
  } else {
    d["estado"] = "ok";
  }
}

// Devuelve la frecuencia medida en kHz para calibrar el AS3935 sin osciloscopio
float calibrarRayos() {
  rayos.changeDivRatio(128);
  rayos.displayOscillator(true, 3);  // LCO (frecuencia de la antena) -> IRQ
  as3935_pulsos = 0;
  as3935_interrupt = false;
  delay(1000);
  float fAntena = as3935_pulsos * 128.0 / 1000.0;  // kHz
  rayos.displayOscillator(false, 3);
  as3935_interrupt = false;
  return fAntena;
}

void setup() {
  // Consola de depuración por USB (Serial)
  Serial.begin(UART_BAUD);
  // Enlace con la estación base por el UART físico (Serial1)
  Serial1.begin(UART_BAUD, SERIAL_8N1, PIN_UART_RX, PIN_UART_TX);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  pinMode(PIN_AS3935_IRQ, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_AS3935_IRQ), onAs3935, RISING);

  aht.begin();
  bmp.begin(0x76); // Comprobar que la dirección está bien
  bmp.setSampling(Adafruit_BMP280::MODE_FORCED);
  veml.begin();
  ina.begin();
  ds18b20.begin();

  if (rayos.begin()) {
    rayos.setIndoorOutdoor(OUTDOOR);
    delay(50);

    // Comprobación de la sintonía de la antena, debe ser unos 500 kHz
    float fAntena = calibrarRayos();
    Serial.printf("AS3935 listo (exterior), antena ~%.0f kHz\n", fAntena);
    if (fAntena < 482.5f || fAntena > 517.5f) {
      Serial.println("ATENCION: antena fuera de rango, calibrar!");
    }
  } else {
    Serial.println("Error: AS3935 no responde");
  }

  Serial.println("Nodo listo, enviando lecturas");
}

void loop() {
  ds18b20.requestTemperatures();

  JsonDocument doc;
  doc["t"] = millis() / 1000;
  leerAmbientales(doc["amb"].to<JsonObject>());
  leerEnergia(doc["energia"].to<JsonObject>());
  leerRayos(doc["rayos"].to<JsonObject>());
  doc["temp_suelo"] = ds18b20.getTempCByIndex(0);
  doc["hum_suelo"]  = analogRead(PIN_ADC_HIGROMETRO);
  doc["uv"]         = analogRead(PIN_ADC_GUVA);

  serializeJson(doc, Serial1);
  Serial1.println();
  serializeJson(doc, Serial);   // eco en consola USB mientras se depura
  Serial.println();

  delay(INTERVALO_MS);
}

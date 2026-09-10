/**
 * @file
 * @brief Estación Agrícola - Estación auxiliar (Cheap Yellow Display)
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-09
 *
 * Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.
 *
 * Muestra las variables del nodo autónomo conectándose al broker MQTT local
 * de la estación base (sin TLS porque la librería no lo soporta).
 *
 *   WiFi -> AsyncMqttClient -> esagrau/nodos/+/telemetria -> display
 */

#include <WiFi.h>
#include <ArduinoJson.h>
#include <AsyncMqttClient.h>
#include <TFT_eSPI.h>

#include "secrets.h"

#ifndef MQTT_TOPIC_ESTADO
#define MQTT_TOPIC_ESTADO "esagrau/base/estado"
#endif

TFT_eSPI tft = TFT_eSPI();
AsyncMqttClient mqtt;

// Valores recibidos
float ta = NAN, ha = NAN, pa = NAN, lx = NAN, ts = NAN, hs = NAN,
      vb = NAN, ia = NAN, pw = NAN, rd = NAN;
int uv = -999, re = -999;
char nid[24] = "";
volatile bool hayDato = false;
byte releEstado[4] = {0, 0, 0, 0};
volatile bool hayReles = false;

// Backlight del CYD
#define TFT_BL 21

// Calibración del higrómetro como en la base
#define HUM_ADC_SECO 4095
#define HUM_ADC_SATURADO 1800

// Convierte la lectura analógica del higrómetro de suelo a porcentaje (0-100%)
int humSueloPct(int raw) {
  int rango = HUM_ADC_SECO - HUM_ADC_SATURADO;
  if (rango <= 0) return 0;
  int pct = (HUM_ADC_SECO - raw) * 100 / rango;
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

// Dibuja los valores en la pantalla
void dibujar() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);

  // 28 px de alto por línea, 8 px de margen
  tft.drawString("Nodo: " + String(nid), 4, 4);
  tft.drawString("T " + String(ta, 1) + " C   H " + String(ha, 0) + "%", 4, 32);
  tft.drawString("P " + String(pa, 1) + " hPa", 4, 60);
  tft.drawString("Luz " + String(lx, 0) + " lux   UV " + String(uv), 4, 88);
  tft.drawString("Suelo " + String(ts, 1) + " C  Hum " +
                 String(isnan(hs) ? 0 : humSueloPct((int)hs)) + "%", 4, 116);
  tft.drawString("Bat " + String(vb, 2) + " V  " + String(ia, 1) + " mA", 4, 144);
  const char* rayose = (re == 3) ? "RAYO" : (re == 2) ? "DISTURBER"
                    : (re == 1) ? "RUIDO" : "OK";
  tft.drawString("Rayos " + String(rayose) +
                 (re == 3 ? "  " + String(rd, 0) + "km" : ""), 4, 172);
  if (hayReles) {
    const char* s1 = releEstado[0] ? "ON " : "OFF";
    const char* s2 = releEstado[1] ? "ON " : "OFF";
    const char* s3 = releEstado[2] ? "ON " : "OFF";
    const char* s4 = releEstado[3] ? "ON " : "OFF";
    tft.drawString(String("R ") + s1 + s2 + s3 + s4, 4, 200);
  }
}

// Función llamada cuando se recibe un mensaje MQTT
void onMessage(char* topic, char* payload, AsyncMqttClientMessageProperties properties,
               size_t len, size_t index, size_t total) {
  if (index > 0) return;  // solo primer fragmento

  // Estado de los relés (esagrau/base/estado): {"rele_1":0/1, ...}
  if (strcmp(topic, MQTT_TOPIC_ESTADO) == 0) {
    JsonDocument doc;
    if (deserializeJson(doc, payload, len)) return;
    char k[8];
    for (int i = 0; i < 4; i++) {
      snprintf(k, sizeof(k), "rele_%d", i + 1);
      releEstado[i] = doc[k] | 0;
    }
    hayReles = true;
    return;
  }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, len);
  if (err) return;
  // El broker envuelve el payload en {"enlace":{...},"dato":{...}}:
  // leer de "dato" si existe, si no del propio documento y así no hay fallos.
  JsonObject d = doc["dato"].is<JsonObject>() ? doc["dato"].as<JsonObject>() : doc.as<JsonObject>();
  ta = d["ta"] | NAN; ha = d["ha"] | NAN; pa = d["pa"] | NAN;
  lx = d["lx"] | NAN; ts = d["ts"] | NAN; hs = d["hs"] | NAN;
  vb = d["vb"] | NAN; ia = d["ia"] | NAN; pw = d["pw"] | NAN;
  rd = d["rd"] | NAN;
  uv = d["uv"] | -999; re = d["re"] | -999;
  snprintf(nid, sizeof(nid), "%s", d["nid"] | "?");
  hayDato = true;
}

// Función llamada cuando se conecta al broker MQTT
void onMqttConnect(bool sessionPresent) {
  Serial.println("MQTT conectado");
  mqtt.subscribe(MQTT_TOPIC, 1);
  mqtt.subscribe(MQTT_TOPIC_ESTADO, 1);
}

// Función llamada cuando se desconecta del broker MQTT
void onMqttDisconnect(AsyncMqttClientDisconnectReason reason) {
  Serial.printf("MQTT desconectado, motivo=%d\n", (int)reason);
}

void setup() {
  Serial.begin(115200);
  delay(200); // Nunca está de más

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  delay(100);  // Espera a que el panel estabilice antes de inicializar
  tft.init();
  tft.setRotation(1);  // landscape 320x240 FUNCIONA
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  
  // WiFi
  tft.drawString("WiFi...", 8, 8);
  Serial.printf("Conectando WiFi %s...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(300); }
  Serial.println("WiFi OK");
  tft.drawString("WiFi OK", 8, 8);
  
  // MQTT
  tft.drawString("Conectando...", 8, 40);
  Serial.printf("MQTT %s:%d\n", MQTT_HOST, MQTT_PORT);
  mqtt.onConnect(onMqttConnect);
  mqtt.onDisconnect(onMqttDisconnect);
  mqtt.onMessage(onMessage);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCredentials(MQTT_USER, MQTT_PASS);
  mqtt.setClientId(MQTT_CLIENT_ID);
  mqtt.setKeepAlive(60);
  mqtt.setWill("esagrau/aux/estado", 1, true, "{\"estado\":\"offline\"}");
  mqtt.connect();

  Serial.println("Estación auxiliar lista");
}

void loop() {
  if (hayDato) { dibujar(); hayDato = false; }
  delay(200);
}

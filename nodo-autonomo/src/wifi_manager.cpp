/**
 * @file
 * @brief Estación Agrícola - WiFi AP
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-03
 *
 * Práctica final de Sistemas Digitales para el Internet de las Cosas.
 *
 * La configuración se realiza en secrets.h.
 * 
 */

#include "wifi_manager.h"
#include <WiFi.h>

#include "secrets.h"

#ifndef WIFI_SSID
#define WIFI_SSID "NodoAutonomo"
#endif
#ifndef WIFI_PASS
#define WIFI_PASS "12345678"
#endif

static const IPAddress AP_IP(192, 168, 4, 1);
static const IPAddress AP_GW(192, 168, 4, 1);
static const IPAddress AP_SN(255, 255, 255, 0);

bool WiFiManager::begin() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_GW, AP_SN);
  bool ok = WiFi.softAP(WIFI_SSID, WIFI_PASS);
  if (ok) {
    Serial.printf("WiFi AP '%s' iniciado en %s\n", WIFI_SSID, AP_IP.toString().c_str());
  } else {
    Serial.println("Error iniciando WiFi AP");
  }
  return ok;
}

bool WiFiManager::isConnected() {
  // En modo AP siempre está "conectado" si hay al menos softAP
  return WiFi.getMode() & WIFI_MODE_AP;
}

void WiFiManager::loop() {
  // Para AP no hay reconexión que gestionar
}

IPAddress WiFiManager::getIP() const {
  return WiFi.softAPIP();
}

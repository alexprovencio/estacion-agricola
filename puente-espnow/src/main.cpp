/**
 * @file
 * @brief Estación Agrícola - Puente ESP-NOW
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-08
 *
 * Práctica final de Comunicaciones Inalámbricas y Protocolos para el IoT.
 *
 * ESP32-C3 conectado a la estación base por USB-CDC. Recibe la telemetría del
 * nodo autónomo por ESP-NOW y la reenvía por el puerto serie (USB-CDC) para 
 * que la base la inyecte en su broker MQTT local:
 *
 *   {"enlace":{"origen":"espnow","rssi_dbm":-55},"dato":{...}}
 *
 * El canal y la MAC del nodo se configuran en secrets.h.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include "esp_mac.h"

#include "secrets.h"

// Imprime la MAC real del dispositivo (leída de efuse, no depende del estado WiFi).
void printMac(const char* label) {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  Serial.printf("%s: %02X:%02X:%02X:%02X:%02X:%02X\n",
                label, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

// Solo acepta la telemetría del nodo configurado en secrets.h.
// info->rx_ctrl->rssi es la señal recibida del enlace ESP-NOW.
void onRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (memcmp(info->src_addr, NODE_MAC, 6) != 0) {
    // Imprimimos la MAC si es una desconocida (bueno para configurar).
    Serial.printf("MAC desconocida: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  info->src_addr[0], info->src_addr[1], info->src_addr[2],
                  info->src_addr[3], info->src_addr[4], info->src_addr[5]);
    return;
  }
  // Wrapper con el RSSI del enlace. El dato se reenvía literal para no perder
  // precisión en los flotantes del JSON.
  Serial.printf("{\"enlace\":{\"origen\":\"espnow\",\"rssi_dbm\":%d},\"dato\":",
                info->rx_ctrl->rssi);
  Serial.write(data, len);
  Serial.println("}");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  printMac("MAC del puente");

  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error: no se pudo iniciar ESP-NOW");
    return;
  }
  // Nodo y puente deben estar en el mismo canal.
  esp_wifi_set_channel(ESP_NOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_now_register_recv_cb(onRecv);

  Serial.println("Puente ESP-NOW listo");
}

void loop() {
  // La recepción se gestiona por callback.
}

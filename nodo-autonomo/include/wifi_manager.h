/**
 * @file
 * @brief Estación Agrícola - Interfaz para el WiFi
 * @author Alejandro Provencio Sanz <aprovenci9@alumno.uned.es>
 * @date 2026-09-03
 *
 * Práctica final de Sistemas Digitales para el Internet de las Cosas.
 *
 *
 */

#pragma once
#include <Arduino.h>

class WiFiManager {
public:
  // Inicia el WiFi en modo AP
  bool begin();

  // Devuelve true si la red está levantada
  bool isConnected();

  // Llamar en cada loop para gestionar reconexión
  void loop();

  // IP del AP (normalmente 192.168.4.1)
  IPAddress getIP() const;
};

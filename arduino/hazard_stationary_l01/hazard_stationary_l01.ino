#include <Arduino.h>
#include <BLEAdvertising.h>
#include <BLEDevice.h>
#include <BLEUtils.h>

/*
 * Node hazard stasioner untuk mesin diam (misal Laser Cutter LSR01 atau Gerinda GRD01).
 *
 * Standar Reksa Industrial Beacon (11 karakter, ultra-fast zero-overhead):
 * Format: RK_[CAT]_[TYP][NN]
 * RK_S_LSR01 -> Stationary Hazard, Laser Cutter Unit 01.
 * Helm mendeteksi awalan "RK_" dan mengklasifikasikan kategori dalam hitungan nanodetik.
 * (Legacy format: REKSA_HAZARD_L01 tetap didukung sebagai fallback).
 */

const char *HAZARD_NAME = "RK_S_LSR01";
BLEAdvertising *advertising = nullptr;

const int BUTTON_PIN = 25;
const int LED_PIN = 2;
bool isAdvertising = true;
bool lastButtonState = HIGH;

void startAdvertising() {
  BLEAdvertisementData advertisementData;
  BLEAdvertisementData scanResponseData;

  advertisementData.setFlags(0x06);
  scanResponseData.setName(HAZARD_NAME);

  advertising->setAdvertisementData(advertisementData);
  advertising->setScanResponseData(scanResponseData);
  advertising->setScanResponse(true);

  // Interval BLE untuk mesin stasioner (160ms - 240ms)
  // 0x0100 = 160 ms, 0x0180 = 240 ms
  advertising->setMinInterval(0x0100);
  advertising->setMaxInterval(0x0180);

  advertising->start();
  Serial.println("BLE Stationary Hazard ON - Mesin Aktif");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);

  Serial.println("\nMemulai REKSA Stationary Hazard Node (Laser/Mesin)...");
  Serial.print("Nama BLE: ");
  Serial.println(HAZARD_NAME);

  BLEDevice::init(HAZARD_NAME);
  advertising = BLEDevice::getAdvertising();

  startAdvertising();
  digitalWrite(LED_PIN, HIGH);
}

void loop() {
  bool currentButtonState = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(50);
    if (digitalRead(BUTTON_PIN) == LOW) {
      if (isAdvertising) {
        advertising->stop();
        digitalWrite(LED_PIN, LOW);
        Serial.println("Mesin Standby / OFF - BLE Hazard Dihentikan");
      } else {
        advertising->start();
        digitalWrite(LED_PIN, HIGH);
        Serial.println("Mesin Operasi / ON - BLE Hazard Diaktifkan");
      }
      isAdvertising = !isAdvertising;
    }
  }

  lastButtonState = currentButtonState;

  static unsigned long lastStatusAt = 0;
  if (millis() - lastStatusAt >= 5000) {
    lastStatusAt = millis();
    if (isAdvertising) {
      Serial.println("Stationary hazard beacon aktif.");
    } else {
      Serial.println("Stationary hazard sedang standby.");
    }
  }

  delay(50);
}

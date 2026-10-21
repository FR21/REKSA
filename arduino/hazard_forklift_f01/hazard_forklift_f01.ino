#include <Arduino.h>
#include <BLEAdvertising.h>
#include <BLEDevice.h>
#include <BLEUtils.h>

/*
 * Standar Reksa Industrial Beacon (11 karakter, ultra-fast zero-overhead):
 * Format: RK_[CAT]_[TYP][NN]
 * RK_M_FLK01 -> Mobile Hazard, Forklift Unit 01.
 * Helm mendeteksi awalan "RK_" dan mengklasifikasikan kategori dalam hitungan nanodetik.
 * (Legacy format: REKSA_HAZARD_F01 tetap didukung sebagai fallback).
 */

const char *HAZARD_NAME = "RK_M_FLK01";
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

  /*
   * Interval lebih pendek membuat helm lebih cepat melihat forklift.
   * Nilai BLE memakai unit 0.625 ms.
   * 0x00A0 = 100 ms.
   */
  advertising->setMinInterval(0x00A0);
  advertising->setMaxInterval(0x00F0);

  advertising->start();
  Serial.println("BLE Sender ON - Hazard Aktif");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);

  Serial.println("\nMemulai REKSA Forklift Hazard Node...");
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
        Serial.println("BLE Sender OFF - Hazard Dimatikan");
      } else {
        advertising->start();
        digitalWrite(LED_PIN, HIGH);
        Serial.println("BLE Sender ON - Hazard Diaktifkan");
      }
      isAdvertising = !isAdvertising;
    }
  }

  lastButtonState = currentButtonState;

  static unsigned long lastStatusAt = 0;
  if (millis() - lastStatusAt >= 5000) {
    lastStatusAt = millis();
    if (isAdvertising) {
      Serial.println("BLE advertising aktif. Mengirim sinyal hazard...");
    } else {
      Serial.println("BLE sender sedang dimatikan (Standby).");
    }
  }

  delay(50);
}

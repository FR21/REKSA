#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

/*
 * Node hazard untuk forklift F01.
 *
 * Helm mendeteksi perangkat BLE yang namanya diawali:
 * REKSA_HAZARD_
 *
 * ID setelah prefix ini akan dikirim helm ke web sebagai hazard_id.
 * Contoh:
 * REKSA_HAZARD_F01 -> hazard_id F01 -> Forklift Alpha di dashboard.
 */

const char* HAZARD_NAME = "REKSA_HAZARD_F01";

BLEAdvertising* advertising = nullptr;

void startAdvertising() {
  BLEAdvertisementData advertisementData;
  BLEAdvertisementData scanResponseData;

  advertisementData.setFlags(0x06);
  scanResponseData.setName(HAZARD_NAME);

  advertising->setAdvertisementData(advertisementData);
  advertising->setScanResponseData(scanResponseData);
  advertising->setScanResponse(true);


  advertising->setMinInterval(0x00A0);
  advertising->setMaxInterval(0x00F0);

  advertising->start();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("Memulai REKSA Forklift Hazard Node...");
  Serial.print("Nama BLE: ");
  Serial.println(HAZARD_NAME);

  BLEDevice::init(HAZARD_NAME);
  advertising = BLEDevice::getAdvertising();

  startAdvertising();

  Serial.println("Forklift hazard node aktif.");
}

void loop() {
  static unsigned long lastStatusAt = 0;

  if (millis() - lastStatusAt >= 5000) {
    lastStatusAt = millis();
    Serial.println("BLE advertising aktif.");
  }

  delay(100);
}

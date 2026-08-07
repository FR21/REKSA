#include <Arduino.h>

// Library BLE bawaan ESP32
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

// Library DHT22
#include <DHT.h>

// Library WiFi & MQTT
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <Wire.h>

// =====================================================
// IDENTITAS PERANGKAT
// =====================================================

const char* HELMET_NAME = "REKSA_HELMET_W01";
const char* WORKER_ID = "W01"; // ID Pekerja untuk Topic MQTT
const char* HAZARD_PREFIX = "REKSA_HAZARD_";

// =====================================================
// KONFIGURASI WIFI & MQTT
// =====================================================

const char* WIFI_SSID = "Shaaapayaaa";
const char* WIFI_PASSWORD = "abcd12345";
const char* MQTT_SERVER = "10.168.239.41"; // Ganti dengan IP Host/Broker
const int MQTT_PORT = 1883;
const char* NTP_SERVER = "pool.ntp.org";
constexpr long GMT_OFFSET_SECONDS = 0;
constexpr int DAYLIGHT_OFFSET_SECONDS = 0;

WiFiClient espClient;
PubSubClient mqttClient(espClient);
bool timeSyncStarted = false;
constexpr uint16_t MQTT_BUFFER_SIZE = 1536;

// =====================================================
// KONFIGURASI PIN
// =====================================================

constexpr uint8_t DHT_PIN = 18;
constexpr uint8_t DHT_TYPE = DHT22;

constexpr uint8_t BUZZER_PIN = 19;
constexpr uint8_t VIBRATION_PIN = 23;

constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint8_t MQ135_ADC_PIN = 34;

/*
 * Atur menjadi true apabila modul aktif saat pin LOW.
 * Jika modul langsung menyala saat boot, coba ubah nilai modul terkait.
 */
constexpr bool BUZZER_ACTIVE_LOW = true;
constexpr bool VIBRATION_ACTIVE_LOW = false;

/*
 * Set true hanya untuk menguji buzzer dan vibration saat ESP32 menyala.
 * Setelah modul terbukti bekerja, ubah kembali menjadi false.
 */
constexpr bool RUN_OUTPUT_SELF_TEST = false;

// =====================================================
// KONFIGURASI DHT22
// =====================================================

constexpr unsigned long DHT_READ_INTERVAL_MS = 2500;
DHT dht(DHT_PIN, DHT_TYPE);

float latestTemperature = NAN;
float latestHumidity = NAN;
bool dhtValid = false;
unsigned long lastDhtReadAt = 0;

// =====================================================
// KONFIGURASI MPU6050 DAN MQ135
// =====================================================

constexpr uint8_t MPU6050_ADDRESS = 0x68;
constexpr uint8_t MPU6050_PWR_MGMT_1 = 0x6B;
constexpr uint8_t MPU6050_GYRO_CONFIG = 0x1B;
constexpr uint8_t MPU6050_ACCEL_CONFIG = 0x1C;
constexpr uint8_t MPU6050_ACCEL_XOUT_H = 0x3B;

constexpr float STANDARD_GRAVITY = 9.80665;
constexpr float MPU6050_ACCEL_SCALE = 4096.0; // +-8g
constexpr float MPU6050_GYRO_SCALE = 65.5; // +-500 deg/s
constexpr float IMPACT_THRESHOLD_G = 3.5;
constexpr float FALL_FREEFALL_THRESHOLD_G = 0.45;
constexpr float FALL_TILT_THRESHOLD_DEG = 60.0;
constexpr unsigned long SENSOR_READ_INTERVAL_MS = 250;

constexpr int MQ135_MODERATE_THRESHOLD = 1200;
constexpr int MQ135_POOR_THRESHOLD = 1800;
constexpr int MQ135_DANGEROUS_THRESHOLD = 2500;

struct MotionData {
  bool valid;
  float accelX;
  float accelY;
  float accelZ;
  float gyroX;
  float gyroY;
  float gyroZ;
  float pitch;
  float roll;
  float yaw;
  float impactG;
  bool impactDetected;
  bool fallDetected;
};

MotionData latestMotion = {
  false,
  0.0,
  0.0,
  STANDARD_GRAVITY,
  0.0,
  0.0,
  0.0,
  0.0,
  0.0,
  0.0,
  1.0,
  false,
  false
};

bool mpu6050Ready = false;
int latestMq135Raw = 0;
const char* latestAirQualityLevel = "UNKNOWN";
bool latestGasAlert = false;
unsigned long lastSensorReadAt = 0;

// =====================================================
// KONFIGURASI BLE DAN HAZARD
// =====================================================

constexpr uint8_t MAX_HAZARDS = 10;
constexpr uint8_t BLE_SCAN_SECONDS = 1;
constexpr unsigned long HAZARD_TIMEOUT_MS = 6000;

// Threshold awal dari rancangan REKSA.
// Kalibrasikan kembali berdasarkan hasil pengujian jarak.
constexpr int RSSI_CRITICAL_THRESHOLD = -65;
constexpr int RSSI_HIGH_THRESHOLD = -75;
constexpr int RSSI_MODERATE_THRESHOLD = -85;

// RSSI smoothing dan stabilisasi perubahan zona.
constexpr uint8_t RSSI_WINDOW_SIZE = 5;
constexpr uint8_t REQUIRED_CONSECUTIVE_READINGS = 2;
constexpr int RSSI_HYSTERESIS_DB = 3;

BLEScan* bleScan = nullptr;

// =====================================================
// KONFIGURASI POLA WARNING
// =====================================================

// HIGH: buzzer dan vibration berdenyut cepat.
constexpr unsigned long HIGH_ON_MS = 200;
constexpr unsigned long HIGH_OFF_MS = 100;

// CRITICAL tidak memakai interval karena buzzer dan vibration
// menyala terus selama zona masih CRITICAL.

// Nilai ini dibaca oleh task warning.
volatile uint8_t currentWarningPriority = 0;

// =====================================================
// TIPE DATA
// =====================================================

enum class ProximityZone : uint8_t {
  ZONE_UNKNOWN = 0,
  ZONE_SAFE = 1,
  ZONE_MODERATE = 2,
  ZONE_HIGH = 3,
  ZONE_CRITICAL = 4
};

struct HazardData {
  bool used;

  String name;
  String macAddress;

  int rawRssi;
  int smoothedRssi;

  int rssiBuffer[RSSI_WINDOW_SIZE];
  long rssiSum;
  uint8_t rssiCount;
  uint8_t rssiIndex;

  ProximityZone zone;
  ProximityZone candidateZone;
  uint8_t candidateCount;

  unsigned long lastSeen;
};

HazardData hazards[MAX_HAZARDS];

// =====================================================
// KONTROL OUTPUT
// =====================================================

void setModuleOutput(uint8_t pin, bool active, bool activeLow) {
  const uint8_t outputLevel = active
    ? (activeLow ? LOW : HIGH)
    : (activeLow ? HIGH : LOW);

  digitalWrite(pin, outputLevel);
}

void setBuzzer(bool active) {
  setModuleOutput(BUZZER_PIN, active, BUZZER_ACTIVE_LOW);
}

void setVibration(bool active) {
  setModuleOutput(
    VIBRATION_PIN,
    active,
    VIBRATION_ACTIVE_LOW
  );
}

void stopAllWarnings() {
  setBuzzer(false);
  setVibration(false);
}

void testWarningModules() {
  Serial.println();
  Serial.println("Memulai self-test output...");

  Serial.println("Tes vibration");
  setVibration(true);
  delay(700);
  setVibration(false);
  delay(300);

  Serial.println("Tes buzzer");
  setBuzzer(true);
  delay(700);
  setBuzzer(false);
  delay(300);

  Serial.println("Tes buzzer dan vibration");
  setBuzzer(true);
  setVibration(true);
  delay(700);

  stopAllWarnings();
  Serial.println("Self-test selesai");
}

// =====================================================
// UTILITAS ZONA
// =====================================================

const char* zoneToString(ProximityZone zone) {
  switch (zone) {
    case ProximityZone::ZONE_SAFE:
      return "SAFE";

    case ProximityZone::ZONE_MODERATE:
      return "MODERATE";

    case ProximityZone::ZONE_HIGH:
      return "HIGH";

    case ProximityZone::ZONE_CRITICAL:
      return "CRITICAL";

    default:
      return "UNKNOWN";
  }
}

uint8_t getZonePriority(ProximityZone zone) {
  return static_cast<uint8_t>(zone);
}

ProximityZone determineRawZone(int rssi) {
  if (rssi >= RSSI_CRITICAL_THRESHOLD) {
    return ProximityZone::ZONE_CRITICAL;
  }

  if (rssi >= RSSI_HIGH_THRESHOLD) {
    return ProximityZone::ZONE_HIGH;
  }

  if (rssi >= RSSI_MODERATE_THRESHOLD) {
    return ProximityZone::ZONE_MODERATE;
  }

  return ProximityZone::ZONE_SAFE;
}

/*
 * Hysteresis mencegah zona berubah cepat ketika RSSI berada dekat batas.
 *
 * Dengan hysteresis 3 dBm:
 * - CRITICAL baru turun jika RSSI lebih kecil dari -68 dBm.
 * - HIGH baru turun jika RSSI lebih kecil dari -78 dBm.
 * - MODERATE baru turun jika RSSI lebih kecil dari -88 dBm.
 */

ProximityZone determineZoneWithHysteresis(
  int rssi,
  ProximityZone currentZone
) {
  if (currentZone == ProximityZone::ZONE_UNKNOWN) {
    return determineRawZone(rssi);
  }

  switch (currentZone) {
    case ProximityZone::ZONE_SAFE:
      return determineRawZone(rssi);

    case ProximityZone::ZONE_MODERATE:
      if (
        rssi <
        RSSI_MODERATE_THRESHOLD - RSSI_HYSTERESIS_DB
      ) {
        return ProximityZone::ZONE_SAFE;
      }

      if (rssi >= RSSI_CRITICAL_THRESHOLD) {
        return ProximityZone::ZONE_CRITICAL;
      }

      if (rssi >= RSSI_HIGH_THRESHOLD) {
        return ProximityZone::ZONE_HIGH;
      }

      return ProximityZone::ZONE_MODERATE;

    case ProximityZone::ZONE_HIGH:
      if (rssi >= RSSI_CRITICAL_THRESHOLD) {
        return ProximityZone::ZONE_CRITICAL;
      }

      if (
        rssi <
        RSSI_HIGH_THRESHOLD - RSSI_HYSTERESIS_DB
      ) {
        return determineRawZone(rssi);
      }

      return ProximityZone::ZONE_HIGH;

    case ProximityZone::ZONE_CRITICAL:
      if (
        rssi <
        RSSI_CRITICAL_THRESHOLD - RSSI_HYSTERESIS_DB
      ) {
        return determineRawZone(rssi);
      }

      return ProximityZone::ZONE_CRITICAL;

    default:
      return determineRawZone(rssi);
  }
}

// =====================================================
// PENGELOLAAN DATA HAZARD
// =====================================================

void resetHazard(HazardData& hazard) {
  hazard.used = false;

  hazard.name = "";
  hazard.macAddress = "";

  hazard.rawRssi = -100;
  hazard.smoothedRssi = -100;

  hazard.rssiSum = 0;
  hazard.rssiCount = 0;
  hazard.rssiIndex = 0;

  for (uint8_t i = 0; i < RSSI_WINDOW_SIZE; i++) {
    hazard.rssiBuffer[i] = -100;
  }

  hazard.zone = ProximityZone::ZONE_UNKNOWN;
  hazard.candidateZone = ProximityZone::ZONE_UNKNOWN;
  hazard.candidateCount = 0;

  hazard.lastSeen = 0;
}

int findHazardIndex(const String& macAddress) {
  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    if (
      hazards[i].used &&
      hazards[i].macAddress == macAddress
    ) {
      return i;
    }
  }

  return -1;
}

int findEmptySlot() {
  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    if (!hazards[i].used) {
      return i;
    }
  }

  return -1;
}

void addRssiReading(HazardData& hazard, int rssi) {
  hazard.rawRssi = rssi;

  const uint8_t slot = hazard.rssiIndex;

  if (hazard.rssiCount < RSSI_WINDOW_SIZE) {
    hazard.rssiBuffer[slot] = rssi;
    hazard.rssiSum += rssi;
    hazard.rssiCount++;
  } else {
    hazard.rssiSum -= hazard.rssiBuffer[slot];
    hazard.rssiBuffer[slot] = rssi;
    hazard.rssiSum += rssi;
  }

  hazard.rssiIndex =
    (hazard.rssiIndex + 1) % RSSI_WINDOW_SIZE;

  hazard.smoothedRssi = static_cast<int>(
    round(
      static_cast<float>(hazard.rssiSum) /
      static_cast<float>(hazard.rssiCount)
    )
  );
}

void updateStableZone(HazardData& hazard) {
  if (
    hazard.rssiCount <
    REQUIRED_CONSECUTIVE_READINGS
  ) {
    return;
  }

  const ProximityZone nextZone =
    determineZoneWithHysteresis(
      hazard.smoothedRssi,
      hazard.zone
    );

  if (nextZone == hazard.zone) {
    hazard.candidateZone = hazard.zone;
    hazard.candidateCount = 0;
    return;
  }

  if (nextZone == hazard.candidateZone) {
    hazard.candidateCount++;
  } else {
    hazard.candidateZone = nextZone;
    hazard.candidateCount = 1;
  }

  if (
    hazard.candidateCount >=
    REQUIRED_CONSECUTIVE_READINGS
  ) {
    const ProximityZone previousZone = hazard.zone;

    hazard.zone = hazard.candidateZone;
    hazard.candidateCount = 0;

    Serial.print("Perubahan zona ");
    Serial.print(hazard.name);
    Serial.print(": ");
    Serial.print(zoneToString(previousZone));
    Serial.print(" -> ");
    Serial.println(zoneToString(hazard.zone));
  }
}

void updateHazard(
  const String& name,
  const String& macAddress,
  int rssi
) {
  int index = findHazardIndex(macAddress);

  if (index == -1) {
    index = findEmptySlot();

    if (index == -1) {
      Serial.println(
        "Penyimpanan hazard penuh."
      );
      return;
    }

    resetHazard(hazards[index]);

    hazards[index].used = true;
    hazards[index].name = name;
    hazards[index].macAddress = macAddress;
    hazards[index].zone = ProximityZone::ZONE_SAFE;
    hazards[index].candidateZone = ProximityZone::ZONE_SAFE;

    Serial.println();
    Serial.print("Hazard baru ditemukan: ");
    Serial.println(name);
  }

  addRssiReading(hazards[index], rssi);
  updateStableZone(hazards[index]);
  hazards[index].lastSeen = millis();
}

void removeInactiveHazards() {
  const unsigned long currentTime = millis();

  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    if (!hazards[i].used) {
      continue;
    }

    if (
      currentTime - hazards[i].lastSeen >
      HAZARD_TIMEOUT_MS
    ) {
      Serial.print("Hazard tidak aktif: ");
      Serial.println(hazards[i].name);

      resetHazard(hazards[i]);
    }
  }
}

// =====================================================
// CALLBACK BLE
// =====================================================

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
  void onResult(
    BLEAdvertisedDevice advertisedDevice
  ) override {
    if (!advertisedDevice.haveName()) {
      return;
    }

    const String deviceName =
      advertisedDevice.getName().c_str();

    if (!deviceName.startsWith(HAZARD_PREFIX)) {
      return;
    }

    const String macAddress =
      advertisedDevice
        .getAddress()
        .toString()
        .c_str();

    updateHazard(
      deviceName,
      macAddress,
      advertisedDevice.getRSSI()
    );
  }
};

// =====================================================
// DHT22
// =====================================================

void updateDHT22() {
  const unsigned long currentTime = millis();

  if (
    lastDhtReadAt != 0 &&
    currentTime - lastDhtReadAt <
    DHT_READ_INTERVAL_MS
  ) {
    return;
  }

  lastDhtReadAt = currentTime;

  const float humidity = dht.readHumidity();
  const float temperature = dht.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    dhtValid = false;
    return;
  }

  latestHumidity = humidity;
  latestTemperature = temperature;
  dhtValid = true;
}

// =====================================================
// MPU6050 DAN MQ135
// =====================================================

bool writeMPU6050Register(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU6050_ADDRESS);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readMPU6050Raw(
  int16_t& ax,
  int16_t& ay,
  int16_t& az,
  int16_t& gx,
  int16_t& gy,
  int16_t& gz
) {
  Wire.beginTransmission(MPU6050_ADDRESS);
  Wire.write(MPU6050_ACCEL_XOUT_H);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(MPU6050_ADDRESS, static_cast<uint8_t>(14)) != 14) {
    return false;
  }

  ax = Wire.read() << 8 | Wire.read();
  ay = Wire.read() << 8 | Wire.read();
  az = Wire.read() << 8 | Wire.read();

  // Temperature internal MPU6050 tidak dipakai.
  Wire.read();
  Wire.read();

  gx = Wire.read() << 8 | Wire.read();
  gy = Wire.read() << 8 | Wire.read();
  gz = Wire.read() << 8 | Wire.read();

  return true;
}

void setupMPU6050() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);

  mpu6050Ready =
    writeMPU6050Register(MPU6050_PWR_MGMT_1, 0x00) &&
    writeMPU6050Register(MPU6050_ACCEL_CONFIG, 0x10) &&
    writeMPU6050Register(MPU6050_GYRO_CONFIG, 0x08);

  Serial.print("MPU6050 status: ");
  Serial.println(mpu6050Ready ? "TERDETEKSI" : "TIDAK TERDETEKSI");
}

const char* classifyAirQuality(int rawValue) {
  if (rawValue >= MQ135_DANGEROUS_THRESHOLD) {
    return "DANGEROUS";
  }

  if (rawValue >= MQ135_POOR_THRESHOLD) {
    return "POOR";
  }

  if (rawValue >= MQ135_MODERATE_THRESHOLD) {
    return "MODERATE";
  }

  return "NORMAL";
}

void updateMotionAndAirQuality() {
  const unsigned long currentTime = millis();

  if (
    lastSensorReadAt != 0 &&
    currentTime - lastSensorReadAt <
    SENSOR_READ_INTERVAL_MS
  ) {
    return;
  }

  lastSensorReadAt = currentTime;

  latestMq135Raw = analogRead(MQ135_ADC_PIN);
  latestAirQualityLevel = classifyAirQuality(latestMq135Raw);
  latestGasAlert =
    strcmp(latestAirQualityLevel, "POOR") == 0 ||
    strcmp(latestAirQualityLevel, "DANGEROUS") == 0;

  if (!mpu6050Ready) {
    latestMotion.valid = false;
    latestMotion.impactDetected = false;
    latestMotion.fallDetected = false;
    latestMotion.impactG = 1.0;
    return;
  }

  int16_t rawAx = 0;
  int16_t rawAy = 0;
  int16_t rawAz = 0;
  int16_t rawGx = 0;
  int16_t rawGy = 0;
  int16_t rawGz = 0;

  if (
    !readMPU6050Raw(
      rawAx,
      rawAy,
      rawAz,
      rawGx,
      rawGy,
      rawGz
    )
  ) {
    latestMotion.valid = false;
    return;
  }

  const float accelXG = rawAx / MPU6050_ACCEL_SCALE;
  const float accelYG = rawAy / MPU6050_ACCEL_SCALE;
  const float accelZG = rawAz / MPU6050_ACCEL_SCALE;
  const float totalG = sqrt(
    accelXG * accelXG +
    accelYG * accelYG +
    accelZG * accelZG
  );

  latestMotion.valid = true;
  latestMotion.accelX = accelXG * STANDARD_GRAVITY;
  latestMotion.accelY = accelYG * STANDARD_GRAVITY;
  latestMotion.accelZ = accelZG * STANDARD_GRAVITY;
  latestMotion.gyroX = rawGx / MPU6050_GYRO_SCALE;
  latestMotion.gyroY = rawGy / MPU6050_GYRO_SCALE;
  latestMotion.gyroZ = rawGz / MPU6050_GYRO_SCALE;
  latestMotion.pitch = atan2(
    -accelXG,
    sqrt(accelYG * accelYG + accelZG * accelZG)
  ) * 180.0 / PI;
  latestMotion.roll = atan2(accelYG, accelZG) * 180.0 / PI;
  latestMotion.yaw = 0.0;
  latestMotion.impactG = totalG;
  latestMotion.impactDetected = totalG >= IMPACT_THRESHOLD_G;
  latestMotion.fallDetected =
    totalG <= FALL_FREEFALL_THRESHOLD_G ||
    fabs(latestMotion.pitch) >= FALL_TILT_THRESHOLD_DEG ||
    fabs(latestMotion.roll) >= FALL_TILT_THRESHOLD_DEG;
}

// =====================================================
// PENENTUAN HAZARD PRIORITAS
// =====================================================

int getMostDangerousHazardIndex() {
  int selectedIndex = -1;
  uint8_t highestPriority = 0;
  int strongestRssi = -200;

  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    if (!hazards[i].used) {
      continue;
    }

    const uint8_t priority =
      getZonePriority(hazards[i].zone);

    if (
      priority > highestPriority ||
      (
        priority == highestPriority &&
        hazards[i].smoothedRssi > strongestRssi
      )
    ) {
      selectedIndex = i;
      highestPriority = priority;
      strongestRssi = hazards[i].smoothedRssi;
    }
  }

  return selectedIndex;
}

void updateWarningPriority() {
  const int hazardIndex =
    getMostDangerousHazardIndex();

  if (hazardIndex == -1) {
    currentWarningPriority = 0;
    return;
  }

  currentWarningPriority =
    getZonePriority(hazards[hazardIndex].zone);
}

// =====================================================
// TASK WARNING NON-BLOCKING
// =====================================================

void warningTask(void* parameter) {
  uint8_t previousPriority = 255;
  bool vibrationPhaseOn = false;
  unsigned long lastPhaseChange = 0;

  while (true) {
    const uint8_t priority = currentWarningPriority;
    const unsigned long currentTime = millis();

    // Terapkan kondisi awal setiap kali level warning berubah.
    if (priority != previousPriority) {
      previousPriority = priority;
      vibrationPhaseOn = false;
      lastPhaseChange = currentTime;
      stopAllWarnings();

      if (priority == 3) {
        // HIGH: buzzer dan vibration mulai dalam kondisi ON.
        vibrationPhaseOn = true;
        setBuzzer(true);
        setVibration(true);
      } else if (priority == 4) {
        // CRITICAL: buzzer dan vibration menyala terus.
        setBuzzer(true);
        setVibration(true);
      }
    }

    if (priority == 3) {
      // HIGH: buzzer dan vibration berdenyut cepat bersamaan.
      const unsigned long phaseDuration =
        vibrationPhaseOn ? HIGH_ON_MS : HIGH_OFF_MS;

      if (
        currentTime - lastPhaseChange >=
        phaseDuration
      ) {
        vibrationPhaseOn = !vibrationPhaseOn;
        lastPhaseChange = currentTime;

        setBuzzer(vibrationPhaseOn);
        setVibration(vibrationPhaseOn);
      }
    } else if (priority == 4) {
      // CRITICAL: pertahankan kedua output tetap menyala.
      setBuzzer(true);
      setVibration(true);
    } else {
      // SAFE, MODERATE, atau tidak ada hazard.
      stopAllWarnings();
    }

    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// =====================================================
// OUTPUT SERIAL
// =====================================================

void printDHTData() {
  Serial.println();
  Serial.println(
    "========== KONDISI LINGKUNGAN =========="
  );

  if (!dhtValid) {
    Serial.println(
      "Status      : Data DHT22 belum tersedia"
    );
  } else {
    Serial.print("Suhu        : ");
    Serial.print(latestTemperature, 1);
    Serial.println(" °C");

    Serial.print("Kelembapan  : ");
    Serial.print(latestHumidity, 1);
    Serial.println(" %");

    if (latestTemperature >= 35.0) {
      Serial.println("Status suhu : TINGGI");
    } else if (latestTemperature >= 30.0) {
      Serial.println("Status suhu : MODERATE");
    } else {
      Serial.println("Status suhu : NORMAL");
    }
  }

  Serial.println(
    "========================================"
  );
}

void printMotionData() {
  Serial.println();
  Serial.println("========== MOTION & IMPACT ==========");

  if (!latestMotion.valid) {
    Serial.println("Status      : MPU6050 belum tersedia");
  } else {
    Serial.print("Accel X/Y/Z : ");
    Serial.print(latestMotion.accelX, 2);
    Serial.print(" / ");
    Serial.print(latestMotion.accelY, 2);
    Serial.print(" / ");
    Serial.print(latestMotion.accelZ, 2);
    Serial.println(" m/s2");

    Serial.print("Gyro X/Y/Z  : ");
    Serial.print(latestMotion.gyroX, 1);
    Serial.print(" / ");
    Serial.print(latestMotion.gyroY, 1);
    Serial.print(" / ");
    Serial.print(latestMotion.gyroZ, 1);
    Serial.println(" dps");

    Serial.print("Impact G    : ");
    Serial.print(latestMotion.impactG, 2);
    Serial.println(" g");

    Serial.print("Benturan    : ");
    Serial.println(latestMotion.impactDetected ? "TERDETEKSI" : "TIDAK");

    Serial.print("Jatuh       : ");
    Serial.println(latestMotion.fallDetected ? "TERDETEKSI" : "TIDAK");
  }

  Serial.println("=====================================");
}

void printAirQualityData() {
  Serial.println();
  Serial.println("========== KUALITAS UDARA ==========");
  Serial.print("MQ135 raw   : ");
  Serial.println(latestMq135Raw);
  Serial.print("Level udara : ");
  Serial.println(latestAirQualityLevel);
  Serial.print("Gas alert   : ");
  Serial.println(latestGasAlert ? "YA" : "TIDAK");
  Serial.println("====================================");
}

void printHazardList() {
  Serial.println();
  Serial.println(
    "========== DAFTAR HAZARD =========="
  );

  uint8_t activeHazardCount = 0;

  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    if (!hazards[i].used) {
      continue;
    }

    activeHazardCount++;

    Serial.print("Nama         : ");
    Serial.println(hazards[i].name);

    Serial.print("MAC          : ");
    Serial.println(hazards[i].macAddress);

    Serial.print("RSSI mentah  : ");
    Serial.print(hazards[i].rawRssi);
    Serial.println(" dBm");

    Serial.print("RSSI rata-rata: ");
    Serial.print(hazards[i].smoothedRssi);
    Serial.println(" dBm");

    Serial.print("Zona         : ");
    Serial.println(zoneToString(hazards[i].zone));

    Serial.println("-----------------------------------");
  }

  if (activeHazardCount == 0) {
    Serial.println(
      "Tidak ada hazard REKSA yang aktif."
    );
  }

  const int priorityIndex =
    getMostDangerousHazardIndex();

  if (priorityIndex != -1) {
    Serial.println();
    Serial.println("HAZARD PRIORITAS:");

    Serial.print("Nama : ");
    Serial.println(hazards[priorityIndex].name);

    Serial.print("RSSI : ");
    Serial.print(
      hazards[priorityIndex].smoothedRssi
    );
    Serial.println(" dBm");

    Serial.print("Zona : ");
    Serial.println(
      zoneToString(hazards[priorityIndex].zone)
    );
  }

  Serial.println(
    "==================================="
  );
}

void printWarningStatus() {
  Serial.println();
  Serial.println("========== STATUS WARNING ==========");

  switch (currentWarningPriority) {
    case 4:
      Serial.println("Level      : CRITICAL");
      Serial.println("Buzzer     : MENYALA TERUS");
      Serial.println("Vibration  : MENYALA TERUS");
      break;

    case 3:
      Serial.println("Level      : HIGH");
      Serial.println("Buzzer     : PULSE CEPAT");
      Serial.println("Vibration  : PULSE CEPAT");
      break;

    case 2:
      Serial.println("Level      : MODERATE");
      Serial.println("Buzzer     : MATI");
      Serial.println("Vibration  : MATI");
      break;

    case 1:
      Serial.println("Level      : SAFE");
      Serial.println("Buzzer     : MATI");
      Serial.println("Vibration  : MATI");
      break;

    default:
      Serial.println("Level      : TANPA HAZARD");
      Serial.println("Buzzer     : MATI");
      Serial.println("Vibration  : MATI");
      break;
  }

  Serial.println(
    "===================================="
  );
}

// =====================================================
// WIFI & MQTT PROCEDURES
// =====================================================

void setupWiFi() {
  delay(10);
  Serial.println();
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("WiFi terhubung!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    if (!timeSyncStarted) {
      configTime(
        GMT_OFFSET_SECONDS,
        DAYLIGHT_OFFSET_SECONDS,
        NTP_SERVER
      );
      timeSyncStarted = true;
    }
  } else {
    Serial.println("");
    Serial.println("WiFi gagal terhubung (akan dicoba kembali).");
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Pesan MQTT diterima [");
  Serial.print(topic);
  Serial.println("]");

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error) {
    Serial.print("Gagal parsing JSON: ");
    Serial.println(error.f_str());
    return;
  }

  const char* level = doc["warning_level"];
  bool buzzer = doc["actions"]["buzzer"] | false;
  bool vibration = doc["actions"]["vibration"] | false;

  Serial.print("Peringatan masuk: level=");
  Serial.print(level);
  Serial.print(", buzzer=");
  Serial.print(buzzer);
  Serial.print(", vibration=");
  Serial.println(vibration);

  if (level != nullptr) {
    String lvl = String(level);
    if (lvl == "CRITICAL") {
      currentWarningPriority = 4;
    } else if (lvl == "HIGH") {
      currentWarningPriority = 3;
    } else if (lvl == "MODERATE") {
      currentWarningPriority = 2;
    } else {
      currentWarningPriority = 1;
    }
  }
}

void reconnectMQTT() {
  int attempts = 0;
  while (!mqttClient.connected() && attempts < 3) {
    Serial.print("Menghubungkan ke Broker MQTT...");
    String clientId = "ReksaHelmet-W01-";
    clientId += String(random(0xffff), HEX);

    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("Terhubung!");
      
      // Subscribe ke topik warning
      String topic = "REKSA/helmet/";
      topic += WORKER_ID;
      topic += "/warning";
      mqttClient.subscribe(topic.c_str());
      Serial.print("Subscribed ke topic: ");
      Serial.println(topic);
    } else {
      Serial.print("Gagal, status=");
      Serial.print(mqttClient.state());
      Serial.println(" coba lagi dalam 2 detik...");
      delay(2000);
      attempts++;
    }
  }
}
void writeIsoTimestamp(char* buffer, size_t bufferSize) {
  time_t now = time(nullptr);

  if (now < 1700000000) {
    snprintf(
      buffer,
      bufferSize,
      "2026-08-06T%02lu:%02lu:%02luZ",
      (millis() / 3600000UL) % 24,
      (millis() / 60000UL) % 60,
      (millis() / 1000UL) % 60
    );
    return;
  }

  struct tm timeInfo;
  gmtime_r(&now, &timeInfo);
  strftime(
    buffer,
    bufferSize,
    "%Y-%m-%dT%H:%M:%SZ",
    &timeInfo
  );
}

void publishSensorData() {
  if (!mqttClient.connected()) {
    return;
  }

  StaticJsonDocument<1024> doc;
  
  String msgId = "msg-" + String(millis());
  char timestamp[25];
  writeIsoTimestamp(timestamp, sizeof(timestamp));

  doc["message_id"] = msgId;
  doc["device_id"] = "HELMET-" + String(WORKER_ID);
  doc["worker_id"] = WORKER_ID;
  doc["timestamp"] = timestamp; 

  JsonObject accel = doc.createNestedObject("acceleration");
  accel["x"] = round(latestMotion.accelX * 100.0) / 100.0;
  accel["y"] = round(latestMotion.accelY * 100.0) / 100.0;
  accel["z"] = round(latestMotion.accelZ * 100.0) / 100.0;

  JsonObject gyro = doc.createNestedObject("gyroscope");
  gyro["x"] = round(latestMotion.gyroX * 10.0) / 10.0;
  gyro["y"] = round(latestMotion.gyroY * 10.0) / 10.0;
  gyro["z"] = round(latestMotion.gyroZ * 10.0) / 10.0;

  JsonObject orient = doc.createNestedObject("orientation");
  orient["pitch"] = round(latestMotion.pitch * 10.0) / 10.0;
  orient["roll"] = round(latestMotion.roll * 10.0) / 10.0;
  orient["yaw"] = round(latestMotion.yaw * 10.0) / 10.0;

  doc["impact_detected"] = latestMotion.impactDetected;
  doc["fall_detected"] = latestMotion.fallDetected;
  doc["impact_g"] = round(latestMotion.impactG * 100.0) / 100.0;
  if (dhtValid) {
    doc["temperature"] =
      round(latestTemperature * 10.0) / 10.0;
    doc["humidity"] =
      round(latestHumidity * 10.0) / 10.0;
  }
  doc["firmware_version"] = "0.2.0";

  JsonObject airQuality = doc.createNestedObject("air_quality");
  airQuality["mq135_raw"] = latestMq135Raw;
  airQuality["air_quality_level"] = latestAirQualityLevel;
  airQuality["gas_alert"] = latestGasAlert;

  int hazardIndex = getMostDangerousHazardIndex();
  if (hazardIndex != -1) {
    JsonObject hz = doc.createNestedObject("closest_hazard");
    String rawId = hazards[hazardIndex].name;
    if (rawId.startsWith(HAZARD_PREFIX)) {
      rawId = rawId.substring(strlen(HAZARD_PREFIX));
    }
    hz["hazard_id"] = rawId;
    hz["hazard_type"] = rawId.startsWith("F") ? "FORKLIFT" : rawId.startsWith("G") ? "GRINDING" : "LASER";
    hz["operating_status"] = "ACTIVE";
    hz["rssi"] = hazards[hazardIndex].smoothedRssi;
    hz["proximity_level"] = zoneToString(hazards[hazardIndex].zone);
  } else {
    doc["closest_hazard"] = nullptr;
  }

  char buffer[1024];
  const size_t payloadSize = serializeJson(doc, buffer);

  String topic = "REKSA/helmet/";
  topic += WORKER_ID;
  topic += "/sensor";

  if (mqttClient.publish(topic.c_str(), buffer)) {
    Serial.print("Mempublikasikan sensor ke ");
    Serial.print(topic);
    Serial.print(" (");
    Serial.print(payloadSize);
    Serial.print(" bytes)");
    Serial.print(": ");
    Serial.println(buffer);
  } else {
    Serial.print("Gagal mempublikasikan sensor ke MQTT. connected=");
    Serial.print(mqttClient.connected());
    Serial.print(", state=");
    Serial.print(mqttClient.state());
    Serial.print(", payload=");
    Serial.print(payloadSize);
    Serial.print(" bytes, buffer=");
    Serial.print(MQTT_BUFFER_SIZE);
    Serial.println(" bytes");
  }
}

// =====================================================
// SETUP
// =====================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println(
    "Memulai REKSA Smart Helmet Node..."
  );

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(VIBRATION_PIN, OUTPUT);
  stopAllWarnings();

  Serial.print(
    "Buzzer dikonfigurasi pada GPIO "
  );
  Serial.println(BUZZER_PIN);

  Serial.print(
    "Vibration dikonfigurasi pada GPIO "
  );
  Serial.println(VIBRATION_PIN);

  if (RUN_OUTPUT_SELF_TEST) {
    testWarningModules();
  }

  dht.begin();

  Serial.print(
    "DHT22 dikonfigurasi pada GPIO "
  );
  Serial.println(DHT_PIN);

  analogReadResolution(12);
  analogSetPinAttenuation(MQ135_ADC_PIN, ADC_11db);

  Serial.print("MQ135 dikonfigurasi pada GPIO ");
  Serial.println(MQ135_ADC_PIN);

  setupMPU6050();

  for (uint8_t i = 0; i < MAX_HAZARDS; i++) {
    resetHazard(hazards[i]);
  }

  BLEDevice::init(HELMET_NAME);

  bleScan = BLEDevice::getScan();

  bleScan->setAdvertisedDeviceCallbacks(
    new ScanCallbacks(),
    true
  );

  bleScan->setActiveScan(true);
  bleScan->setInterval(100);
  bleScan->setWindow(80);

  Serial.println("BLE Scanner aktif");

  const BaseType_t taskCreated = xTaskCreate(
    warningTask,
    "REKSA_Warning",
    2048,
    nullptr,
    1,
    nullptr
  );

  if (taskCreated != pdPASS) {
    Serial.println(
      "Gagal membuat task warning."
    );
  }

  // Inisialisasi WiFi dan MQTT
  setupWiFi();
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setBufferSize(MQTT_BUFFER_SIZE);
  mqttClient.setCallback(mqttCallback);
}

// =====================================================
// LOOP
// =====================================================

void loop() {
  // Pastikan WiFi terhubung
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }

  // Pastikan MQTT terhubung
  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
    reconnectMQTT();
  }

  // Jalankan MQTT Loop
  if (mqttClient.connected()) {
    mqttClient.loop();
  }

  Serial.println();
  Serial.println(
    "Memindai seluruh hazard REKSA..."
  );

  bleScan->start(BLE_SCAN_SECONDS, false);

  removeInactiveHazards();
  updateWarningPriority();
  updateDHT22();
  updateMotionAndAirQuality();

  printDHTData();
  printMotionData();
  printAirQualityData();
  printHazardList();
  printWarningStatus();

  // Kirim data sensor ke dashboard web secara berkala via MQTT
  static unsigned long lastPublish = 0;
  if (millis() - lastPublish >= 2500) {
    lastPublish = millis();
    publishSensorData();
  }

  bleScan->clearResults();

  delay(100);
}

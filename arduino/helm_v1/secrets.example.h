#pragma once

// Salin menjadi secrets.h. File secrets.h diabaikan Git.
#define REKSA_WIFI_SSID "YOUR_WIFI_SSID"
#define REKSA_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define REKSA_MQTT_HOST "your-cluster.s1.eu.hivemq.cloud"
#define REKSA_MQTT_PORT 8883
#define REKSA_MQTT_USERNAME "reksa-helmet-w01"
#define REKSA_MQTT_PASSWORD "replace-me"
#define REKSA_MQTT_USE_TLS 1

// Isi dengan root CA PEM yang memvalidasi sertifikat endpoint HiveMQ.
// Jangan gunakan setInsecure() pada demo final.
static const char REKSA_MQTT_ROOT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_ROOT_CA
-----END CERTIFICATE-----
)EOF";

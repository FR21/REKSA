#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: command '$1' belum terpasang."
    exit 1
  fi
}

read_safe_value() {
  local label="$1"
  local variable_name="$2"
  local secret="${3:-false}"
  local value=""

  while true; do
    if [[ "${secret}" == "true" ]]; then
      read -r -s -p "${label}: " value
      echo
    else
      read -r -p "${label}: " value
    fi

    if [[ "${value}" =~ ^[A-Za-z0-9._@%+=:,/-]+$ ]]; then
      printf -v "${variable_name}" '%s' "${value}"
      return
    fi
    echo "Gunakan hanya huruf, angka, dan karakter . _ @ %% + = : , / -"
  done
}

c_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

require_command openssl
require_command awk

echo "=== Konfigurasi aman REKSA + HiveMQ Cloud ==="
echo "Password tidak akan ditampilkan dan file rahasia tidak akan masuk Git."
echo

read_safe_value "Hostname HiveMQ (tanpa mqtts:// dan tanpa :8883)" HIVEMQ_HOST
if [[ ! "${HIVEMQ_HOST}" =~ ^[A-Za-z0-9.-]+\.hivemq\.cloud$ ]]; then
  echo "ERROR: hostname harus berakhir dengan .hivemq.cloud tanpa protokol atau port."
  exit 1
fi
read_safe_value "Username HiveMQ untuk backend" BACKEND_USER
read_safe_value "Password HiveMQ untuk backend" BACKEND_PASSWORD true
read_safe_value "Username HiveMQ untuk helmet W01" HELMET_USER
read_safe_value "Password HiveMQ untuk helmet W01" HELMET_PASSWORD true
read_safe_value "Username HiveMQ untuk bridge/gateway" BRIDGE_USER
read_safe_value "Password HiveMQ untuk bridge/gateway" BRIDGE_PASSWORD true

read -r -p "Nama Wi-Fi untuk ESP32: " WIFI_SSID
read -r -s -p "Password Wi-Fi untuk ESP32: " WIFI_PASSWORD
echo
read -r -p "Google Cloud Project ID (ENTER jika belum dibuat): " GCP_PROJECT_ID
GCP_PROJECT_ID="${GCP_PROJECT_ID:-CHANGE_ME_AFTER_GCP_PROJECT_EXISTS}"

if [[ ! "${GCP_PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] && \
   [[ "${GCP_PROJECT_ID}" != "CHANGE_ME_AFTER_GCP_PROJECT_EXISTS" ]]; then
  echo "ERROR: format Google Cloud Project ID tidak valid."
  exit 1
fi

TEMP_DIR="$(mktemp -d)"
case "${TEMP_DIR}" in
  /tmp/*) ;;
  *) echo "ERROR: direktori sementara tidak aman: ${TEMP_DIR}"; exit 1 ;;
esac
cleanup() {
  rm -rf -- "${TEMP_DIR:?}"
}
trap cleanup EXIT

echo "Mengambil rantai sertifikat TLS dari ${HIVEMQ_HOST}:8883 ..."
if ! openssl s_client -showcerts \
  -connect "${HIVEMQ_HOST}:8883" \
  -servername "${HIVEMQ_HOST}" </dev/null >"${TEMP_DIR}/chain.txt" 2>"${TEMP_DIR}/openssl-error.txt"; then
  echo "ERROR: tidak dapat terhubung ke HiveMQ. Periksa hostname dan internet."
  sed -n '1,8p' "${TEMP_DIR}/openssl-error.txt"
  exit 1
fi

awk -v output_dir="${TEMP_DIR}" '
  /-----BEGIN CERTIFICATE-----/ { certificate_count++; capture=1 }
  capture { print > (output_dir "/cert-" certificate_count ".pem") }
  /-----END CERTIFICATE-----/ { capture=0; close(output_dir "/cert-" certificate_count ".pem") }
  END { if (certificate_count == 0) exit 1 }
' "${TEMP_DIR}/chain.txt"

CERT_COUNT="$(find "${TEMP_DIR}" -maxdepth 1 -type f -name 'cert-*.pem' | wc -l)"
if [[ "${CERT_COUNT}" -lt 1 ]]; then
  echo "ERROR: sertifikat CA tidak ditemukan."
  exit 1
fi
CA_FILE="${TEMP_DIR}/cert-${CERT_COUNT}.pem"
if [[ ! -s "${CA_FILE}" ]]; then
  echo "ERROR: file sertifikat CA kosong."
  exit 1
fi

cat >"${ROOT_DIR}/.env.hivemq" <<EOF
MQTT_HOST=${HIVEMQ_HOST}
MQTT_PORT=8883
MQTT_USERNAME=${BACKEND_USER}
MQTT_PASSWORD=${BACKEND_PASSWORD}
MQTT_TLS=true
MQTT_CA_CERT=
MQTT_CLIENT_ID=reksa-backend-demo
EOF

cat >"${ROOT_DIR}/bridge/.env" <<EOF
GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID}
PUBSUB_TOPIC=reksa-telemetry
MQTT_HOST=${HIVEMQ_HOST}
MQTT_PORT=8883
MQTT_USERNAME=${BRIDGE_USER}
MQTT_PASSWORD=${BRIDGE_PASSWORD}
MQTT_CA_CERT=
BRIDGE_ID=reksa-gateway-01
OUTBOX_PATH=/data/outbox.db
EOF

{
  printf '%s\n' '#pragma once' ''
  printf '#define REKSA_WIFI_SSID "%s"\n' "$(c_escape "${WIFI_SSID}")"
  printf '#define REKSA_WIFI_PASSWORD "%s"\n' "$(c_escape "${WIFI_PASSWORD}")"
  printf '#define REKSA_MQTT_HOST "%s"\n' "${HIVEMQ_HOST}"
  printf '%s\n' '#define REKSA_MQTT_PORT 8883'
  printf '#define REKSA_MQTT_USERNAME "%s"\n' "${HELMET_USER}"
  printf '#define REKSA_MQTT_PASSWORD "%s"\n' "${HELMET_PASSWORD}"
  printf '%s\n\n' '#define REKSA_MQTT_USE_TLS 1'
  printf '%s\n' 'static const char REKSA_MQTT_ROOT_CA[] PROGMEM = R"EOF('
  cat "${CA_FILE}"
  printf '%s\n' ')EOF";'
} >"${ROOT_DIR}/arduino/helm_v1/secrets.h"

chmod 600 \
  "${ROOT_DIR}/.env.hivemq" \
  "${ROOT_DIR}/bridge/.env" \
  "${ROOT_DIR}/arduino/helm_v1/secrets.h"

echo
echo "SELESAI. File berikut sudah dibuat:"
echo "- .env.hivemq (backend)"
echo "- bridge/.env (gateway)"
echo "- arduino/helm_v1/secrets.h (ESP32 + sertifikat TLS)"
echo "Password tidak dicetak. Lanjutkan ke Langkah 7 pada panduan."

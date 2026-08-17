#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.hivemq"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: .env.hivemq belum ada. Jalankan ./deploy/setup-hivemq.sh"
  exit 1
fi
for command_name in mosquitto_pub mosquitto_sub; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "ERROR: ${command_name} belum terpasang. Jalankan: sudo dnf install -y mosquitto"
    exit 1
  fi
done

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

TEST_TOPIC="REKSA/setup/test-$(date +%s)"
EXPECTED='{"status":"ok","source":"setup"}'
OUTPUT_FILE="$(mktemp)"
SUBSCRIBER_PID=""
case "${OUTPUT_FILE}" in
  /tmp/*) ;;
  *) echo "ERROR: file sementara tidak aman"; exit 1 ;;
esac
cleanup() {
  if [[ -n "${SUBSCRIBER_PID}" ]] && kill -0 "${SUBSCRIBER_PID}" >/dev/null 2>&1; then
    kill "${SUBSCRIBER_PID}" >/dev/null 2>&1 || true
  fi
  rm -f -- "${OUTPUT_FILE:?}"
}
trap cleanup EXIT

mosquitto_sub \
  -h "${MQTT_HOST}" -p "${MQTT_PORT}" \
  -u "${MQTT_USERNAME}" -P "${MQTT_PASSWORD}" \
  --tls-use-os-certs \
  -t "${TEST_TOPIC}" -q 1 -C 1 -W 10 >"${OUTPUT_FILE}" &
SUBSCRIBER_PID=$!
sleep 1

mosquitto_pub \
  -h "${MQTT_HOST}" -p "${MQTT_PORT}" \
  -u "${MQTT_USERNAME}" -P "${MQTT_PASSWORD}" \
  --tls-use-os-certs \
  -t "${TEST_TOPIC}" -q 1 -m "${EXPECTED}"

if ! wait "${SUBSCRIBER_PID}"; then
  echo "GAGAL: subscriber tidak menerima pesan. Periksa permission REKSA/#."
  exit 1
fi

ACTUAL="$(tr -d '\r\n' <"${OUTPUT_FILE}")"
if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
  echo "GAGAL: payload yang diterima berbeda: ${ACTUAL}"
  exit 1
fi

echo "BERHASIL: koneksi TLS, publish, subscribe, dan QoS 1 HiveMQ berfungsi."

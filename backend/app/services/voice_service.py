import io
import json
import logging
import os
import wave
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.services.db_service import db_service
from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

logger = logging.getLogger(__name__)


def get_wit_ai_token() -> str:
    token = (settings.wit_ai_token or os.getenv("WIT_AI_TOKEN", "")).strip()
    if not token:
        return ""
    return token if token.startswith("Bearer ") else f"Bearer {token}"


def parse_safety_intent(
    transcription: str,
    worker: dict[str, Any] | None,
    hazards: list[dict[str, Any]],
) -> dict[str, Any]:
    text = transcription.lower().strip()

    # Intent keyword dictionaries (ID & EN)
    evacuation_keywords = [
        "evakuasi", "darurat", "kebakaran", "api", "asap", "ledakan", "meledak",
        "runtuh", "ambruk", "keluar semua", "kabur", "tinggalkan area", "gempa",
        "gas beracun", "bocor parah", "bahaya maut", "evacuate", "evacuation",
        "emergency", "fire", "smoke", "explosion", "exploding", "collapse",
        "collapsing", "get out", "run", "clear the area", "toxic gas", "abandon area", "mayday mayday",
    ]
    sos_keywords = [
        "tolong", "bantu", "bantuan", "jatuh", "terjatuh", "pingsan", "medis",
        "sakit", "terjepit", "tertimpa", "darah", "pendarahan", "luka", "patah",
        "kesetrum", "tersengat", "sesak", "tidak sadar", "butuh dokter", "p3k",
        "mayday", "sos", "help", "help me", "assistance", "medic", "medical",
        "doctor", "first aid", "injured", "injury", "bleeding", "casualty",
        "fallen", "fall down", "collapsed", "unconscious", "trapped", "crushed",
        "electrocuted", "suffocating",
    ]
    halt_keywords = [
        "matikan mesin", "matiin mesin", "stop mesin", "hentikan", "rem blong",
        "rem blonk", "rem macet", "jangan maju", "berhenti", "jangan jalan",
        "tahan", "e-stop", "putus daya", "rem tidak berfungsi", "tabrakan",
        "stop machine", "shut down", "shutdown", "kill engine", "emergency stop",
        "halt", "brake failure", "no brakes", "brakes failed", "dont move",
        "don't move", "freeze", "cut the power", "kill switch",
    ]
    hazard_keywords = [
        "bahaya", "lapor", "laporan", "tumpahan", "oli", "minyak", "kimia",
        "bocor", "kebocoran", "rusak", "kerusakan", "hampir kena", "hampir tabrak",
        "senggol", "kesenggol", "kabel terkelupas", "kabel lepas", "licin",
        "retak", "pecah", "rawan", "blind spot", "tidak aman", "hazard", "danger",
        "dangerous", "warning", "report", "spill", "oil spill", "chemical leak",
        "gas leak", "leakage", "damaged", "broken", "near miss", "near-miss",
        "almost hit", "collision risk", "slippery", "loose wire", "exposed cable",
        "crack", "hazard spotted", "unsafe condition",
    ]
    safe_keywords = [
        "aman", "terkendali", "selesai", "kembali ke pos", "lapor aman",
        "cek radio", "status normal", "kondisi normal", "nihil", "beres",
        "situasi aman", "sudah diatasi", "sudah beres", "all clear", "clear",
        "safe", "roger", "roger that", "copy", "copy that", "10-4", "stand down",
        "controlled", "under control", "resolved", "status normal", "task completed", "all good",
    ]

    # Intent classification
    if any(k in text for k in evacuation_keywords):
        intent, intent_label, urgency, nature, confidence = (
            "EMERGENCY_EVACUATE", "Evakuasi Darurat", "CRITICAL", "Bahaya Mengancam Jiwa / Evakuasi", 0.97
        )
    elif any(k in text for k in sos_keywords):
        intent, intent_label, urgency, nature, confidence = (
            "ASSISTANCE_SOS", "Panggilan Bantuan / SOS", "CRITICAL", "Insiden Pekerja / Cedera Fisik", 0.96
        )
    elif any(k in text for k in halt_keywords):
        intent, intent_label, urgency, nature, confidence = (
            "MACHINE_HALT", "Perintah Hentikan Mesin", "HIGH", "Kendala Mekanikal / Pergerakan Alat", 0.94
        )
    elif any(k in text for k in hazard_keywords):
        intent, intent_label, urgency, nature, confidence = (
            "HAZARD_REPORT", "Laporan Potensi Bahaya", "HIGH", "Potensi Kecelakaan Kerja", 0.92
        )
    elif any(k in text for k in safe_keywords):
        intent, intent_label, urgency, nature, confidence = (
            "SAFETY_STATUS", "Laporan Status Aman", "INFO", "Pemeriksaan Rutin", 0.93
        )
    else:
        intent, intent_label, urgency, nature, confidence = (
            "GENERAL_TRANSMISSION", "Komunikasi Radio Umum", "INFO", "Komunikasi Operasional", 0.88
        )

    # Hazard entity matching
    matched_hazard = None
    for h in hazards:
        hid = h.get("id", "").lower()
        hname = h.get("name", "").lower()
        htype = h.get("type", "").lower()

        if hid and (hid in text or f"hazard {hid}" in text):
            matched_hazard = h
            break
        if hname and hname in text:
            matched_hazard = h
            break
        if htype == "forklift" and any(w in text for w in ["forklift", "forklif", "forklip", "truck", "truk", "f01", "f-01"]):
            matched_hazard = h
            break
        if htype == "grinding" and any(w in text for w in ["grinding", "gerinda", "gerenda", "pemotong", "cutter", "g01"]):
            matched_hazard = h
            break
        if htype == "laser" and any(w in text for w in ["laser", "mesin laser", "cutting laser", "l01"]):
            matched_hazard = h
            break

    if not matched_hazard and worker and worker.get("closest_hazard"):
        ch_id = worker.get("closest_hazard")
        matched_hazard = next((h for h in hazards if h.get("id") == ch_id), None)

    # Area entity matching
    detected_area = None
    area_map = {
        "Gudang Utama": ["gudang utama", "main warehouse", "warehouse", "gudang", "storage"],
        "Zona Bongkar": ["zona bongkar", "loading dock", "unloading dock", "bongkar muat", "dock"],
        "Produksi A": ["produksi a", "production a", "line a", "jalur a"],
        "Produksi B": ["produksi b", "production b", "line b", "jalur b"],
        "Koridor Timur": ["koridor timur", "east corridor", "lorong timur"],
        "Area Laser": ["area laser", "laser area", "zona laser", "laser cutting"],
        "Assembly Point": ["assembly point", "titik kumpul", "area evakuasi"],
    }
    for standard_name, synonyms in area_map.items():
        if any(syn in text for syn in synonyms):
            detected_area = standard_name
            break

    if not detected_area and worker:
        detected_area = worker.get("area", "Area Kerja")

    # Action generation
    hazard_str = matched_hazard.get("name", "alat berat") if matched_hazard else "alat sekitar"
    worker_name = worker.get("name", "Pekerja") if worker else "Pekerja"

    if intent == "EMERGENCY_EVACUATE":
        action = f"Bunyikan sirene evakuasi untuk {detected_area}. Pastikan {worker_name} dan seluruh personil segera menuju Assembly Point."
    elif intent == "ASSISTANCE_SOS":
        action = f"Kirim tim medis P3K / rescue segera ke {detected_area} untuk memberi pertolongan pertama kepada {worker_name}."
    elif intent == "MACHINE_HALT":
        action = f"Kirim sinyal buzzer darurat dan instruksikan operator {hazard_str} di {detected_area} untuk segera mematikan mesin."
    elif intent == "HAZARD_REPORT":
        action = f"Tandai batas barikade keselamatan di {detected_area} dan periksa kelayakan {hazard_str} sebelum aktivitas dilanjutkan."
    elif intent == "SAFETY_STATUS":
        action = f"Catat konfirmasi aman dari {worker_name} di {detected_area}. Lanjutkan pemantauan telemetri rutin."
    else:
        action = f"Verifikasi panggilan radio dari {worker_name} di {detected_area}."

    return {
        "intent": intent,
        "intent_label": intent_label,
        "urgency": urgency,
        "nature": nature,
        "confidence": confidence,
        "matched_hazard": matched_hazard,
        "detected_area": detected_area or "Area Kerja",
        "recommended_action": action,
    }


class VoiceService:
    def __init__(self):
        self.audio_buffers: dict[str, bytearray] = {}
        self.audio_cache: dict[str, bytes] = {}
        self.latest_audio: bytes | None = None

    def get_audio(self, transmission_id: str) -> bytes | None:
        return self.audio_cache.get(transmission_id) or self.latest_audio

    def has_audio(self) -> bool:
        return bool(self.audio_cache or self.latest_audio)

    async def handle_stream(self, worker_id: str, chunk: bytes) -> None:
        if worker_id not in self.audio_buffers:
            self.audio_buffers[worker_id] = bytearray()
        self.audio_buffers[worker_id].extend(chunk)

    async def handle_status(self, worker_id: str, status: str) -> None:
        if status == "start":
            self.audio_buffers[worker_id] = bytearray()
            logger.info("[VOICE] Started recording for %s", worker_id)
        elif status == "stop":
            logger.info("[VOICE] Stopped recording for %s. Processing...", worker_id)
            audio_data = self.audio_buffers.get(worker_id)
            if audio_data:
                await self.process_audio(worker_id, bytes(audio_data))
            self.audio_buffers.pop(worker_id, None)

    async def process_audio(self, worker_id: str, audio_data: bytes) -> None:
        if len(audio_data) == 0:
            logger.warning("[VOICE] Audio is empty, discarding")
            return

        now_str = datetime.now(UTC).isoformat()
        time_code = datetime.now(UTC).strftime("%H%M%S")
        transmission_id = f"VT-{time_code}"

        # Encode PCM into in-memory WAV buffer (no local disk writes)
        try:
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(8000)
                wav_file.writeframes(audio_data)
            wav_bytes = wav_buf.getvalue()
            self.audio_cache[transmission_id] = wav_bytes
            self.latest_audio = wav_bytes
            if len(self.audio_cache) > 20:
                self.audio_cache.pop(next(iter(self.audio_cache)), None)
        except Exception as exc:
            logger.error("[VOICE] In-memory WAV encoding error: %s", exc)

        auth_header = get_wit_ai_token()
        if not auth_header:
            logger.error("[VOICE] WIT_AI_TOKEN is not configured in environment or .env")
            return

        try:
            logger.info("[VOICE] Sending %d bytes audio to Wit.ai...", len(audio_data))
            headers = {
                "Authorization": auth_header,
                "Content-Type": "audio/raw;encoding=signed-integer;bits=16;rate=8000;endian=little",
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post("https://api.wit.ai/speech", headers=headers, content=audio_data)
                if resp.status_code != 200:
                    logger.error("[VOICE] Wit.ai HTTP Error %d: %s", resp.status_code, resp.text)
                    return

                result_text = resp.text
                logger.info("[VOICE] Wit.ai Response: %s", result_text)
            final_json = None
            decoder = json.JSONDecoder()
            text_to_parse = result_text.strip()
            while text_to_parse:
                try:
                    obj, index = decoder.raw_decode(text_to_parse)
                    if isinstance(obj, dict) and obj.get("is_final"):
                        final_json = obj
                    elif isinstance(obj, dict) and final_json is None:
                        final_json = obj
                    text_to_parse = text_to_parse[index:].strip()
                except json.JSONDecodeError:
                    break

            if not final_json:
                logger.error("[VOICE] Could not parse valid JSON from Wit.ai response")
                return

            transkripsi = (final_json.get("text") or "").strip()
            if not transkripsi:
                logger.warning("[VOICE] Empty transcription from Wit.ai")
                return

            worker = next(
                (w for w in simulation_engine.state.get("workers", []) if w["id"] == worker_id),
                None,
            )
            hazards = simulation_engine.state.get("hazards", [])

            nlu_result = parse_safety_intent(transkripsi, worker, hazards)
            matched_hz = nlu_result["matched_hazard"]

            transmission = {
                "id": transmission_id,
                "timestamp": now_str,
                "worker_id": worker_id,
                "worker_name": worker["name"] if worker else f"Pekerja {worker_id}",
                "worker_role": worker.get("role", "Operator") if worker else "Operator",
                "area": nlu_result["detected_area"],
                "transcription": transkripsi,
                "intent": nlu_result["intent"],
                "intent_label": nlu_result["intent_label"],
                "urgency": nlu_result["urgency"],
                "nature": nlu_result["nature"],
                "confidence": nlu_result["confidence"],
                "target_hazard_id": matched_hz.get("id") if matched_hz else None,
                "target_hazard_name": matched_hz.get("name") if matched_hz else None,
                "target_hazard_type": matched_hz.get("type") if matched_hz else None,
                "recommended_action": nlu_result["recommended_action"],
                "acknowledged": False,
                "acknowledged_by": None,
                "supervisor_note": "",
                "audio_available": True,
                "audio_url": f"/api/v1/voice/audio/{transmission_id}",
            }

            if "voice_transmissions" not in simulation_engine.state:
                simulation_engine.state["voice_transmissions"] = []
            simulation_engine.state["voice_transmissions"].insert(0, transmission)
            if len(simulation_engine.state["voice_transmissions"]) > 40:
                simulation_engine.state["voice_transmissions"].pop()

            # Auto-escalate near miss for critical/high safety events
            if nlu_result["urgency"] in ("CRITICAL", "HIGH"):
                nm_event = {
                    "id": f"NM-V{time_code}",
                    "timestamp": now_str,
                    "worker_id": worker_id,
                    "worker_name": worker["name"] if worker else worker_id,
                    "hazard_id": matched_hz.get("id") if matched_hz else (worker.get("closest_hazard") or "F01"),
                    "hazard_name": matched_hz.get("name") if matched_hz else (worker.get("hazard_name") or "Laporan Bahaya Suara"),
                    "hazard_type": matched_hz.get("type") if matched_hz else "VOICE_HAZARD",
                    "proximity": "CRITICAL" if nlu_result["urgency"] == "CRITICAL" else "HIGH",
                    "rssi": worker.get("rssi", -52) if worker else -52,
                    "duration": 5.0,
                    "hazard_status": "ACTIVE",
                    "risk_score": 96 if nlu_result["urgency"] == "CRITICAL" else 76,
                    "risk_level": nlu_result["urgency"],
                    "warning_status": "DELIVERED",
                    "acknowledged": False,
                    "note": f"Laporan Suara ({nlu_result['intent_label']}): \"{transkripsi}\"",
                }
                if "near_misses" in simulation_engine.state:
                    simulation_engine.state["near_misses"].insert(0, nm_event)
                await websocket_manager.broadcast("near_miss.created", nm_event)
                await db_service.persist_near_miss(nm_event)

                if worker:
                    if nlu_result["urgency"] == "CRITICAL":
                        worker["risk_level"] = "CRITICAL"
                        worker["risk_score"] = max(worker.get("risk_score", 0), 96)
                    elif nlu_result["urgency"] == "HIGH" and worker.get("risk_level") not in ("CRITICAL", "HIGH"):
                        worker["risk_level"] = "HIGH"
                        worker["risk_score"] = max(worker.get("risk_score", 0), 76)
                    worker["dominant_factor"] = f"Laporan Suara ({nlu_result['intent_label']})"
                    worker["recommended_action"] = nlu_result["recommended_action"]
                    await websocket_manager.broadcast("worker.updated", worker)

            if "activities" in simulation_engine.state:
                simulation_engine.state["activities"].insert(0, {
                    "id": f"act-v{time_code}",
                    "type": "VOICE_DISPATCH",
                    "message": f"Transmisi Suara [{nlu_result['urgency']}] {transmission['worker_name']}: \"{transkripsi}\"",
                    "timestamp": now_str,
                })

            await websocket_manager.broadcast("voice.transmission", transmission)
            await websocket_manager.broadcast("voice.command", {
                "worker_id": worker_id,
                "transcription": transkripsi,
                "action": nlu_result["intent"],
                "urgency": nlu_result["urgency"],
                "message": nlu_result["intent_label"],
            })

            logger.info("[VOICE] Processed %s: %s -> %s", transmission_id, transkripsi, nlu_result["intent_label"])

        except Exception as exc:
            logger.error("[VOICE] Wit.ai processing error: %s", exc, exc_info=True)


voice_service = VoiceService()

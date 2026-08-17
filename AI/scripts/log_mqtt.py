#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from reksa_ai.mqtt_logger import CsvMqttLogger


def main() -> None:
    parser = argparse.ArgumentParser(description="Log validated REKSA helmet MQTT data to CSV")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic", default="REKSA/helmet/+/sensor")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--mq135-baseline", type=float)
    parser.add_argument("--username")
    parser.add_argument("--password-env", default="MQTT_PASSWORD")
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--ca-cert")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    context = {
        "participant_id": args.participant,
        "session_id": args.session,
        "scenario_id": args.scenario,
        "trajectory_id": args.trajectory,
    }
    if args.mq135_baseline is not None:
        context["mq135_baseline"] = str(args.mq135_baseline)
    password = os.getenv(args.password_env) if args.username else None
    if args.username and not password:
        parser.error(f"{args.password_env} must be set when --username is used")
    CsvMqttLogger(args.output, context).run(
        args.host,
        args.port,
        args.topic,
        username=args.username,
        password=password,
        use_tls=args.tls,
        ca_cert=args.ca_cert,
    )


if __name__ == "__main__":
    main()

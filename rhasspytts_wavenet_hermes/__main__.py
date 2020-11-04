"""Hermes MQTT service for Rhasspy TTS with Google Wavenet."""
import argparse
import asyncio
import logging
from pathlib import Path

import paho.mqtt.client as mqtt

import rhasspyhermes.cli as hermes_cli

from . import TtsHermesMqtt

_LOGGER = logging.getLogger("rhasspytts_wavenet_hermes")

# -----------------------------------------------------------------------------


def main():
    """Main method."""
    parser = argparse.ArgumentParser(prog="rhasspy-tts-wavenet-hermes")
    parser.add_argument(
        "--credentials-json",
        required=True,
        help="Path to Google Wavenet credentials JSON file",
    )
    parser.add_argument(
        "--cache-dir", required=True, help="Directory to cache WAV files"
    )
    parser.add_argument(
        "--voice",
        default="en-US-Wavenet-C",
        help="Chosen voice (default: en-US-Wavenet-C)",
    )
    parser.add_argument(
        "--sample-rate",
        default=22050,
        type=int,
        help="Chosen sample rate of the outpt wave sample (default: 22050)",
    )
    parser.add_argument(
        "--play-command",
        help="Command to play WAV data from stdin (default: publish playBytes)",
    )
    parser.add_argument(
        "--volume", type=float, help="Volume scale for output audio (0-1, default: 1)"
    )

    hermes_cli.add_hermes_args(parser)
    args = parser.parse_args()

    hermes_cli.setup_logging(args)
    _LOGGER.debug(args)

    args.credentials_json = Path(args.credentials_json)
    args.cache_dir = Path(args.cache_dir)

    # Listen for messages
    client = mqtt.Client()
    hermes = TtsHermesMqtt(
        client,
        credentials_json=args.credentials_json,
        cache_dir=args.cache_dir,
        voice=args.voice,
        sample_rate=args.sample_rate,
        play_command=args.play_command,
        volume=args.volume,
        site_ids=args.site_id,
    )

    _LOGGER.debug("Connecting to %s:%s", args.host, args.port)
    hermes_cli.connect(client, args)
    client.loop_start()

    try:
        # Run event loop
        asyncio.run(hermes.handle_messages_async())
    except KeyboardInterrupt:
        pass
    finally:
        _LOGGER.debug("Shutting down")
        client.loop_stop()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()

"""Hermes MQTT service for Rhasspy TTS with Google Wavenet."""
import argparse
import asyncio
import logging

import paho.mqtt.client as mqtt
import rhasspyhermes.cli as hermes_cli

from . import TtsHermesMqtt

_LOGGER = logging.getLogger("rhasspytts_wavenet_hermes")

# -----------------------------------------------------------------------------


def main():
    """Main method."""
    parser = argparse.ArgumentParser(prog="rhasspy-tts-wavenet-hermes")
    parser.add_argument(
        "--wavenet_dir",
        required=True,
        help="Directory of the Google Wavenet cache and credentials",
    )
    parser.add_argument(
        "--voice",
        required=True,
        help="Chosen voice",
    )
    parser.add_argument(
        "--gender",
        required=True,
        help="Chosen gender",
    )
    parser.add_argument(
        "--sample_rate",
        required=True,
        help="Chosen sample rate of the outpt wave sample",
    )
    parser.add_argument(
        "--language_code",
        required=True,
        help="Chosen language",
    )
    parser.add_argument(
        "--play-command",
        help="Command to play WAV data from stdin (default: publish playBytes)",
    )

    hermes_cli.add_hermes_args(parser)
    args = parser.parse_args()

    hermes_cli.setup_logging(args)
    _LOGGER.debug(args)

    # Listen for messages
    client = mqtt.Client()
    hermes = TtsHermesMqtt(
        client,
        wavenet_dir=args.wavenet_dir,
        voice=args.voice,
        gender=args.gender,
        sample_rate=args.sample_rate,
        language_code=args.language_code,
        play_command=args.play_command,
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


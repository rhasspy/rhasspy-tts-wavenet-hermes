"""Hermes MQTT service for Rhasspy wakeword with pocketsphinx"""
import argparse
import asyncio
import logging
from pathlib import Path

import paho.mqtt.client as mqtt
import rhasspyhermes.cli as hermes_cli

from . import WakeHermesMqtt

_LOGGER = logging.getLogger("rhasspywake_pocketsphinx_hermes")

# -----------------------------------------------------------------------------


def main():
    """Main method."""
    parser = argparse.ArgumentParser(prog="rhasspy-wake-pocketsphinx-hermes")
    parser.add_argument(
        "--acoustic-model",
        required=True,
        help="Path to Pocketsphinx acoustic model directory (hmm)",
    )
    parser.add_argument(
        "--dictionary",
        required=True,
        action="append",
        help="Path to pronunciation dictionary file(s)",
    )
    parser.add_argument(
        "--keyphrase", required=True, help="Keyword phrase to listen for"
    )
    parser.add_argument(
        "--keyphrase-threshold",
        type=float,
        default=1e-40,
        help="Threshold for keyphrase (default: 1e-40)",
    )
    parser.add_argument(
        "--mllr-matrix", default=None, help="Path to tuned MLLR matrix file"
    )
    parser.add_argument(
        "--wakeword-id",
        default="",
        help="Wakeword ID of each keyphrase (default: use keyphrase)",
    )
    parser.add_argument(
        "--udp-audio",
        nargs=3,
        action="append",
        help="Host/port/siteId for UDP audio input",
    )

    hermes_cli.add_hermes_args(parser)
    args = parser.parse_args()

    hermes_cli.setup_logging(args)
    _LOGGER.debug(args)

    # Convert to paths
    args.acoustic_model = Path(args.acoustic_model)
    args.dictionary = [Path(d) for d in args.dictionary]

    if args.mllr_matrix:
        args.mllr_matrix = Path(args.mllr_matrix)

    udp_audio = []
    if args.udp_audio:
        udp_audio = [
            (host, int(port), site_id) for host, port, site_id in args.udp_audio
        ]

    # Listen for messages
    client = mqtt.Client()
    hermes = WakeHermesMqtt(
        client,
        args.keyphrase,
        args.acoustic_model,
        args.dictionary,
        wakeword_id=args.wakeword_id,
        keyphrase_threshold=args.keyphrase_threshold,
        mllr_matrix=args.mllr_matrix,
        udp_audio=udp_audio,
        site_ids=args.site_id,
        debug=args.debug,
    )

    hermes.load_decoder()

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

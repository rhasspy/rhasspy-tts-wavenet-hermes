"""Hermes MQTT server for Rhasspy wakeword with pocketsphinx"""
import asyncio
import logging
import queue
import socket
import tempfile
import threading
import typing
from pathlib import Path

import pocketsphinx
from rhasspyhermes.audioserver import AudioFrame
from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient, TopicArgs
from rhasspyhermes.wake import (
    HotwordDetected,
    HotwordError,
    HotwordToggleOff,
    HotwordToggleOn,
    HotwordToggleReason,
)

WAV_HEADER_BYTES = 44
_LOGGER = logging.getLogger("rhasspywake_pocketsphinx_hermes")

# -----------------------------------------------------------------------------


class WakeHermesMqtt(HermesClient):
    """Hermes MQTT server for Rhasspy wakeword with pocketsphinx."""

    def __init__(
        self,
        client,
        keyphrase: str,
        acoustic_model: Path,
        dictionary_paths: typing.List[Path],
        wakeword_id: str = "",
        keyphrase_threshold: float = 1e-40,
        mllr_matrix: typing.Optional[Path] = None,
        site_ids: typing.Optional[typing.List[str]] = None,
        enabled: bool = True,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        chunk_size: int = 960,
        udp_audio: typing.Optional[typing.List[typing.Tuple[str, int, str]]] = None,
        udp_chunk_size: int = 2048,
        debug: bool = False,
    ):
        super().__init__(
            "rhasspywake_pocketsphinx_hermes",
            client,
            sample_rate=sample_rate,
            sample_width=sample_width,
            channels=channels,
            site_ids=site_ids,
        )

        self.subscribe(AudioFrame, HotwordToggleOn, HotwordToggleOff)

        self.keyphrase = keyphrase
        self.keyphrase_threshold = keyphrase_threshold

        self.acoustic_model = acoustic_model
        self.dictionary_paths = dictionary_paths
        self.mllr_matrix = mllr_matrix

        self.wakeword_id = wakeword_id
        self.enabled = enabled
        self.disabled_reasons: typing.Set[str] = set()

        # Required audio format
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels

        self.chunk_size = chunk_size

        # Queue of WAV audio chunks to process (plus site_id)
        self.wav_queue: queue.Queue = queue.Queue()

        self.first_audio: bool = True
        self.audio_buffer = bytes()

        self.decoder: typing.Optional[pocketsphinx.Decoder] = []
        self.decoder_started = False
        self.debug = debug

        # Start threads
        threading.Thread(target=self.detection_thread_proc, daemon=True).start()

        # Listen for raw audio on UDP too
        self.udp_chunk_size = udp_chunk_size

        if udp_audio:
            for udp_host, udp_port, udp_site_id in udp_audio:
                threading.Thread(
                    target=self.udp_thread_proc,
                    args=(udp_host, udp_port, udp_site_id),
                    daemon=True,
                ).start()

    # -------------------------------------------------------------------------

    def load_decoder(self):
        """Load Pocketsphinx decoder."""
        _LOGGER.debug(
            "Loading decoder with hmm=%s, dicts=%s",
            str(self.acoustic_model),
            self.dictionary_paths,
        )

        words_needed = set(self.keyphrase.split())

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt") as dict_file:
            # Combine all dictionaries
            for sub_dict_path in self.dictionary_paths:
                if not sub_dict_path.is_file():
                    _LOGGER.warning("Skipping dictionary %s", str(sub_dict_path))
                    continue

                with open(sub_dict_path, "r") as sub_dict_file:
                    for line in sub_dict_file:
                        line = line.strip()
                        if line:
                            word = line.split(maxsplit=2)[0]
                            if word in words_needed:
                                print(line, file=dict_file)
                                words_needed.remove(word)

            assert (
                len(words_needed) == 0
            ), f"Missing pronunciations for words: {words_needed}"
            dict_file.seek(0)

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string("-hmm", str(self.acoustic_model))
            decoder_config.set_string("-dict", str(dict_file.name))
            decoder_config.set_string("-keyphrase", self.keyphrase)
            decoder_config.set_float("-kws_threshold", self.keyphrase_threshold)

            if not self.debug:
                decoder_config.set_string("-logfn", "/dev/null")

            if self.mllr_matrix and self.mllr_matrix.is_file():
                decoder_config.set_string("-mllr", str(self.mllr_matrix))

            self.decoder = pocketsphinx.Decoder(decoder_config)

    # -------------------------------------------------------------------------

    async def handle_audio_frame(self, wav_bytes: bytes, site_id: str = "default"):
        """Process a single audio frame"""
        self.wav_queue.put((wav_bytes, site_id))

    async def handle_detection(
        self, wakeword_id: str, site_id: str = "default"
    ) -> typing.AsyncIterable[
        typing.Union[typing.Tuple[HotwordDetected, TopicArgs], HotwordError]
    ]:
        """Handle a successful hotword detection"""
        try:
            yield (
                HotwordDetected(
                    site_id=site_id,
                    model_id=self.keyphrase,
                    current_sensitivity=self.keyphrase_threshold,
                    model_version="",
                    model_type="personal",
                ),
                {"wakeword_id": wakeword_id},
            )
        except Exception as e:
            _LOGGER.exception("handle_detection")
            yield HotwordError(error=str(e), context=self.keyphrase, site_id=site_id)

    def detection_thread_proc(self):
        """Handle WAV audio chunks."""
        try:
            while True:
                wav_bytes, site_id = self.wav_queue.get()
                if self.first_audio:
                    _LOGGER.debug("Receiving audio")
                    self.first_audio = False

                if not self.decoder:
                    self.load_decoder()

                assert self.decoder is not None

                # Extract/convert audio data
                audio_data = self.maybe_convert_wav(wav_bytes)

                # Add to persistent buffer
                self.audio_buffer += audio_data

                # Process in chunks.
                # Any remaining audio data will be kept in buffer.
                while len(self.audio_buffer) >= self.chunk_size:
                    chunk = self.audio_buffer[: self.chunk_size]
                    self.audio_buffer = self.audio_buffer[self.chunk_size :]

                    if not self.decoder_started:
                        # Begin utterance
                        self.decoder.start_utt()
                        self.decoder_started = True

                    self.decoder.process_raw(chunk, False, False)
                    hyp = self.decoder.hyp()
                    if hyp:
                        if self.decoder_started:
                            # End utterance
                            self.decoder.end_utt()
                            self.decoder_started = False

                        wakeword_id = self.wakeword_id
                        if not wakeword_id:
                            wakeword_id = self.keyphrase

                        asyncio.run_coroutine_threadsafe(
                            self.publish_all(
                                self.handle_detection(wakeword_id, site_id=site_id)
                            ),
                            self.loop,
                        )

                        # Stop and clear buffer to avoid duplicate reports
                        self.audio_buffer = bytes()
                        break

        except Exception:
            _LOGGER.exception("detection_thread_proc")

    # -------------------------------------------------------------------------

    def udp_thread_proc(self, host: str, port: int, site_id: str):
        """Handle WAV chunks from UDP socket."""
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind((host, port))
            _LOGGER.debug("Listening for audio on UDP %s:%s", host, port)

            while True:
                wav_bytes, _ = udp_socket.recvfrom(
                    self.udp_chunk_size + WAV_HEADER_BYTES
                )

                if self.enabled:
                    self.wav_queue.put((wav_bytes, site_id))
        except Exception:
            _LOGGER.exception("udp_thread_proc")

    # -------------------------------------------------------------------------

    async def on_message_blocking(
        self,
        message: Message,
        site_id: typing.Optional[str] = None,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        """Received message from MQTT broker."""
        # Check enable/disable messages
        if isinstance(message, HotwordToggleOn):
            if message.reason == HotwordToggleReason.UNKNOWN:
                # Always enable on unknown
                self.disabled_reasons.clear()
            else:
                self.disabled_reasons.discard(message.reason)

            if self.disabled_reasons:
                _LOGGER.debug("Still disabled: %s", self.disabled_reasons)
            else:
                self.enabled = True
                self.first_audio = True
                _LOGGER.debug("Enabled")
        elif isinstance(message, HotwordToggleOff):
            self.enabled = False
            self.disabled_reasons.add(message.reason)

            # End utterance
            if self.decoder and self.decoder_started:
                self.decoder.end_utt()
                self.decoder_started = False

            _LOGGER.debug("Disabled")
        elif isinstance(message, AudioFrame):
            if self.enabled:
                assert site_id, "Missing site_id"
                await self.handle_audio_frame(message.wav_bytes, site_id=site_id)
        else:
            _LOGGER.warning("Unexpected message: %s", message)

        # Mark as async generator
        yield None

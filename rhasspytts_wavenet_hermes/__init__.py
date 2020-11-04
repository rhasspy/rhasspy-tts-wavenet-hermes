"""Hermes MQTT server for Rhasspy TTS using Google Wavenet"""
import asyncio
import audioop
import hashlib
import io
import logging
import os
import shlex
import subprocess
import typing
import wave
from pathlib import Path
from uuid import uuid4

from google.cloud import texttospeech

from rhasspyhermes.audioserver import AudioPlayBytes, AudioPlayError, AudioPlayFinished
from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient, TopicArgs
from rhasspyhermes.tts import GetVoices, TtsError, TtsSay, TtsSayFinished, Voice, Voices

_LOGGER = logging.getLogger("rhasspytts_wavenet_hermes")

# -----------------------------------------------------------------------------


class TtsHermesMqtt(HermesClient):
    """Hermes MQTT server for Rhasspy TTS using Google Wavenet."""

    def __init__(
        self,
        client,
        credentials_json: Path,
        cache_dir: Path,
        voice: str = "en-US-Wavenet-C",
        sample_rate: int = 22050,
        play_command: typing.Optional[str] = None,
        volume: typing.Optional[float] = None,
        site_ids: typing.Optional[typing.List[str]] = None,
    ):
        super().__init__("rhasspytts_wavenet_hermes", client, site_ids=site_ids)

        self.subscribe(TtsSay, GetVoices, AudioPlayFinished)

        self.credentials_json = credentials_json
        self.cache_dir = cache_dir
        self.voice = voice
        self.sample_rate = int(sample_rate)
        self.play_command = play_command
        self.volume = volume

        self.play_finished_events: typing.Dict[typing.Optional[str], asyncio.Event] = {}

        # Seconds added to playFinished timeout
        self.finished_timeout_extra: float = 0.25

        self.wavenet_client: typing.Optional[texttospeech.TextToSpeechClient] = None

        # Create cache directory in profile if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if (not self.wavenet_client) and self.credentials_json.is_file():
            _LOGGER.debug("Loading credentials at %s", self.credentials_json)

            # Set environment var
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                self.credentials_json.absolute()
            )

            self.wavenet_client = texttospeech.TextToSpeechClient()

    # -------------------------------------------------------------------------

    async def handle_say(
        self, say: TtsSay
    ) -> typing.AsyncIterable[
        typing.Union[
            TtsSayFinished,
            typing.Tuple[AudioPlayBytes, TopicArgs],
            TtsError,
            AudioPlayError,
        ]
    ]:
        """Run TTS system and publish WAV data."""
        wav_bytes: typing.Optional[bytes] = None

        try:
            # Try to pull WAV from cache first
            sentence_hash = self.get_sentence_hash(say.text)
            cached_wav_path = self.cache_dir / f"{sentence_hash.hexdigest()}.wav"
            from_cache = False

            if cached_wav_path.is_file():
                # Use WAV file from cache
                _LOGGER.debug("Using WAV from cache: %s", cached_wav_path)
                wav_bytes = cached_wav_path.read_bytes()
                from_cache = True

            if not wav_bytes:
                # Run text to speech
                assert self.wavenet_client, "No Wavenet Client"

                _LOGGER.debug(
                    "Calling Wavenet (voice=%s, rate=%s)", self.voice, self.sample_rate
                )

                if say.text.startswith("<speak>"):
                    synthesis_input = texttospeech.SynthesisInput(ssml=say.text)
                else:
                    synthesis_input = texttospeech.SynthesisInput(text=say.text)

                voice_params = texttospeech.VoiceSelectionParams(
                    language_code="-".join(self.voice.split("-")[:2]), name=self.voice
                )

                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=self.sample_rate,
                )

                response = self.wavenet_client.synthesize_speech(
                    request={
                        "input": synthesis_input,
                        "voice": voice_params,
                        "audio_config": audio_config,
                    }
                )
                wav_bytes = response.audio_content

            assert wav_bytes, "No WAV data received"
            _LOGGER.debug("Got %s byte(s) of WAV data", len(wav_bytes))

            # Adjust volume
            volume = self.volume
            if say.volume is not None:
                # Override with message volume
                volume = say.volume

            original_wav_bytes = wav_bytes
            if volume is not None:
                wav_bytes = TtsHermesMqtt.change_volume(wav_bytes, volume)

            finished_event = asyncio.Event()

            # Play WAV
            if self.play_command:
                try:
                    # Play locally
                    play_command = shlex.split(self.play_command.format(lang=say.lang))
                    _LOGGER.debug(play_command)

                    subprocess.run(play_command, input=wav_bytes, check=True)

                    # Don't wait for playFinished
                    finished_event.set()
                except Exception as e:
                    _LOGGER.exception("play_command")
                    yield AudioPlayError(
                        error=str(e),
                        context=say.id,
                        site_id=say.site_id,
                        session_id=say.session_id,
                    )
            else:
                # Publish playBytes
                request_id = say.id or str(uuid4())
                self.play_finished_events[request_id] = finished_event

                yield (
                    AudioPlayBytes(wav_bytes=wav_bytes),
                    {"site_id": say.site_id, "request_id": request_id},
                )

            # Save to cache
            if not from_cache:
                with open(cached_wav_path, "wb") as cached_wav_file:
                    cached_wav_file.write(original_wav_bytes)

            try:
                # Wait for audio to finished playing or timeout
                wav_duration = TtsHermesMqtt.get_wav_duration(wav_bytes)
                wav_timeout = wav_duration + self.finished_timeout_extra

                _LOGGER.debug("Waiting for play finished (timeout=%s)", wav_timeout)
                await asyncio.wait_for(finished_event.wait(), timeout=wav_timeout)
            except asyncio.TimeoutError:
                _LOGGER.warning("Did not receive playFinished before timeout")

        except Exception as e:
            _LOGGER.exception("handle_say")
            yield TtsError(
                error=str(e),
                context=say.id,
                site_id=say.site_id,
                session_id=say.session_id,
            )
        finally:
            yield TtsSayFinished(
                id=say.id, site_id=say.site_id, session_id=say.session_id
            )

    # -------------------------------------------------------------------------

    async def handle_get_voices(
        self, get_voices: GetVoices
    ) -> typing.AsyncIterable[typing.Union[Voices, TtsError]]:
        """Publish list of available voices."""
        voices: typing.List[Voice] = []
        try:
            if self.wavenet_client:
                response = self.wavenet_client.list_voices()
                voicelist = sorted(response.voices, key=lambda voice: voice.name)
                for item in voicelist:
                    voice = Voice(voice_id=item.name)
                    voice.description = texttospeech.SsmlVoiceGender(
                        item.ssml_gender
                    ).name
                    voices.append(voice)

        except Exception as e:
            _LOGGER.exception("handle_get_voices")
            yield TtsError(
                error=str(e), context=get_voices.id, site_id=get_voices.site_id
            )

        # Publish response
        yield Voices(voices=voices, id=get_voices.id, site_id=get_voices.site_id)

    # -------------------------------------------------------------------------

    async def on_message(
        self,
        message: Message,
        site_id: typing.Optional[str] = None,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        """Received message from MQTT broker."""
        if isinstance(message, TtsSay):
            async for say_result in self.handle_say(message):
                yield say_result
        elif isinstance(message, GetVoices):
            async for voice_result in self.handle_get_voices(message):
                yield voice_result
        elif isinstance(message, AudioPlayFinished):
            # Signal audio play finished
            finished_event = self.play_finished_events.pop(message.id, None)
            if finished_event:
                finished_event.set()
        else:
            _LOGGER.warning("Unexpected message: %s", message)

    # -------------------------------------------------------------------------

    def get_sentence_hash(self, sentence: str):
        """Get hash for cache."""
        m = hashlib.md5()
        m.update(
            "_".join([sentence, self.voice, str(self.sample_rate)]).encode("utf-8")
        )

        return m

    @staticmethod
    def get_wav_duration(wav_bytes: bytes) -> float:
        """Return the real-time duration of a WAV file"""
        with io.BytesIO(wav_bytes) as wav_buffer:
            wav_file: wave.Wave_read = wave.open(wav_buffer, "rb")
            with wav_file:
                width = wav_file.getsampwidth()
                rate = wav_file.getframerate()

                # getnframes is not reliable.
                # espeak inserts crazy large numbers.
                guess_frames = (len(wav_bytes) - 44) / width

                return guess_frames / float(rate)

    # -------------------------------------------------------------------------

    @staticmethod
    def change_volume(wav_bytes: bytes, volume: float) -> bytes:
        """Scale WAV amplitude by factor (0-1)"""
        if volume == 1.0:
            return wav_bytes

        try:
            with io.BytesIO(wav_bytes) as wav_in_io:
                # Re-write WAV with adjusted volume
                with io.BytesIO() as wav_out_io:
                    wav_out_file: wave.Wave_write = wave.open(wav_out_io, "wb")
                    wav_in_file: wave.Wave_read = wave.open(wav_in_io, "rb")

                    with wav_out_file:
                        with wav_in_file:
                            sample_width = wav_in_file.getsampwidth()

                            # Copy WAV details
                            wav_out_file.setframerate(wav_in_file.getframerate())
                            wav_out_file.setsampwidth(sample_width)
                            wav_out_file.setnchannels(wav_in_file.getnchannels())

                            # Adjust amplitude
                            wav_out_file.writeframes(
                                audioop.mul(
                                    wav_in_file.readframes(wav_in_file.getnframes()),
                                    sample_width,
                                    volume,
                                )
                            )

                    wav_bytes = wav_out_io.getvalue()

        except Exception:
            _LOGGER.exception("change_volume")

        return wav_bytes

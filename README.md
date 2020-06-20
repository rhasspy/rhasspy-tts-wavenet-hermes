# Rhasspy TTS Hermes MQTT Service

[![Continous Integration](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/workflows/Tests/badge.svg)](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/actions)
[![GitHub license](https://img.shields.io/github/license/rhasspy/rhasspy-tts-wavenet-hermes.svg)](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/blob/master/LICENSE)

Implements `hermes/tts` functionality from [Hermes protocol](https://docs.snips.ai/reference/hermes) using Google Wavenet

* [Google Wavenet](https://cloud.google.com/text-to-speech/docs/wavenet)

Use `--play-command aplay` to play speech locally instead of using `hermes/audioServer<siteId>/playBytes`.

## Running With Docker

```bash
docker run -it rhasspy/rhasspy-tts-wavenet-hermes:<VERSION> <ARGS>
```

## Building From Source

Clone the repository and create the virtual environment:

```bash
git clone https://github.com/rhasspy/rhasspy-tts-wavenet-hermes.git
cd rhasspy-tts-wavenet-hermes
make venv
```

Run the `bin/rhasspy-tts-wavenet-hermes` script to access the command-line interface:

```bash
bin/rhasspy-tts-wavenet-hermes --help
```

## Building the Debian Package

Follow the instructions to build from source, then run:

```bash
source .venv/bin/activate
make debian
```

If successful, you'll find a `.deb` file in the `dist` directory that can be installed with `apt`.

## Building the Docker Image

Follow the instructions to build from source, then run:

```bash
source .venv/bin/activate
make docker
```

This will create a Docker image tagged `rhasspy/rhasspy-tts-wavenet-hermes:<VERSION>` where `VERSION` comes from the file of the same name in the source root directory.

NOTE: If you add things to the Docker image, make sure to whitelist them in `.dockerignore`.

## Command-Line Options

```
usage: rhasspy-tts-wavenet-hermes [-h] 
                              [--wavenet_dir] [--voice] [--gender] [--sample_rate] [--language_code]
                              [--play-command PLAY_COMMAND] [--host HOST]
                              [--port PORT] [--siteId SITEID] [--debug]

optional arguments:
  -h, --help            show this help message and exit
  --wavenet_dir         Directory of the Google Wavenet cache and credentials
  --voice               Chosen voice
  --gender              Chosen gender
  --sample_rate         Chosen sample rate of the outpt wave sample
  --language_code     Chosen language
  --play-command PLAY_COMMAND
                        Command to play WAV data from stdin (default: publish
                        playBytes)
  --host HOST           MQTT host (default: localhost)
  --port PORT           MQTT port (default: 1883)
  --siteId SITEID       Hermes siteId of this server
  --debug               Print DEBUG messages to the console
```


# Rhasspy TTS Hermes MQTT Service

[![Continous Integration](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/workflows/Tests/badge.svg)](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/actions)
[![GitHub license](https://img.shields.io/github/license/rhasspy/rhasspy-tts-wavenet-hermes.svg)](https://github.com/rhasspy/rhasspy-tts-wavenet-hermes/blob/master/LICENSE)

Implements `hermes/tts` functionality from [Hermes protocol](https://docs.snips.ai/reference/hermes) using [Google Wavenet](https://cloud.google.com/text-to-speech/docs/wavenet).

See [documentation](https://rhasspy.readthedocs.io/en/latest/text-to-speech/#google-wavenet) for more details.

Use `--play-command aplay` to play speech locally instead of using `hermes/audioServer<siteId>/playBytes`.

## Installing

Clone the repository and create a virtual environment:

```bash
$ git clone https://github.com/rhasspy/rhasspy-tts-wavenet-hermes.git
$ cd rhasspy-tts-wavenet-hermes
$ ./configure
$ make
$ make install
```

## Command-Line Options

```
usage: rhasspy-tts-wavenet-hermes [-h] --credentials-json CREDENTIALS_JSON
                                  --cache-dir CACHE_DIR [--voice VOICE]
                                  [--sample-rate SAMPLE_RATE]
                                  [--play-command PLAY_COMMAND] [--host HOST]
                                  [--port PORT] [--username USERNAME]
                                  [--password PASSWORD] [--tls]
                                  [--tls-ca-certs TLS_CA_CERTS]
                                  [--tls-certfile TLS_CERTFILE]
                                  [--tls-keyfile TLS_KEYFILE]
                                  [--tls-cert-reqs {CERT_REQUIRED,CERT_OPTIONAL,CERT_NONE}]
                                  [--tls-version TLS_VERSION]
                                  [--tls-ciphers TLS_CIPHERS]
                                  [--site-id SITE_ID] [--debug]
                                  [--log-format LOG_FORMAT]

optional arguments:
  -h, --help            show this help message and exit
  --credentials-json CREDENTIALS_JSON
                        Path to Google Wavenet credentials JSON file
  --cache-dir CACHE_DIR
                        Directory to cache WAV files
  --voice VOICE         Chosen voice (default: en-US-Wavenet-C)
  --sample-rate SAMPLE_RATE
                        Chosen sample rate of the outpt wave sample (default:
                        22050)
  --play-command PLAY_COMMAND
                        Command to play WAV data from stdin (default: publish
                        playBytes)
  --host HOST           MQTT host (default: localhost)
  --port PORT           MQTT port (default: 1883)
  --username USERNAME   MQTT username
  --password PASSWORD   MQTT password
  --tls                 Enable MQTT TLS
  --tls-ca-certs TLS_CA_CERTS
                        MQTT TLS Certificate Authority certificate files
  --tls-certfile TLS_CERTFILE
                        MQTT TLS certificate file (PEM)
  --tls-keyfile TLS_KEYFILE
                        MQTT TLS key file (PEM)
  --tls-cert-reqs {CERT_REQUIRED,CERT_OPTIONAL,CERT_NONE}
                        MQTT TLS certificate requirements (default:
                        CERT_REQUIRED)
  --tls-version TLS_VERSION
                        MQTT TLS version (default: highest)
  --tls-ciphers TLS_CIPHERS
                        MQTT TLS ciphers to use
  --site-id SITE_ID     Hermes site id(s) to listen for (default: all)
  --debug               Print DEBUG messages to the console
  --log-format LOG_FORMAT
                        Python logger format
```


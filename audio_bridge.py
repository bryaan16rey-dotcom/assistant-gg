"""Stream only the selected OBS monitor input to the private Cloudflare relay."""

import argparse
import getpass
import io
import os
import queue
import sys
import time
import wave
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import sounddevice as sd

SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_SECONDS = 5
DEFAULT_DEVICE_NAME = "CABLE Output"


def find_input_device(query: str):
    devices = sd.query_devices()
    if query.isdigit():
        index = int(query)
        device = sd.query_devices(index)
        if device["max_input_channels"] > 0:
            return index, device
        raise RuntimeError(f"El dispositivo {index} no tiene entrada de audio.")

    matches = [
        (index, device) for index, device in enumerate(devices)
        if device["max_input_channels"] > 0 and query.casefold() in device["name"].casefold()
    ]
    if not matches:
        raise RuntimeError(
            f"No encontré una entrada de audio que contenga {query!r}. "
            "Ejecuta `python audio_bridge.py --list-devices` para ver las entradas disponibles."
        )
    return matches[0]


def make_wav(raw_audio: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(raw_audio)
    return buffer.getvalue()


def send_chunk(url: str, token: str, wav_audio: bytes) -> None:
    request = Request(
        f"{url.rstrip('/')}/v1/audio",
        data=wav_audio,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "audio/wav",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 201:
                raise RuntimeError(f"El puente respondió HTTP {response.status}.")
    except HTTPError as error:
        raise RuntimeError(f"El puente respondió HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError("No se pudo conectar con Cloudflare.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="Lista entradas de audio disponibles")
    args = parser.parse_args()

    if args.list_devices:
        for index, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                print(f"{index}: {device['name']} ({device['max_input_channels']} canal(es) de entrada)")
        return 0

    url = os.environ.get("AUDIO_BRIDGE_URL", "").strip().rstrip("/")
    token = os.environ.get("AUDIO_BRIDGE_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Token privado del puente (no se mostrará): ").strip()
    device_query = os.environ.get("AUDIO_INPUT_DEVICE", DEFAULT_DEVICE_NAME).strip()
    if not url.startswith("https://") or not token:
        print("Configura AUDIO_BRIDGE_URL y AUDIO_BRIDGE_TOKEN en esta terminal.", file=sys.stderr)
        return 2

    try:
        device_index, device = find_input_device(device_query)
        sd.check_input_settings(
            device=device_index, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype="int16"
        )
    except Exception as error:
        print(f"No se pudo preparar la entrada de audio: {error}", file=sys.stderr)
        return 2

    blocks = queue.Queue(maxsize=32)
    chunk_bytes = SAMPLE_RATE * SAMPLE_WIDTH * CHUNK_SECONDS

    def capture_callback(indata, _frames, _time_info, status):
        if status:
            return
        try:
            blocks.put_nowait(bytes(indata))
        except queue.Full:
            pass

    print(f"🎙️ Enviando solo la entrada `{device['name']}` a Cloudflare, en fragmentos de {CHUNK_SECONDS}s.")
    print("No se guarda audio en disco. Presiona Ctrl+C para detener el puente.")
    pending = bytearray()
    sent_count = 0
    try:
        with sd.RawInputStream(
            device=device_index,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=SAMPLE_RATE // 2,
            callback=capture_callback,
        ):
            while True:
                pending.extend(blocks.get())
                if len(pending) >= chunk_bytes:
                    segment = bytes(pending[:chunk_bytes])
                    del pending[:chunk_bytes]
                    send_chunk(url, token, make_wav(segment))
                    sent_count += 1
                    print(f"✅ Fragmento {sent_count} enviado ({time.strftime('%H:%M:%S')}).")
    except KeyboardInterrupt:
        print("\nPuente detenido por el usuario.")
        return 0
    except Exception as error:
        print(f"El puente se detuvo: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

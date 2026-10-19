"""Serve OBS microphone chunks locally for a temporary Cloudflare Quick Tunnel."""

import argparse
import getpass
import hmac
import os
import queue
import sys
import threading
import time
import wave
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import sounddevice as sd

SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_SECONDS = 5
MAX_PENDING_CHUNKS = 24
DEFAULT_DEVICE_NAME = "CABLE Output"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


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
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(raw_audio)
    return buffer.getvalue()


class AudioQueue:
    """Small in-memory FIFO; old audio is dropped rather than written to disk."""

    def __init__(self):
        self._items = deque()
        self._lock = threading.Lock()
        self._next_id = 0

    def add(self, wav_audio: bytes) -> bool:
        dropped = False
        with self._lock:
            if len(self._items) >= MAX_PENDING_CHUNKS:
                self._items.popleft()
                dropped = True
            item_id = str(self._next_id)
            self._next_id += 1
            self._items.append((item_id, wav_audio))
        return dropped

    def peek(self):
        with self._lock:
            return self._items[0] if self._items else None

    def acknowledge(self, item_id: str) -> bool:
        with self._lock:
            if self._items and hmac.compare_digest(self._items[0][0], item_id):
                self._items.popleft()
                return True
            return False


def make_handler(audio_queue: AudioQueue, token: str):
    class BridgeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            # Do not log paths, query parameters, audio text, or auth headers.
            return

        def _authorized(self) -> bool:
            received = self.headers.get("Authorization", "")
            return hmac.compare_digest(received, f"Bearer {token}")

        def _reply(self, status: int, body: bytes = b"", content_type: str = "application/json", headers=None):
            self.send_response(status)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(body)))
            if body:
                self.send_header("Content-Type", content_type)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if not self._authorized():
                self._reply(401, b'{"error":"unauthorized"}')
                return
            path = urlsplit(self.path).path
            if path == "/health":
                self._reply(200, b'{"ok":true}')
                return
            if path != "/v1/audio/next":
                self._reply(404, b'{"error":"not found"}')
                return
            item = audio_queue.peek()
            if item is None:
                self._reply(204)
                return
            item_id, wav_audio = item
            self._reply(200, wav_audio, "audio/wav", {"X-Audio-Id": item_id})

        def do_DELETE(self):
            if not self._authorized():
                self._reply(401, b'{"error":"unauthorized"}')
                return
            parsed = urlsplit(self.path)
            if parsed.path != "/v1/audio/ack":
                self._reply(404, b'{"error":"not found"}')
                return
            item_id = parse_qs(parsed.query).get("id", [""])[0]
            if audio_queue.acknowledge(item_id):
                self._reply(204)
            else:
                self._reply(404, b'{"error":"audio item not found"}')

    return BridgeHandler


def start_http_server(audio_queue: AudioQueue, token: str, host: str, port: int):
    server = ThreadingHTTPServer((host, port), make_handler(audio_queue, token))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="audio-http-bridge", daemon=True)
    thread.start()
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="Lista entradas de audio disponibles")
    args = parser.parse_args()

    if args.list_devices:
        for index, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                print(f"{index}: {device['name']} ({device['max_input_channels']} canal(es) de entrada)")
        return 0

    token = os.environ.get("AUDIO_BRIDGE_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Token privado del puente (no se mostrará): ").strip()
    device_query = os.environ.get("AUDIO_INPUT_DEVICE", DEFAULT_DEVICE_NAME).strip()
    host = os.environ.get("AUDIO_BRIDGE_HOST", DEFAULT_HOST).strip()
    try:
        port = int(os.environ.get("AUDIO_BRIDGE_PORT", str(DEFAULT_PORT)))
    except ValueError:
        print("AUDIO_BRIDGE_PORT debe ser un número.", file=sys.stderr)
        return 2
    if host != DEFAULT_HOST or not (1 <= port <= 65535) or len(token) < 32:
        print(
            "El puente requiere host 127.0.0.1, un puerto válido y un token aleatorio de al menos 32 caracteres.",
            file=sys.stderr,
        )
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
    audio_queue = AudioQueue()

    def capture_callback(indata, _frames, _time_info, status):
        if status:
            return
        try:
            blocks.put_nowait(bytes(indata))
        except queue.Full:
            try:
                blocks.get_nowait()
                blocks.put_nowait(bytes(indata))
            except queue.Empty:
                pass

    try:
        server = start_http_server(audio_queue, token, host, port)
    except OSError as error:
        print(f"No se pudo abrir el puente local en {host}:{port}: {error}", file=sys.stderr)
        return 2

    print(f"🎙️ Capturando solo `{device['name']}` en fragmentos de {CHUNK_SECONDS}s.")
    print(f"Puente privado local activo en http://{host}:{port}; no se guardan archivos de audio.")
    print("En otra terminal abre: cloudflared tunnel --url http://127.0.0.1:" + str(port))
    print("Pega la URL https://*.trycloudflare.com como entrada del workflow manual.")
    print("Deja ambas terminales abiertas durante la prueba; Ctrl+C detiene este puente.")

    pending = bytearray()
    chunk_count = 0
    dropped_count = 0
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
                try:
                    pending.extend(blocks.get(timeout=0.5))
                except queue.Empty:
                    continue
                if len(pending) >= chunk_bytes:
                    segment = bytes(pending[:chunk_bytes])
                    del pending[:chunk_bytes]
                    if audio_queue.add(make_wav(segment)):
                        dropped_count += 1
                        if dropped_count == 1 or dropped_count % 12 == 0:
                            print("⚠️ El consumidor está atrasado; se descartó audio antiguo por privacidad y latencia.")
                    chunk_count += 1
                    if chunk_count == 1 or chunk_count % 12 == 0:
                        print(f"✅ Audio de micrófono en cola ({chunk_count} fragmentos capturados).")
    except KeyboardInterrupt:
        print("\nPuente detenido por el usuario.")
        return 0
    except Exception as error:
        print(f"El puente se detuvo: {type(error).__name__}.", file=sys.stderr)
        return 1
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())


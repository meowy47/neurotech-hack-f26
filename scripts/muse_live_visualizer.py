#!/usr/bin/env python3
"""Serve a live LSL EEG monitor for a Muse or any LSL EEG producer.

The service discovers an EEG LSL stream, honours its reported sample rate, and
pushes Server-Sent Event frames at a configurable cadence (125 ms by default).
It deliberately reports live signal quality rather than issuing a creative or
clinical interpretation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from pylsl import StreamInlet, StreamInfo, resolve_byprop


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "visualizations" / "muse-live.html"
APP_WEB_DIR = ROOT / "eureka-demo" / "web"
BANDS_HZ = {"theta": (4.0, 8.0), "alpha": (8.0, 12.0), "beta": (13.0, 30.0)}
ANALYSIS_WINDOW_SECONDS = 2.0
ARTIFACT_WINDOW_SECONDS = 1.0
BUFFER_SECONDS = 8.0
BASELINE_SECONDS = 30.0
PEAK_TO_PEAK_LIMIT_UV = 150.0
DERIVATIVE_RMS_LIMIT_UV = 45.0
MUSE_EEG_CHANNEL_COUNT = 4


def _channel_labels(info: StreamInfo) -> list[str]:
    """Read LSL labels when present, with stable generic fallbacks otherwise."""
    labels: list[str] = []
    try:
        node = info.desc().child("channels").child("channel")
        while node.name() == "channel":
            labels.append(node.child_value("label") or f"Channel {len(labels) + 1}")
            node = node.next_sibling()
    except Exception:  # LSL metadata is optional and varies by producer.
        labels = []
    count = info.channel_count()
    return (labels + [f"Channel {index + 1}" for index in range(len(labels), count)])[:count]


def _bandpower(samples: np.ndarray, sample_rate_hz: float) -> dict[str, np.ndarray]:
    """Return simple windowed FFT band powers for every channel."""
    centered = samples - np.mean(samples, axis=0, keepdims=True)
    window = np.hanning(len(centered))[:, None]
    spectrum = np.abs(np.fft.rfft(centered * window, axis=0)) ** 2
    frequencies = np.fft.rfftfreq(len(centered), 1.0 / sample_rate_hz)
    powers: dict[str, np.ndarray] = {}
    for name, (low_hz, high_hz) in BANDS_HZ.items():
        mask = (frequencies >= low_hz) & (frequencies <= high_hz)
        powers[name] = np.mean(spectrum[mask], axis=0) if np.any(mask) else np.zeros(samples.shape[1])
    return powers


class LiveEEGProcessor:
    def __init__(self, info: StreamInfo) -> None:
        self.stream_name = info.name()
        self.sample_rate_hz = float(info.nominal_srate())
        if not math.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
            raise ValueError("The discovered EEG LSL stream does not report a usable nominal sample rate.")
        source_channels = _channel_labels(info)
        # Muse's fifth sample value is Right AUX, not a fifth EEG electrode.
        # If LSL labels are missing, preserve the standard first-four Muse EEG
        # ordering rather than accidentally analysing generic "Channel 5".
        aux_names = {"right aux", "right_aux", "aux", "auxiliary"}
        eeg_indexes = [
            index for index, channel in enumerate(source_channels) if channel.strip().lower() not in aux_names
        ][:MUSE_EEG_CHANNEL_COUNT]
        if len(eeg_indexes) < MUSE_EEG_CHANNEL_COUNT and len(source_channels) >= MUSE_EEG_CHANNEL_COUNT:
            eeg_indexes = list(range(MUSE_EEG_CHANNEL_COUNT))
        if not eeg_indexes:
            raise ValueError("The discovered LSL EEG stream has no usable EEG channels.")
        self.eeg_indexes = eeg_indexes
        self.channels = [source_channels[index] for index in self.eeg_indexes]
        normalized = [channel.strip().lower() for channel in self.channels]
        self.forehead_indexes = [
            normalized.index(name) if name in normalized else fallback
            for name, fallback in (("af7", min(1, len(self.channels) - 1)), ("af8", min(2, len(self.channels) - 1)))
        ]
        self.rows: deque[list[float]] = deque(maxlen=math.ceil(self.sample_rate_hz * BUFFER_SECONDS))
        self.timestamps: deque[float] = deque(maxlen=math.ceil(self.sample_rate_hz * BUFFER_SECONDS))
        self.started_at: float | None = None
        self.alpha_baseline: list[np.ndarray] = []

    def push(self, samples: list[list[float]], timestamps: list[float]) -> None:
        for sample, timestamp in zip(samples, timestamps, strict=True):
            row = [float(sample[index]) for index in self.eeg_indexes]
            if len(row) != len(self.channels) or not np.all(np.isfinite(row)):
                continue
            self.rows.append(row)
            self.timestamps.append(float(timestamp))
            if self.started_at is None:
                self.started_at = float(timestamp)

    def _display(self, data: np.ndarray) -> dict[str, Any]:
        """Make a small 1–30 Hz AF7/AF8 compatibility trace for the Eureka app."""
        length = min(len(data), math.ceil(self.sample_rate_hz * 4.0))
        recent = data[-length:, self.forehead_indexes]
        centered = recent - np.mean(recent, axis=0, keepdims=True)
        spectrum = np.fft.rfft(centered, axis=0)
        frequencies = np.fft.rfftfreq(len(centered), 1.0 / self.sample_rate_hz)
        spectrum[(frequencies < 1.0) | (frequencies > 30.0)] = 0
        filtered = np.fft.irfft(spectrum, n=len(centered), axis=0)
        decimation = max(1, round(self.sample_rate_hz / 64.0))
        return {
            "rate": round(self.sample_rate_hz / decimation, 3),
            "af7": np.round(filtered[::decimation, 0], 2).tolist(),
            "af8": np.round(filtered[::decimation, 1], 2).tolist(),
        }

    def frame(self) -> dict[str, Any]:
        elapsed = 0.0 if self.started_at is None or not self.timestamps else self.timestamps[-1] - self.started_at
        base = {
            "type": "eeg_frame",
            "stream_name": self.stream_name,
            "sample_rate_hz": round(self.sample_rate_hz, 3),
            "elapsed_seconds": round(max(elapsed, 0.0), 3),
            "channels": self.channels,
            "alpha_index": None,
            "clean_channels": [],
            "artifact": {"detected": False, "channels": [], "reasons": {}},
            "bandpower": {band: {channel: None for channel in self.channels} for band in BANDS_HZ},
            "ready": False,
        }
        analysis_samples = math.ceil(self.sample_rate_hz * ANALYSIS_WINDOW_SECONDS)
        artifact_samples = math.ceil(self.sample_rate_hz * ARTIFACT_WINDOW_SECONDS)
        if len(self.rows) < analysis_samples:
            base["buffered_seconds"] = round(len(self.rows) / self.sample_rate_hz, 3)
            return base

        data = np.asarray(self.rows, dtype=float)
        latest = data[-analysis_samples:]
        artifact_window = data[-artifact_samples:]
        peak_to_peak = np.ptp(artifact_window, axis=0)
        derivative_rms = np.sqrt(np.mean(np.diff(artifact_window, axis=0) ** 2, axis=0))
        clean_mask = (peak_to_peak < PEAK_TO_PEAK_LIMIT_UV) & (derivative_rms < DERIVATIVE_RMS_LIMIT_UV)
        powers = _bandpower(latest, self.sample_rate_hz)
        clean_channels = [channel for channel, clean in zip(self.channels, clean_mask, strict=True) if clean]
        artifact_channels = [channel for channel, clean in zip(self.channels, clean_mask, strict=True) if not clean]
        reasons = {
            channel: [
                *(["high_peak_to_peak"] if peak_to_peak[index] >= PEAK_TO_PEAK_LIMIT_UV else []),
                *(["rapid_change"] if derivative_rms[index] >= DERIVATIVE_RMS_LIMIT_UV else []),
            ]
            for index, channel in enumerate(self.channels)
            if not clean_mask[index]
        }
        if np.any(clean_mask) and elapsed <= BASELINE_SECONDS:
            self.alpha_baseline.append(powers["alpha"][clean_mask])
        baseline = np.concatenate(self.alpha_baseline) if self.alpha_baseline else np.array([])
        alpha_index = None
        if np.any(clean_mask) and len(baseline):
            alpha_index = 100.0 * float(np.median(powers["alpha"][clean_mask])) / float(np.median(baseline))

        base.update(
            {
                "ready": True,
                "alpha_index": round(alpha_index, 2) if alpha_index is not None else None,
                "clean_channels": clean_channels,
                "artifact": {"detected": bool(artifact_channels), "channels": artifact_channels, "reasons": reasons},
                "bandpower": {
                    band: {channel: round(float(value), 4) for channel, value in zip(self.channels, values, strict=True)}
                    for band, values in powers.items()
                },
                "display": self._display(data),
            }
        )
        return base


class LiveServer:
    def __init__(self, host: str, port: int, update_seconds: float) -> None:
        self.host = host
        self.port = port
        self.update_seconds = update_seconds
        self.processor: LiveEEGProcessor | None = None
        self.event_clients: set[asyncio.StreamWriter] = set()

    async def handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request.decode("latin-1").split()
            if len(parts) < 2 or parts[0] != "GET":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return
            path = parts[1].split("?", 1)[0]
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
            if path == "/events":
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n"
                )
                await writer.drain()
                self.event_clients.add(writer)
                while not reader.at_eof():
                    await reader.read(1024)
                return
            if path in ("/", "/muse-live.html"):
                body = HTML_PATH.read_bytes()
                header = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                writer.write(header + body)
            elif path in ("/app", "/app/", "/app/index.html", "/app/app.js", "/app/styles.css"):
                filename = "index.html" if path.rstrip("/") == "/app" else path.removeprefix("/app/")
                asset = APP_WEB_DIR / filename
                content_types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
                if not asset.is_file() or asset.parent != APP_WEB_DIR:
                    writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                else:
                    body = asset.read_bytes()
                    header = f"HTTP/1.1 200 OK\r\nContent-Type: {content_types[asset.suffix]}\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                    writer.write(header + body)
            elif path == "/health":
                body = json.dumps({"stream_connected": self.processor is not None}).encode()
                header = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                writer.write(header + body)
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        finally:
            self.event_clients.discard(writer)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def broadcast_frames(self) -> None:
        while True:
            frame = self.processor.frame() if self.processor else {"type": "status", "status": "looking_for_eeg_stream"}
            payload = f"data: {json.dumps(frame, separators=(',', ':'))}\n\n".encode()
            for writer in list(self.event_clients):
                try:
                    writer.write(payload)
                    await writer.drain()
                except (ConnectionError, asyncio.IncompleteReadError):
                    self.event_clients.discard(writer)
            await asyncio.sleep(self.update_seconds)

    async def read_lsl(self) -> None:
        print("Looking for an LSL stream with type=EEG…")
        loop = asyncio.get_running_loop()
        streams: list[StreamInfo] = []
        while not streams:
            streams = await loop.run_in_executor(None, lambda: resolve_byprop("type", "EEG", timeout=2.0))
        info = streams[0]
        self.processor = LiveEEGProcessor(info)
        inlet = StreamInlet(info, max_chunklen=max(1, round(self.processor.sample_rate_hz // 4)))
        print(
            f"Connected to '{self.processor.stream_name}' · {self.processor.sample_rate_hz:g} Hz · "
            f"{', '.join(self.processor.channels)}"
        )
        while True:
            samples, timestamps = inlet.pull_chunk(timeout=0.0, max_samples=max(1, round(self.processor.sample_rate_hz)))
            if samples:
                self.processor.push(samples, timestamps)
            await asyncio.sleep(0.01)

    async def run(self) -> None:
        server = await asyncio.start_server(self.handle_http, self.host, self.port)
        socket_address = (server.sockets or [])[0].getsockname()
        print(f"Muse live visualizer: http://{socket_address[0]}:{socket_address[1]}")
        async with server:
            await asyncio.gather(server.serve_forever(), self.read_lsl(), self.broadcast_frames())


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Eureka LSL EEG live visualizer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--update-ms", type=int, default=125, choices=range(125, 251), metavar="125-250")
    args = parser.parse_args()
    asyncio.run(LiveServer(args.host, args.port, args.update_ms / 1_000).run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

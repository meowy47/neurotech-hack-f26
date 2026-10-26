#!/usr/bin/env python3
"""Eureka EEG bridge.

Reads raw EEG from a Muse 2 (through Mind Monitor's OSC stream or a muselsl
LSL stream), computes relative band powers on the forehead sensors (AF7, AF8),
and broadcasts one JSON frame every 100 ms to any browser connected on a
WebSocket (default ws://localhost:8765).

Usage:
    python bridge.py --source osc   # Mind Monitor app streaming OSC to this computer
    python bridge.py --source lsl   # run `muselsl stream` in another terminal first
    python bridge.py --source sim   # synthetic EEG, to test without a headband
"""

import argparse
import asyncio
import json
import math
import random
import time
from collections import deque

import numpy as np
import websockets

FS = 256                       # Muse 2 EEG sampling rate, Hz
CHANNELS = ["TP9", "AF7", "AF8", "TP10"]
FOREHEAD = [1, 2]              # AF7, AF8: where the band powers are measured
BUFFER_S = 4                   # seconds of raw data kept
BAND_WINDOW_S = 2              # seconds of data per band-power estimate
FRAME_INTERVAL_S = 0.1         # how often a frame is sent
DISPLAY_DECIMATE = 4           # 256 Hz -> 64 Hz for the on-screen traces
BLINK_UV = 150.0               # peak-to-peak over the last second above this = artifact
MUSCLE_GAMMA = 0.35            # relative gamma above this = muscle artifact

BANDS = {
    "delta": (1, 4),
    "theta": (4, 8),
    "alpha": (8, 13),
    "upper_alpha": (10, 13),
    "beta": (13, 30),
    "gamma": (30, 44),
}
TOTAL = (1, 44)


class RawBuffer:
    """Keeps the last few seconds of 4-channel samples."""

    def __init__(self, seconds=BUFFER_S):
        self.rows = deque(maxlen=FS * seconds)
        self.last_sample_at = 0.0
        self.received = 0

    def push(self, values):
        vals = [float(v) for v in values[:4]]
        if len(vals) < 4 or not all(math.isfinite(v) for v in vals):
            return
        self.rows.append(vals)
        self.last_sample_at = time.time()
        self.received += 1

    def array(self):
        return np.asarray(self.rows, dtype=float)


def band_powers(x):
    """Relative band power for each band, averaged over the columns of x (samples x channels)."""
    x = x - x.mean(axis=0)
    win = np.hanning(len(x))[:, None]
    spec = np.abs(np.fft.rfft(x * win, axis=0)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1.0 / FS)

    def power(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return spec[mask].sum(axis=0)

    total = np.maximum(power(*TOTAL), 1e-12)
    return {name: float(np.mean(power(lo, hi) / total)) for name, (lo, hi) in BANDS.items()}


def display_traces(x):
    """1-30 Hz band-passed, decimated traces for drawing (samples x channels -> lists)."""
    x = x - x.mean(axis=0)
    spec = np.fft.rfft(x, axis=0)
    freqs = np.fft.rfftfreq(len(x), 1.0 / FS)
    spec[(freqs < 1) | (freqs > 30)] = 0
    filtered = np.fft.irfft(spec, n=len(x), axis=0)[::DISPLAY_DECIMATE]
    return [np.round(filtered[:, i], 1).tolist() for i in range(filtered.shape[1])]


def make_frame(buf, source):
    data = buf.array()
    age = time.time() - buf.last_sample_at if buf.last_sample_at else None
    frame = {"type": "frame", "t": time.time(), "source": source, "age": age, "ready": False}
    if len(data) < FS * BAND_WINDOW_S:
        frame["buffered_s"] = round(len(data) / FS, 2)
        return frame

    forehead = data[:, FOREHEAD]
    bands = band_powers(forehead[-FS * BAND_WINDOW_S:])
    last_second = forehead[-FS:]
    blink = float(np.ptp(last_second, axis=0).max())
    clean = blink < BLINK_UV and bands["gamma"] < MUSCLE_GAMMA
    af7, af8 = display_traces(forehead)

    frame.update({
        "ready": True,
        "bands": {k: round(v, 4) for k, v in bands.items()},
        "clean": bool(clean),
        "ptp_uv": round(blink, 1),
        "display": {"rate": FS // DISPLAY_DECIMATE, "af7": af7, "af8": af8},
    })
    return frame


# ---------- sources ----------

async def run_osc(buf, ip, port):
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import AsyncIOOSCUDPServer

    def on_eeg(_address, *args):
        buf.push(args)

    dispatcher = Dispatcher()
    dispatcher.map("/muse/eeg", on_eeg)
    server = AsyncIOOSCUDPServer((ip, port), dispatcher, asyncio.get_running_loop())
    transport, _ = await server.create_serve_endpoint()
    print(f"Listening for Mind Monitor OSC on udp://{ip}:{port} (path /muse/eeg)")
    try:
        await asyncio.Future()
    finally:
        transport.close()


async def run_lsl(buf):
    from pylsl import StreamInlet, resolve_byprop

    print("Looking for a Muse LSL stream (start it with `muselsl stream`)...")
    loop = asyncio.get_running_loop()
    streams = []
    while not streams:
        streams = await loop.run_in_executor(None, lambda: resolve_byprop("type", "EEG", timeout=5))
        if not streams:
            print("  no EEG stream yet, still looking...")
    inlet = StreamInlet(streams[0], max_chunklen=12)
    print(f"Connected to LSL stream '{streams[0].name()}'")
    while True:
        samples, _ = inlet.pull_chunk(timeout=0.0, max_samples=256)
        for s in samples:
            buf.push(s)
        await asyncio.sleep(0.02)


async def run_sim(buf):
    """Synthetic EEG: slow drift, theta, beta and noise, plus a 10.5 Hz rhythm that slowly waxes and wanes."""
    print("Simulating EEG at 256 Hz (no headband)")
    n = 0
    start = time.time()
    drift = [0.0] * 4
    while True:
        due = int((time.time() - start) * FS)
        while n < due:
            t = n / FS
            alpha_amp = 7 + 4 * math.sin(2 * math.pi * t / 30)
            row = []
            for ch in range(4):
                drift[ch] = 0.98 * drift[ch] + random.gauss(0, 4)   # low-frequency background
                v = (drift[ch]
                     + 14 * math.sin(2 * math.pi * 2.5 * t + ch)
                     + 9 * math.sin(2 * math.pi * 6 * t + 2 * ch)
                     + alpha_amp * math.sin(2 * math.pi * 10.5 * t + ch)
                     + 4 * math.sin(2 * math.pi * 20 * t + ch)
                     + random.gauss(0, 5))
                row.append(v)
            if random.random() < 0.0004:   # an occasional blink on the forehead sensors
                row[1] += 250
                row[2] += 250
            buf.push(row)
            n += 1
        await asyncio.sleep(0.01)


# ---------- WebSocket ----------

async def serve(buf, source, host, port):
    clients = set()

    async def handler(ws, *_):
        clients.add(ws)
        print(f"Browser connected ({len(clients)} open)")
        try:
            await ws.send(json.dumps({"type": "hello", "source": source, "channels": CHANNELS}))
            await ws.wait_closed()
        finally:
            clients.discard(ws)
            print(f"Browser disconnected ({len(clients)} open)")

    async with websockets.serve(handler, host, port):
        print(f"Serving frames on ws://{host}:{port}")
        while True:
            if clients:
                msg = json.dumps(make_frame(buf, source))
                for ws in list(clients):
                    try:
                        await ws.send(msg)
                    except websockets.ConnectionClosed:
                        clients.discard(ws)
            await asyncio.sleep(FRAME_INTERVAL_S)


async def main():
    p = argparse.ArgumentParser(description="Stream Muse 2 band powers to the Eureka web demo.")
    p.add_argument("--source", choices=["osc", "lsl", "sim"], default="osc")
    p.add_argument("--osc-ip", default="0.0.0.0", help="address to listen on for Mind Monitor")
    p.add_argument("--osc-port", type=int, default=5000)
    p.add_argument("--ws-host", default="localhost", help="use 0.0.0.0 to let a phone on the same Wi-Fi connect")
    p.add_argument("--ws-port", type=int, default=8765)
    args = p.parse_args()

    buf = RawBuffer()
    if args.source == "osc":
        reader = run_osc(buf, args.osc_ip, args.osc_port)
    elif args.source == "lsl":
        reader = run_lsl(buf)
    else:
        reader = run_sim(buf)
    await asyncio.gather(reader, serve(buf, args.source, args.ws_host, args.ws_port))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

# Eureka

A break coach for students that reads a Muse 2 EEG headband. While you work, it shows your live brain waves. When focus fades, it offers a creative break, ranking activities by how much they raised your upper alpha (10–13 Hz) in past breaks.

The connected version now runs from the repository root. `scripts/muse-live`
discovers the LSL EEG stream, hosts the app, and supplies live data through a
Server-Sent Event stream. The older `bridge/` WebSocket prototype is retained
as reference material, not the default integration.

- `web/`: the phone-sized Eureka app, served by `scripts/muse-live` at `/app/`.
- `bridge/`: the earlier WebSocket prototype.

```
Muse 2 ──Bluetooth──▶ muselsl ──LSL EEG──▶ scripts/muse-live ──SSE──▶ web app
```

## Quick start

```bash
# 1. Start a MuseLSL EEG stream from the repository root
./scripts/muse-stream --name Muse-XXXX

# 2. In another terminal, start the live service
./scripts/muse-live

# 3. Open the connected app
open http://127.0.0.1:8765/app/
```

The chip in the top-right corner shows where the data comes from:

| Chip | Meaning |
| --- | --- |
| Live · Muse 2 | Connected to the bridge and receiving data |
| Headband signal lost | Bridge connected, but no EEG for 2+ seconds |
| Simulated data | No bridge found; the page makes up data and retries every 3 seconds |

## Legacy bridge setup (not used by the connected app)

Pick one of the two routes below.

### Option A: muselsl (free, laptop Bluetooth)

```bash
pip install muselsl
muselsl stream                      # finds and streams the Muse 2; leave it running
python bridge/bridge.py --source lsl
```

On macOS, if `muselsl stream` can't find the headband, try `muselsl stream --backend bleak`.

### Option B: Mind Monitor app (phone)

1. In Mind Monitor, open Settings and set **OSC Stream Target IP** to your laptop's IP address and **OSC Stream Port** to `5000`.
2. Connect the headband in Mind Monitor and tap the streaming button.
3. Run `python bridge/bridge.py --source osc`.

Your phone and laptop must be on the same Wi-Fi network, and the laptop's firewall must allow UDP on port 5000.

## Demo options

URL parameters for the web app:

- `?start=2832` starts the work stopwatch at 47:12 (in seconds), for a mid-session demo.
- `?ws=ws://192.168.1.20:8765` connects to a bridge on another computer.

To show the app on a phone: run the bridge with `--ws-host 0.0.0.0`, serve the web folder, then open `http://<laptop-ip>:8000/?ws=ws://<laptop-ip>:8765` on the phone. GitHub Pages serves over HTTPS, and browsers block an HTTPS page from opening a plain `ws://` connection to another machine. Serve the page locally over HTTP when you use live data.

## What the bridge computes

Every 100 ms the bridge sends one frame:

```json
{
  "type": "frame",
  "source": "lsl",
  "age": 0.004,
  "ready": true,
  "bands": { "delta": 0.41, "theta": 0.19, "alpha": 0.17, "upper_alpha": 0.11, "beta": 0.18, "gamma": 0.05 },
  "clean": true,
  "ptp_uv": 62.3,
  "display": { "rate": 64, "af7": [...], "af8": [...] }
}
```

- **bands:** relative power (share of 1–44 Hz power) over the last 2 seconds on the forehead sensors AF7 and AF8, averaged. `upper_alpha` (10–13 Hz) sits inside `alpha` (8–13 Hz), so the bands don't sum to 1.
- **clean:** false when the last second shows a blink or movement (peak-to-peak above 150 µV) or muscle noise (gamma above 35%). The app ignores frames that aren't clean.
- **display:** the last 4 seconds of AF7 and AF8, filtered to 1–30 Hz and downsampled to 64 Hz, for drawing.
- **age:** seconds since the last raw sample arrived.

The tuning constants are at the top of `bridge/bridge.py` and in `CONFIG` at the top of `web/app.js`.

## How the break reading works

1. While you're on the work screen, the app keeps the upper-alpha value of every clean frame.
2. When you tap **Take a creative break**, it saves the average of the last 60 seconds as your baseline.
3. During an activity, it compares the average of the last 10 seconds to that baseline. At +15% or more it shows "You're in" and how long you've held it.

## Limitations

- **Scripted parts:** the sentence on the work screen ("Your brain waves have drifted…") is fixed text, and the activity rankings and their stats are sample data. The waves, band powers, baseline and break reading are live.
- **Placeholder thresholds:** the +15% target and the artifact cutoffs are starting values. Calibrate them with the data-collection plan.
- **Forehead sensors only:** AF7 and AF8 pick up blinks and eye movements, which show up mostly in delta and theta. The artifact check drops the worst windows but not all of them.
- **Alpha isn't creativity:** upper alpha going up is linked to divergent thinking in research, but it also rises when you relax or close your eyes. Keep activities eyes-open and present the reading as a brain-state marker, not a creativity score.

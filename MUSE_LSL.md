# MuseLSL setup and first stream

MuseLSL is installed in this repository's `.venv` from the upstream
[`alexandrebarachant/muse-lsl`](https://github.com/alexandrebarachant/muse-lsl)
repository. It streams Muse 2 sensor data to Lab Streaming Layer (LSL).

The environment pins `bitstring<5` in
`requirements-muse-lsl.txt`. MuseLSL 2.5.3 uses a Bitstring API that was
removed in Bitstring 5; do not upgrade that package without first testing a
newer MuseLSL release.

## Before starting

1. Charge and wear the Muse 2; make sure its sensors have stable skin contact.
2. Use the Muse app only for fit/contact checks, then close it completely. The
   headband can normally connect to only one Bluetooth client at a time.
3. Turn on Bluetooth. macOS may ask for Bluetooth permission the first time
   MuseLSL runs; allow it.

## Run a live stream

From the repository root, find the headset:

```bash
./scripts/muse-list
```

Start the stream. Replace the name with the discovered Muse name:

```bash
./scripts/muse-stream --name Muse-XXXX
```

This terminal must remain open. It publishes `EEG`, `PPG`, `ACC`, and `GYRO`
LSL streams.

In a second terminal, open the viewer:

```bash
./scripts/muse-view
```

Or launch Eureka's live monitor, which discovers the LSL stream by its `EEG`
type and serves a browser dashboard:

```bash
./scripts/muse-live
```

Open `http://127.0.0.1:8765`. It reads chunks continuously at the stream's
reported sample rate and sends browser updates every 125 ms with elapsed time,
alpha index, clean channels, artifact state, and alpha/theta/beta bandpower.
Pass `--update-ms 125` through `250` to adjust the update interval.
It always analyzes only the first four Muse EEG electrodes; a fifth Muse value
is treated as `Right AUX` and excluded even when the LSL stream omits labels.
The same service hosts the connected phone-sized Eureka app at
`http://127.0.0.1:8765/app/`.

Moving EEG traces confirm that data is arriving. Blink once or gently clench
your jaw to confirm the display is live; do not use those noisy periods for
Eureka scoring.

In a third terminal, save a short EEG check recording:

```bash
./scripts/muse-record-test
```

It records 20 seconds by default in `recordings/` (ignored by Git). Pass a
duration in seconds to change it, for example `./scripts/muse-record-test 60`.

## Expected sequence

```text
Muse 2 → muse-stream → LSL EEG / ACC / GYRO / PPG streams
                            ├─ muse-view: development visualization
                            ├─ muse-record-test: quick CSV verification
                            └─ Eureka signal service: production consumer
```

For Eureka, use the `EEG` and `ACC` streams first. Keep a separate event/marker
stream for prompt onset, cue onset, idea tap, speech start/end, and trial end.
Do not treat Muse's consumer-app Calm score as an Eureka feature.

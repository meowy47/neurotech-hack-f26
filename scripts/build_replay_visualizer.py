#!/usr/bin/env python3
"""Build compact replay data for the standalone Eureka visualizer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from eeg_scoring import BAND_RANGES_HZ, CHANNELS, SAMPLE_RATE_HZ, load_filtered_bands


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "simulated"
REAL_INPUT_DIR = ROOT / "data" / "real"
OUTPUT_PATH = ROOT / "visualizations" / "eureka-replay-data.js"
# Beta extends through 30 Hz, so this display stream must remain above 60 Hz.
# 125 Hz also divides the 250 Hz Muse source rate exactly.
WAVEFORM_SAMPLE_RATE_HZ = 125


def pack_session(csv_path: Path, metadata_path: Path | dict) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if isinstance(metadata_path, Path) else metadata_path
    filtered_bands = {
        band: values[:: SAMPLE_RATE_HZ // WAVEFORM_SAMPLE_RATE_HZ]
        for band, values in load_filtered_bands(csv_path).items()
    }
    waveforms_by_band = {band: np.round(values.T, 3).tolist() for band, values in filtered_bands.items()}
    # One robust limit is shared by all channels and three bands in this session.
    # A percentile avoids a rare filtered artifact flattening every clean trace.
    all_filtered_values = np.concatenate([values.ravel() for values in filtered_bands.values()])
    return {
        "scenario": metadata.get("scenario", csv_path.stem),
        "display_name": metadata.get("display_name", csv_path.stem.replace("_", " ").replace("-", " ").title()),
        "source_type": metadata.get("source_type", "simulation"),
        "duration_seconds": round(len(next(iter(filtered_bands.values()))) / SAMPLE_RATE_HZ, 3),
        "waveforms_by_band": waveforms_by_band,
        "waveform_y_limit_uv": float(np.ceil(np.percentile(np.abs(all_filtered_values), 99.5) / 5.0) * 5.0),
    }


def main() -> None:
    metadata_paths = [*sorted(INPUT_DIR.glob("*.json")), *sorted(REAL_INPUT_DIR.glob("*.json"))]
    sessions = [pack_session(path.with_suffix(".csv"), path) for path in metadata_paths]
    training_csv = next(
        (
            path
            for path in (REAL_INPUT_DIR / "trial-for-training.csv", REAL_INPUT_DIR / "trial_for_training.csv")
            if path.exists()
        ),
        None,
    )
    known_csv_paths = {path.with_suffix(".csv") for path in metadata_paths}
    if training_csv is not None and training_csv not in known_csv_paths:
        training_metadata = {
            "scenario": "real_trial_for_training",
            "display_name": "Real trial for training",
            "source_type": "real",
        }
        sessions.append(pack_session(training_csv, training_metadata))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_sample_rate_hz": SAMPLE_RATE_HZ,
        "waveform_sample_rate_hz": WAVEFORM_SAMPLE_RATE_HZ,
        "channels": list(CHANNELS),
        "inspection_bands_hz": {band: list(bounds) for band, bounds in BAND_RANGES_HZ.items()},
        "sessions": sessions,
    }
    OUTPUT_PATH.write_text(
        "window.EUREKA_REPLAY_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

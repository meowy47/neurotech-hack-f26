#!/usr/bin/env python3
"""Build compact replay data for the standalone Eureka visualizer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from eeg_scoring import CHANNELS, SAMPLE_RATE_HZ, analyze_session, load_filtered_alpha


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "simulated"
REAL_INPUT_DIR = ROOT / "data" / "real"
OUTPUT_PATH = ROOT / "visualizations" / "eureka-replay-data.js"
WINDOW_HOP_SECONDS = 0.125  # Eight UI updates per second; source CSV remains 250 Hz.
WAVEFORM_SAMPLE_RATE_HZ = 50


def pack_session(metadata_path: Path) -> dict:
    csv_path = metadata_path.with_suffix(".csv")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    result = analyze_session(csv_path, metadata_path, hop_seconds=WINDOW_HOP_SECONDS)
    filtered = load_filtered_alpha(csv_path)[:: SAMPLE_RATE_HZ // WAVEFORM_SAMPLE_RATE_HZ]
    segment_ids = {"baseline": 0, "imagery": 1, "drawing": 2, "post_drawing_still": 3}
    channel_masks = {
        "TP9": 1,
        "AF7": 2,
        "AF8": 4,
        "TP10": 8,
    }
    windows = [
        [
            record["time_s"],
            segment_ids[record["segment"]],
            record["alpha_index"],
            int(record["clean"]),
            record["clean_channels"],
            sum(channel_masks[channel] for channel in record["clean_channel_names"]),
        ]
        for record in result.pop("windows")
    ]
    result["windows"] = windows
    result["waveforms"] = np.round(filtered.T, 3).tolist()
    # One robust limit is shared by all channel inspections in this session.
    # A percentile avoids a rare filtered artifact flattening every clean trace.
    result["waveform_y_limit_uv"] = float(np.ceil(np.percentile(np.abs(filtered), 99.5) / 5.0) * 5.0)
    result["segment_bounds"] = metadata["segments_s"]
    return result


def main() -> None:
    session_paths = [*sorted(INPUT_DIR.glob("*.json")), *sorted(REAL_INPUT_DIR.glob("*.json"))]
    sessions = [pack_session(path) for path in session_paths]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_sample_rate_hz": SAMPLE_RATE_HZ,
        "stream_chunk_seconds": 1,
        "ui_refresh_hz": 8,
        "waveform_sample_rate_hz": WAVEFORM_SAMPLE_RATE_HZ,
        "channels": list(CHANNELS),
        "segment_names": ["baseline", "imagery", "drawing", "post_drawing_still"],
        "sessions": sessions,
        # These are intentionally inactive until tomorrow's recordings and their
        # sidecar metadata files land in data/real/. The builder then discovers
        # those sessions automatically instead of needing another UI edit.
        "planned_real_sessions": [
            {"id": f"tomorrow-validation-{number}", "display_name": f"Tomorrow · validation trial {number}", "disabled": True}
            for number in range(1, 5)
        ],
    }
    OUTPUT_PATH.write_text(
        "window.EUREKA_REPLAY_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

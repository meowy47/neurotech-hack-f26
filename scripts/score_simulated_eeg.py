#!/usr/bin/env python3
"""Score generated fixtures from raw CSV values and verify their expected labels.

The gate uses only raw signal features and baseline-derived thresholds. It does
not read the fixture's artifact annotations or expected result when deciding
which windows to reject.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import signal


SAMPLE_RATE_HZ = 250
WINDOW_SECONDS = 2
HOP_SECONDS = 1
CHANNEL_INDEX = {"TP9": 1, "AF7": 2, "AF8": 3, "TP10": 4}


def robust_sigma(values: np.ndarray) -> float:
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def window_features(window: np.ndarray) -> tuple[float, float]:
    frontal = window[:, [CHANNEL_INDEX["AF7"], CHANNEL_INDEX["AF8"]]]
    all_eeg = window[:, list(CHANNEL_INDEX.values())]
    frontal_peak_to_peak = float(np.max(np.ptp(frontal, axis=0)))
    derivative_rms = float(np.median(np.sqrt(np.mean(np.diff(all_eeg, axis=0) ** 2, axis=0))))
    return frontal_peak_to_peak, derivative_rms


def alpha_band_power(window: np.ndarray) -> float:
    frontal_average = np.mean(window[:, [CHANNEL_INDEX["AF7"], CHANNEL_INDEX["AF8"]]], axis=1)
    frequencies, power = signal.welch(frontal_average, fs=SAMPLE_RATE_HZ, nperseg=len(frontal_average))
    alpha = np.trapezoid(power[(frequencies >= 8.0) & (frequencies <= 12.0)], frequencies[(frequencies >= 8.0) & (frequencies <= 12.0)])
    return float(alpha)


def windows_for_segment(samples: np.ndarray, start_s: float, end_s: float):
    length = WINDOW_SECONDS * SAMPLE_RATE_HZ
    hop = HOP_SECONDS * SAMPLE_RATE_HZ
    for start in range(int(start_s * SAMPLE_RATE_HZ), int(end_s * SAMPLE_RATE_HZ) - length + 1, hop):
        yield samples[start : start + length]


def analyze(csv_path: Path, metadata_path: Path) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    samples = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    segments = metadata["segments_s"]
    baseline_windows = list(windows_for_segment(samples, *segments["baseline"]))
    baseline_features = np.array([window_features(window) for window in baseline_windows])
    p2p_threshold = float(np.median(baseline_features[:, 0]) + 6.0 * robust_sigma(baseline_features[:, 0]))
    derivative_threshold = float(np.median(baseline_features[:, 1]) + 6.0 * robust_sigma(baseline_features[:, 1]))

    def score_segment(name: str) -> dict:
        segment_windows = list(windows_for_segment(samples, *segments[name]))
        clean_power = []
        rejected = 0
        for window in segment_windows:
            p2p, derivative = window_features(window)
            if p2p > p2p_threshold or derivative > derivative_threshold:
                rejected += 1
            else:
                clean_power.append(alpha_band_power(window))
        return {
            "window_count": len(segment_windows),
            "clean_window_count": len(clean_power),
            "clean_fraction": len(clean_power) / len(segment_windows),
            "alpha_power": float(np.median(clean_power)) if clean_power else None,
            "rejected_window_count": rejected,
        }

    baseline = score_segment("baseline")
    imagery = score_segment("imagery")
    drawing = score_segment("drawing")
    post_drawing = score_segment("post_drawing_still")
    baseline_alpha = baseline["alpha_power"]
    if baseline_alpha is None or imagery["alpha_power"] is None or post_drawing["alpha_power"] is None:
        result, confidence = "inconclusive", "low"
    else:
        imagery_change = imagery["alpha_power"] / baseline_alpha - 1.0
        drawing_change = post_drawing["alpha_power"] / baseline_alpha - 1.0
        difference = drawing_change - imagery_change
        enough_clean_data = imagery["clean_fraction"] >= 0.6 and post_drawing["clean_fraction"] >= 0.6
        if not enough_clean_data or abs(difference) < 0.08:
            result, confidence = "inconclusive", "low"
        elif difference > 0:
            result, confidence = "drawing", "high"
        else:
            result, confidence = "imagery", "high"

    return {
        "scenario": metadata["scenario"],
        "expected_result": metadata["expected_result"],
        "expected_confidence": metadata["expected_confidence"],
        "result": result,
        "confidence": confidence,
        "matches_expected": result == metadata["expected_result"] and confidence == metadata["expected_confidence"],
        "artifact_gate_thresholds": {"frontal_peak_to_peak": p2p_threshold, "derivative_rms": derivative_threshold},
        "segments": {"baseline": baseline, "imagery": imagery, "drawing": drawing, "post_drawing_still": post_drawing},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/simulated"))
    parser.add_argument("--verify", action="store_true", help="Exit nonzero if a fixture does not meet its expected label.")
    arguments = parser.parse_args()
    all_match = True
    for metadata_path in sorted(arguments.data_dir.glob("*.json")):
        csv_path = metadata_path.with_suffix(".csv")
        result = analyze(csv_path, metadata_path)
        all_match &= result["matches_expected"]
        print(json.dumps(result, indent=2))
    if arguments.verify and not all_match:
        raise SystemExit("One or more fixture labels did not match raw-signal scoring.")


if __name__ == "__main__":
    main()

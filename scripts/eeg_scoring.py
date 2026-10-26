"""Shared EEG processing for Eureka replay, charts, and alpha-based decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal


SAMPLE_RATE_HZ = 250
ALPHA_RANGE_HZ = (8.0, 12.0)
BAND_RANGES_HZ = {
    "theta": (4.0, 8.0),
    "alpha": ALPHA_RANGE_HZ,
    "beta": (13.0, 30.0),
}
WINDOW_SECONDS = 2.0
DEFAULT_HOP_SECONDS = 1.0
MIN_CLEAN_CHANNELS = 3
ABSOLUTE_CLIP_UV = 1_000.0
DEMO_MARGIN_INDEX = 8.0
CHANNELS = ("TP9", "AF7", "AF8", "TP10")
CSV_CHANNEL_INDEXES = (1, 2, 3, 4)


def _robust_sigma_by_channel(values: np.ndarray) -> np.ndarray:
    median = np.median(values, axis=0)
    return 1.4826 * np.median(np.abs(values - median), axis=0)


def load_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_raw_eeg(csv_path: Path) -> np.ndarray:
    samples = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    if samples.ndim != 2 or samples.shape[1] < 5:
        raise ValueError(f"Expected Muse CSV columns in {csv_path}")
    return samples[:, CSV_CHANNEL_INDEXES]


def filter_band(raw_eeg: np.ndarray, band: str) -> np.ndarray:
    """Band-pass every EEG channel in one of the replay inspection bands."""
    try:
        low_hz, high_hz = BAND_RANGES_HZ[band]
    except KeyError as error:
        raise ValueError(f"Unknown EEG band: {band}") from error
    band_filter = signal.butter(4, (low_hz, high_hz), btype="bandpass", fs=SAMPLE_RATE_HZ, output="sos")
    return signal.sosfiltfilt(band_filter, raw_eeg, axis=0)


def filter_alpha(raw_eeg: np.ndarray) -> np.ndarray:
    """Preserve the single shared 8–12 Hz filter used for all scoring decisions."""
    return filter_band(raw_eeg, "alpha")


def load_filtered_alpha(csv_path: Path) -> np.ndarray:
    return filter_alpha(load_raw_eeg(csv_path))


def load_filtered_bands(csv_path: Path) -> dict[str, np.ndarray]:
    """Load theta, alpha, and beta inspection traces from the exact same raw CSV."""
    raw_eeg = load_raw_eeg(csv_path)
    return {band: filter_band(raw_eeg, band) for band in BAND_RANGES_HZ}


def _window_starts(start_s: float, end_s: float, hop_seconds: float) -> list[int]:
    length = int(WINDOW_SECONDS * SAMPLE_RATE_HZ)
    hop = int(hop_seconds * SAMPLE_RATE_HZ)
    if hop < 1:
        raise ValueError("Window hop must be at least one sample.")
    return list(range(int(start_s * SAMPLE_RATE_HZ), int(end_s * SAMPLE_RATE_HZ) - length + 1, hop))


def _channel_features(raw_window: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    peak_to_peak = np.ptp(raw_window, axis=0)
    derivative_rms = np.sqrt(np.mean(np.diff(raw_window, axis=0) ** 2, axis=0))
    clipped = np.max(np.abs(raw_window), axis=0) >= ABSOLUTE_CLIP_UV
    return peak_to_peak, derivative_rms, clipped


def _channel_alpha_power(filtered_window: np.ndarray) -> np.ndarray:
    return np.mean(filtered_window**2, axis=0)


def _segment_windows(segments: dict[str, list[float]], hop_seconds: float) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for segment in ("baseline", "imagery", "drawing", "post_drawing_still"):
        if segment in segments:
            rows.extend((segment, start) for start in _window_starts(*segments[segment], hop_seconds))
    return sorted(rows, key=lambda row: row[1])


def analyze_session(
    csv_path: Path, metadata_path: Path | dict[str, Any], hop_seconds: float = DEFAULT_HOP_SECONDS
) -> dict[str, Any]:
    """Return shared per-window records plus the only allowed session decision."""
    metadata = load_metadata(metadata_path) if isinstance(metadata_path, Path) else metadata_path
    segments = metadata["segments_s"]
    raw_eeg = load_raw_eeg(csv_path)
    filtered_alpha = filter_alpha(raw_eeg)
    window_length = int(WINDOW_SECONDS * SAMPLE_RATE_HZ)

    baseline_starts = _window_starts(*segments["baseline"], hop_seconds)
    baseline_features = [_channel_features(raw_eeg[start : start + window_length]) for start in baseline_starts]
    baseline_p2p = np.array([features[0] for features in baseline_features])
    baseline_derivative = np.array([features[1] for features in baseline_features])
    p2p_threshold = np.median(baseline_p2p, axis=0) + 6.0 * _robust_sigma_by_channel(baseline_p2p)
    derivative_threshold = np.median(baseline_derivative, axis=0) + 6.0 * _robust_sigma_by_channel(baseline_derivative)

    pending_records: list[dict[str, Any]] = []
    for segment, start in _segment_windows(segments, hop_seconds):
        raw_window = raw_eeg[start : start + window_length]
        filtered_window = filtered_alpha[start : start + window_length]
        p2p, derivative, clipped = _channel_features(raw_window)
        clean_mask = ~((p2p > p2p_threshold) | (derivative > derivative_threshold) | clipped)
        clean_channel_names = [channel for channel, is_clean in zip(CHANNELS, clean_mask, strict=True) if is_clean]
        clean = len(clean_channel_names) >= MIN_CLEAN_CHANNELS
        alpha_power = float(np.median(_channel_alpha_power(filtered_window)[clean_mask])) if clean else None
        pending_records.append(
            {
                "time_s": round(start / SAMPLE_RATE_HZ + WINDOW_SECONDS / 2.0, 3),
                "segment": segment,
                "alpha_power": alpha_power,
                "clean": clean,
                "clean_channels": len(clean_channel_names),
                "clean_channel_names": clean_channel_names,
            }
        )

    baseline_power = float(np.median([record["alpha_power"] for record in pending_records if record["segment"] == "baseline" and record["clean"]]))
    for record in pending_records:
        record["alpha_index"] = round(100.0 * record["alpha_power"] / baseline_power, 3) if record["clean"] else None

    summaries = {segment: _summarize_segment(pending_records, segment) for segment in segments}
    result, confidence = _decide(summaries)
    return {
        "scenario": metadata.get("scenario", csv_path.stem),
        "display_name": metadata.get("display_name", metadata.get("scenario", csv_path.stem).replace("_", " ").title()),
        "source_type": metadata.get("source_type", "simulation"),
        "participant": metadata.get("participant"),
        "baseline_group": metadata.get("baseline_group"),
        "expected_result": metadata.get("expected_result"),
        "expected_confidence": metadata.get("expected_confidence"),
        "baseline_alpha_power": baseline_power,
        "duration_seconds": round(len(raw_eeg) / SAMPLE_RATE_HZ, 3),
        "alpha_range_hz": list(ALPHA_RANGE_HZ),
        "window_seconds": WINDOW_SECONDS,
        "hop_seconds": hop_seconds,
        "demo_margin_index": DEMO_MARGIN_INDEX,
        "result": result,
        "confidence": confidence,
        "matches_expected": _matches_expected(metadata, result, confidence),
        "artifact_gate_thresholds": {
            "peak_to_peak_by_channel": dict(zip(CHANNELS, p2p_threshold.tolist(), strict=True)),
            "derivative_rms_by_channel": dict(zip(CHANNELS, derivative_threshold.tolist(), strict=True)),
            "absolute_clip_uv": ABSOLUTE_CLIP_UV,
            "minimum_clean_channels": MIN_CLEAN_CHANNELS,
        },
        "segments": summaries,
        "windows": pending_records,
    }


def _summarize_segment(records: list[dict[str, Any]], segment: str) -> dict[str, Any]:
    rows = [record for record in records if record["segment"] == segment]
    clean_rows = [record for record in rows if record["clean"]]
    return {
        "window_count": len(rows),
        "clean_window_count": len(clean_rows),
        "clean_fraction": len(clean_rows) / len(rows) if rows else 0.0,
        "median_clean_channel_count": float(np.median([record["clean_channels"] for record in clean_rows])) if clean_rows else 0.0,
        "alpha_power": float(np.median([record["alpha_power"] for record in clean_rows])) if clean_rows else None,
        "alpha_index": float(np.median([record["alpha_index"] for record in clean_rows])) if clean_rows else None,
        "rejected_window_count": len(rows) - len(clean_rows),
    }


def _decide(summaries: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if "imagery" not in summaries or "post_drawing_still" not in summaries:
        return "reference_only", "not_applicable"
    imagery = summaries["imagery"]
    post_drawing = summaries["post_drawing_still"]
    enough_clean_data = imagery["clean_fraction"] >= 0.6 and post_drawing["clean_fraction"] >= 0.6
    if not enough_clean_data or imagery["alpha_index"] is None or post_drawing["alpha_index"] is None:
        return "inconclusive", "low"
    difference = post_drawing["alpha_index"] - imagery["alpha_index"]
    if abs(difference) < DEMO_MARGIN_INDEX:
        return "inconclusive", "low"
    return ("drawing", "high") if difference > 0 else ("imagery", "high")


def _matches_expected(metadata: dict[str, Any], result: str, confidence: str) -> bool | None:
    if "expected_result" not in metadata or "expected_confidence" not in metadata:
        return None
    return result == metadata["expected_result"] and confidence == metadata["expected_confidence"]

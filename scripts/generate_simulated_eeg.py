#!/usr/bin/env python3
"""Generate deterministic Muse-shaped EEG fixtures for Eureka's MVP flow.

The generator derives its ordinary noise scale from the quieter AF7 and TP10
channels in ``data/real``. It does not copy real waveforms or use the
eyes-closed recording as an ideation template.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal


SAMPLE_RATE_HZ = 250
ALPHA_RANGE_HZ = (8.0, 12.0)
CHANNELS = ("TP9", "AF7", "AF8", "TP10")
CSV_COLUMNS = ("timestamps", *CHANNELS, "Right AUX")
TOTAL_SECONDS = 240


@dataclass(frozen=True)
class Scenario:
    seed: int
    imagery_power: float
    drawing_power: float
    post_drawing_power: float
    expected_result: str
    expected_confidence: str
    contaminated_drawing: bool = False


SCENARIOS: dict[str, Scenario] = {
    "imagery_stronger": Scenario(1729, 1.32, 1.08, 1.08, "imagery", "high"),
    "drawing_stronger": Scenario(2718, 1.08, 1.32, 1.32, "drawing", "high"),
    "inconclusive": Scenario(3141, 1.14, 1.16, 1.16, "inconclusive", "low"),
    "contaminated_drawing": Scenario(
        5772, 1.14, 1.32, 1.15, "inconclusive", "low", contaminated_drawing=True
    ),
}


def robust_sigma(values: np.ndarray) -> float:
    """MAD-based scale that is not dominated by a few large real-data artifacts."""
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def estimate_quiet_noise(real_data_dir: Path) -> tuple[float, list[str]]:
    """Estimate sample-to-sample noise from AF7/TP10, excluding eyes-closed data."""
    estimates: list[float] = []
    sources: list[str] = []
    for path in sorted(real_data_dir.glob("*.csv")):
        if "eyes-closed" in path.name:
            continue
        samples = np.loadtxt(path, delimiter=",", skiprows=1)
        if samples.ndim != 2 or samples.shape[1] != len(CSV_COLUMNS):
            continue
        for column_index in (2, 4):  # AF7 and TP10 in the established CSV layout.
            channel = samples[:, column_index]
            step_sigma = robust_sigma(np.diff(channel)) / np.sqrt(2.0)
            if np.isfinite(step_sigma) and step_sigma > 0:
                estimates.append(float(step_sigma))
                sources.append(path.name)
    if not estimates:
        raise RuntimeError(f"No usable AF7/TP10 data found in {real_data_dir}")
    # Keep rare bad-contact recordings from setting an unrealistically noisy fixture.
    return float(np.clip(np.median(estimates), 3.0, 15.0)), sorted(set(sources))


def colored_noise(rng: np.random.Generator, sample_count: int) -> np.ndarray:
    """Return zero-mean, unit-SD noise with approximately 1/f power."""
    frequencies = np.fft.rfftfreq(sample_count, d=1.0 / SAMPLE_RATE_HZ)
    # PSD proportional to 1/f means Fourier amplitude proportional to 1/sqrt(f).
    amplitude = 1.0 / np.sqrt(np.maximum(frequencies, 0.1))
    coefficients = rng.normal(size=frequencies.size) + 1j * rng.normal(size=frequencies.size)
    coefficients[0] = 0.0
    noise = np.fft.irfft(coefficients * amplitude, n=sample_count)
    return (noise - np.mean(noise)) / np.std(noise)


def slow_drift(rng: np.random.Generator, sample_count: int) -> np.ndarray:
    """Create a smooth channel baseline drift well below the alpha band."""
    white = rng.normal(size=sample_count)
    sos = signal.butter(2, 0.12, btype="lowpass", fs=SAMPLE_RATE_HZ, output="sos")
    drift = signal.sosfiltfilt(sos, white)
    return (drift - np.mean(drift)) / np.std(drift)


def smoothstep(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def alpha_power_envelope(times: np.ndarray, scenario: Scenario, rng: np.random.Generator) -> np.ndarray:
    """Build a continuous alpha-power envelope with 8-second activity transitions."""
    power = np.ones_like(times)
    # Transitions begin at an activity boundary and settle over eight seconds;
    # alpha amplitude is sqrt(power), so none of these changes are instantaneous.
    changes = ((30.0, scenario.imagery_power), (120.0, scenario.drawing_power), (210.0, scenario.post_drawing_power))
    current = 1.0
    for boundary, target in changes:
        after_boundary = times >= boundary
        fraction = smoothstep((times[after_boundary] - boundary) / 8.0)
        power[after_boundary] = current + (target - current) * fraction
        current = target

    # Small, gradual natural variation: knots are 7.5 seconds apart and linearly blended.
    knots = np.arange(0.0, times[-1] + 7.5, 7.5)
    variation = np.interp(times, knots, rng.normal(loc=1.0, scale=0.035, size=knots.size))
    return np.clip(power * variation, 0.65, None)


def add_drawing_artifacts(
    eeg: np.ndarray, times: np.ndarray, rng: np.random.Generator, noise_scale: float
) -> list[dict[str, float | str]]:
    """Inject actual raw-signal artifacts; scoring must detect them from the CSV."""
    events: list[dict[str, float | str]] = []
    channel_burst_gain = np.array([0.75, 1.10, 1.00, 0.68])

    for start in (133.0, 151.5, 177.0, 199.0):
        duration = float(rng.uniform(0.45, 0.95))
        selection = (times >= start) & (times < start + duration)
        count = int(selection.sum())
        envelope = signal.windows.tukey(count, alpha=0.45)
        broadband = rng.normal(size=count) * envelope * noise_scale * 13.0
        eeg[selection, :] += broadband[:, None] * channel_burst_gain[None, :]
        events.append({"type": "broadband_movement", "start_s": start, "duration_s": duration})

    for start in (141.0, 164.0, 190.0):
        duration = float(rng.uniform(0.65, 1.10))
        selection = (times >= start) & (times < start + duration)
        count = int(selection.sum())
        phase = np.linspace(0.0, np.pi, count, endpoint=False)
        # A slow frontal pulse is intentionally unlike the short broadband bursts.
        blink = np.sin(phase) ** 1.7 * noise_scale * 17.0
        eeg[selection, 1] += blink * 1.08  # AF7
        eeg[selection, 2] += blink * 0.94  # AF8
        eeg[selection, 0] += blink * 0.22  # TP9, weaker spillover
        eeg[selection, 3] += blink * 0.17  # TP10, weaker spillover
        events.append({"type": "frontal_blink", "start_s": start, "duration_s": duration})
    return events


def generate_session(scenario_name: str, scenario: Scenario, noise_scale: float) -> tuple[np.ndarray, dict]:
    rng = np.random.default_rng(scenario.seed)
    sample_count = SAMPLE_RATE_HZ * TOTAL_SECONDS
    times = np.arange(sample_count, dtype=float) / SAMPLE_RATE_HZ
    power_envelope = alpha_power_envelope(times, scenario, rng)
    alpha_amplitude = np.sqrt(power_envelope)

    channel_gain = np.array([0.88, 1.04, 0.96, 0.82])
    phase_offset = rng.uniform(-0.75, 0.75, size=len(CHANNELS))
    dc_offset = rng.normal(loc=-18.0, scale=8.0, size=len(CHANNELS))
    base_alpha_amplitude = noise_scale * 2.0
    instantaneous_frequency = 10.0 + 0.18 * np.sin(2.0 * np.pi * times / 53.0)
    phase = 2.0 * np.pi * np.cumsum(instantaneous_frequency) / SAMPLE_RATE_HZ

    eeg = np.empty((sample_count, len(CHANNELS)), dtype=float)
    for index in range(len(CHANNELS)):
        background = colored_noise(rng, sample_count) * noise_scale * (0.76 + 0.08 * index)
        sensor_noise = rng.normal(scale=noise_scale * 0.18, size=sample_count)
        drift = slow_drift(rng, sample_count) * noise_scale * (0.25 + 0.03 * index)
        alpha = (
            base_alpha_amplitude
            * channel_gain[index]
            * alpha_amplitude
            * np.sin(phase + phase_offset[index])
        )
        eeg[:, index] = dc_offset[index] + background + sensor_noise + drift + alpha

    artifact_events: list[dict[str, float | str]] = []
    if scenario.contaminated_drawing:
        artifact_events = add_drawing_artifacts(eeg, times, rng, noise_scale)

    # Keep the auxiliary channel present and shaped exactly like the real exports.
    timestamps = 1_792_900_000.0 + scenario.seed + times
    output = np.column_stack((timestamps, eeg, np.zeros(sample_count)))
    metadata = {
        "scenario": scenario_name,
        "expected_result": scenario.expected_result,
        "expected_confidence": scenario.expected_confidence,
        "seed": scenario.seed,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "alpha_range_hz": list(ALPHA_RANGE_HZ),
        "columns": list(CSV_COLUMNS),
        "segments_s": {
            "baseline": [0, 30],
            "imagery": [30, 120],
            "drawing": [120, 210],
            "post_drawing_still": [210, 240],
        },
        "alpha_power_targets": {
            "baseline": 1.0,
            "imagery": scenario.imagery_power,
            "drawing": scenario.drawing_power,
            "post_drawing_still": scenario.post_drawing_power,
        },
        "artifact_events": artifact_events,
        "notes": (
            "Effects change the raw 8–12 Hz alpha amplitude by sqrt(target power). "
            "Expected labels are test expectations, not embedded scores."
        ),
    }
    return output, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-data-dir", type=Path, default=Path("data/real"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/simulated"))
    arguments = parser.parse_args()

    noise_scale, sources = estimate_quiet_noise(arguments.real_data_dir)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    for scenario_name, scenario in SCENARIOS.items():
        samples, metadata = generate_session(scenario_name, scenario, noise_scale)
        metadata["quiet_noise_scale_uv"] = round(noise_scale, 6)
        metadata["noise_reference_files"] = sources
        csv_path = arguments.output_dir / f"{scenario_name}.csv"
        json_path = arguments.output_dir / f"{scenario_name}.json"
        np.savetxt(
            csv_path,
            samples,
            delimiter=",",
            header=",".join(CSV_COLUMNS),
            comments="",
            fmt="%.3f",
        )
        json_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {csv_path} and {json_path}")


if __name__ == "__main__":
    main()

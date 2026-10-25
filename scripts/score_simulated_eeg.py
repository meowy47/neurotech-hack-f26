#!/usr/bin/env python3
"""Score fixtures with the shared Eureka per-window alpha processing contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eeg_scoring import analyze_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/simulated"))
    parser.add_argument("--verify", action="store_true", help="Exit nonzero when a fixture fails its expected label.")
    parser.add_argument("--include-windows", action="store_true", help="Print the shared per-window replay data.")
    arguments = parser.parse_args()

    all_match = True
    for metadata_path in sorted(arguments.data_dir.glob("*.json")):
        result = analyze_session(metadata_path.with_suffix(".csv"), metadata_path)
        if result["matches_expected"] is not None:
            all_match &= bool(result["matches_expected"])
        if not arguments.include_windows:
            result.pop("windows")
        print(json.dumps(result, indent=2))
    if arguments.verify and not all_match:
        raise SystemExit("One or more fixture labels did not match shared alpha processing.")


if __name__ == "__main__":
    main()

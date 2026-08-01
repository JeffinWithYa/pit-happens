"""
Push compact rFactor telemetry frames to the PIT//CALL Next.js ingest API.

Usage (Windows, game running):
  python scripts/push_live_to_web.py
  python scripts/push_live_to_web.py --url http://127.0.0.1:3000 --hz 5
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telemetry_live import compact_frame  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Push rFactor telemetry to PIT//CALL web UI")
    parser.add_argument("--url", default="http://127.0.0.1:3000", help="Next.js base URL")
    parser.add_argument("--hz", type=float, default=5.0, help="Push rate")
    parser.add_argument("--once", action="store_true", help="Push one frame and exit")
    args = parser.parse_args()

    endpoint = args.url.rstrip("/") + "/api/live"
    interval = 1.0 / args.hz if args.hz > 0 else 0.2
    print(f"Pushing telemetry -> {endpoint} @ {args.hz} Hz")

    try:
        while True:
            frame = compact_frame()
            if not frame.get("ok"):
                print(f"  wait: {frame.get('error', 'no data')}")
            else:
                try:
                    res = requests.post(endpoint, json=frame, timeout=5)
                    res.raise_for_status()
                    print(
                        f"  ok lap={frame['lap']} P{frame['place']} "
                        f"{frame['speed_kph']}km/h progress={frame['progress_frac']:.2f}"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  post failed: {exc}")
            if args.once:
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

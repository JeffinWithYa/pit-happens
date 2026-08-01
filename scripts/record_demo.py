"""
Record /api/state into a JSONL demo file while a live session runs.

Capture video of the drive / Hermes chat separately; this only stores
the pit-wall data stream for DEMO replay.

Usage:
  python scripts/record_demo.py --out Build-With-Gemma/frontend/public/demo/recording.jsonl --seconds 90
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Record PIT//CALL state into demo JSONL")
    parser.add_argument("--url", default="http://127.0.0.1:3000")
    parser.add_argument(
        "--out",
        default="Build-With-Gemma/frontend/public/demo/recording.jsonl",
    )
    parser.add_argument("--hz", type=float, default=5.0)
    parser.add_argument("--seconds", type=float, default=0.0, help="0 = until Ctrl+C")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    endpoint = args.url.rstrip("/") + "/api/state"
    interval = 1.0 / args.hz if args.hz > 0 else 0.2
    started = time.time()
    last_agent_ts = None
    last_live_sig = None
    count = 0

    print(f"Recording {endpoint} → {out}")
    with out.open("w", encoding="utf-8") as fh:
        try:
            while True:
                if args.seconds and time.time() - started >= args.seconds:
                    break
                t = time.time() - started
                try:
                    state = requests.get(endpoint, timeout=5).json()
                except Exception as exc:  # noqa: BLE001
                    print(f"  poll failed: {exc}")
                    time.sleep(interval)
                    continue

                live = state.get("live")
                agent = state.get("agent")
                if live:
                    sig = (
                        live.get("lap"),
                        round(float(live.get("progress_frac") or 0), 2),
                        round(float(live.get("speed_kph") or 0), 0),
                        live.get("phase"),
                    )
                    if sig != last_live_sig:
                        fh.write(
                            json.dumps({"t": round(t, 3), "type": "live", "payload": live})
                            + "\n"
                        )
                        last_live_sig = sig
                        count += 1

                if agent and agent.get("ts") != last_agent_ts:
                    fh.write(
                        json.dumps({"t": round(t, 3), "type": "agent", "payload": agent})
                        + "\n"
                    )
                    last_agent_ts = agent.get("ts")
                    count += 1
                    print(f"  +agent @ {t:.1f}s: {agent.get('call', '')[:60]}")

                fh.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")

    print(f"Wrote {count} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Read live rFactor 1 telemetry from the SharedMemoryMap plugin.

Prerequisites:
  1. rFactorSharedMemoryMap.dll is in the game's Plugins folder
  2. rFactor is running and you are in a session (on track / realtime)

Usage:
  python read_telemetry.py
  python read_telemetry.py --once
  python read_telemetry.py --hz 20
"""

from __future__ import annotations

import argparse
import sys
import time
from ctypes import sizeof
from mmap import mmap

from rf1_structs import (
    GAME_PHASE,
    RF_MAP_TAG,
    decode_c_str,
    mps_to_kph,
    rfShared,
)


def open_shared_memory() -> mmap:
    return mmap(fileno=0, length=sizeof(rfShared), tagname=RF_MAP_TAG)


def read_telemetry(handle: mmap) -> rfShared:
    handle.seek(0)
    return rfShared.from_buffer_copy(handle)


def has_session_data(data: rfShared) -> bool:
    return bool(decode_c_str(data.trackName) or data.inRealtime or data.numVehicles > 0)


def format_snapshot(data: rfShared) -> str:
    track = decode_c_str(data.trackName) or "(none)"
    vehicle = decode_c_str(data.vehicleName) or "(none)"
    player = decode_c_str(data.playerName) or "(none)"
    phase = GAME_PHASE.get(data.gamePhase, str(data.gamePhase))

    player_vehicle = None
    for v in data.vehicle[: max(0, data.numVehicles)]:
        if v.isPlayer:
            player_vehicle = v
            break

    lines = [
        f"track={track}  vehicle={vehicle}  player={player}",
        (
            f"realtime={data.inRealtime}  phase={phase}  "
            f"session={data.session}  vehicles={data.numVehicles}"
        ),
        (
            f"lap={data.lapNumber}  gear={data.gear}  "
            f"rpm={data.engineRPM:7.0f}/{data.engineMaxRPM:7.0f}  "
            f"speed={mps_to_kph(data.speed):6.1f} km/h"
        ),
        (
            f"throttle={data.unfilteredThrottle:5.2f}  "
            f"brake={data.unfilteredBrake:5.2f}  "
            f"steer={data.unfilteredSteering:6.2f}  "
            f"clutch={data.unfilteredClutch:5.2f}"
        ),
        (
            f"fuel={data.fuel:5.1f} L  water={data.engineWaterTemp:5.1f} C  "
            f"oil={data.engineOilTemp:5.1f} C  "
            f"et={data.currentET:8.1f}s"
        ),
    ]

    if player_vehicle is not None:
        lines.append(
            f"place=P{player_vehicle.place}  "
            f"best={player_vehicle.bestLapTime:7.3f}s  "
            f"last={player_vehicle.lastLapTime:7.3f}s  "
            f"pits={player_vehicle.inPits}"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read rFactor 1 shared-memory telemetry")
    parser.add_argument("--once", action="store_true", help="Print one sample and exit")
    parser.add_argument("--hz", type=float, default=5.0, help="Refresh rate (default: 5)")
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="Seconds to wait for game data before giving up (0 = forever while polling)",
    )
    args = parser.parse_args()

    try:
        handle = open_shared_memory()
    except OSError as exc:
        print(f"Could not open shared memory map '{RF_MAP_TAG}': {exc}", file=sys.stderr)
        print(
            "Start rFactor with rFactorSharedMemoryMap.dll installed, then retry.",
            file=sys.stderr,
        )
        return 1

    interval = 1.0 / args.hz if args.hz > 0 else 0.2
    started = time.time()
    saw_data = False

    print(f"Listening on '{RF_MAP_TAG}' (struct size={sizeof(rfShared)} bytes)")
    print("Start / join a session in rFactor to see live values. Ctrl+C to stop.\n")

    try:
        while True:
            data = read_telemetry(handle)
            if has_session_data(data):
                saw_data = True
                print(format_snapshot(data))
                print("-" * 72)
                if args.once:
                    return 0
            else:
                elapsed = time.time() - started
                if args.wait and elapsed >= args.wait and not saw_data:
                    print(
                        "No telemetry yet. Is rFactor running in a session?",
                        file=sys.stderr,
                    )
                    return 2
                if args.once and args.wait == 0:
                    print(format_snapshot(data))
                    print(
                        "\n(No active session data — values may be zeros until you are on track.)"
                    )
                    return 0

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    finally:
        handle.close()


if __name__ == "__main__":
    raise SystemExit(main())

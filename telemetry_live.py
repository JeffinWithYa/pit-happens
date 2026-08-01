"""
Live rFactor 1 telemetry helpers (Windows shared memory).

Used by the MCP server so Hermes (WSL) can query the current session
without reading shared memory itself.
"""

from __future__ import annotations

import time
from ctypes import sizeof
from mmap import mmap
from typing import Any

from rf1_structs import (
    GAME_PHASE,
    RF_MAP_TAG,
    decode_c_str,
    mps_to_kph,
    rfShared,
)

FINISH_STATUS = {
    -1: "none",
    0: "none",
    1: "finished",
    2: "dnf",
    3: "dq",
}


def open_shared_memory() -> mmap:
    return mmap(fileno=0, length=sizeof(rfShared), tagname=RF_MAP_TAG)


def read_raw(handle: mmap | None = None) -> tuple[rfShared, mmap | None]:
    owns = handle is None
    h = handle or open_shared_memory()
    try:
        h.seek(0)
        data = rfShared.from_buffer_copy(h)
    finally:
        if owns:
            h.close()
            return data, None
    return data, h


def _lap_time(value: float) -> float | None:
    if value is None or value <= 0:
        return None
    return round(float(value), 3)


def _vehicle_dict(v: Any) -> dict[str, Any]:
    return {
        "driver": decode_c_str(v.driverName) or "?",
        "vehicle": decode_c_str(v.vehicleName) or "?",
        "class": decode_c_str(v.vehicleClass) or "?",
        "place": int(v.place),
        "is_player": bool(v.isPlayer),
        "in_pits": bool(v.inPits),
        "laps": int(v.totalLaps),
        "sector": int(v.sector),
        "best_lap_s": _lap_time(v.bestLapTime),
        "last_lap_s": _lap_time(v.lastLapTime),
        "pitstops": int(v.numPitstops),
        "penalties": int(v.numPenalties),
        "time_behind_next_s": round(float(v.timeBehindNext), 3),
        "laps_behind_next": int(v.lapsBehindNext),
        "time_behind_leader_s": round(float(v.timeBehindLeader), 3),
        "laps_behind_leader": int(v.lapsBehindLeader),
        "finish_status": FINISH_STATUS.get(int(v.finishStatus), str(v.finishStatus)),
        "speed_kph": round(mps_to_kph(float(v.speed)), 1),
    }


def snapshot(data: rfShared | None = None) -> dict[str, Any]:
    """Structured live snapshot suitable for agents / JSON."""
    if data is None:
        try:
            data, _ = read_raw()
        except OSError as exc:
            return {
                "ok": False,
                "error": f"Could not open shared memory '{RF_MAP_TAG}': {exc}",
                "hint": "Start rFactor with rFactorSharedMemoryMap.dll installed.",
                "ts": time.time(),
            }

    phase = GAME_PHASE.get(data.gamePhase, str(data.gamePhase))
    vehicles = [_vehicle_dict(v) for v in data.vehicle[: max(0, int(data.numVehicles))]]
    vehicles.sort(key=lambda row: (row["place"] if row["place"] > 0 else 999, row["driver"]))
    player = next((v for v in vehicles if v["is_player"]), None)

    wheels = []
    for i, name in enumerate(("FL", "FR", "RL", "RR")):
        w = data.wheel[i]
        wheels.append(
            {
                "corner": name,
                "temp_c": [round(float(x), 1) for x in w.temperature],
                "brake_temp_c": round(float(w.brakeTemp), 1),
                # Plugin reports remaining tyre life in 0..1 (1.0 = new).
                "life_remaining": round(float(w.wear), 3),
                "pressure_kpa": round(float(w.pressure), 1),
                "flat": bool(w.flat),
                "detached": bool(w.detached),
            }
        )

    return {
        "ok": True,
        "ts": time.time(),
        "session": {
            "track": decode_c_str(data.trackName) or "(none)",
            "vehicle": decode_c_str(data.vehicleName) or "(none)",
            "player": decode_c_str(data.playerName) or "(none)",
            "realtime": bool(data.inRealtime),
            "phase": phase,
            "session_id": int(data.session),
            "vehicles": int(data.numVehicles),
            "current_et_s": round(float(data.currentET), 1),
            "end_et_s": round(float(data.endET), 1),
            "max_laps": int(data.maxLaps),
            "yellow_flag_state": int(data.yellowFlagState),
            "sector_flags": [int(x) for x in data.sectorFlag],
            "ambient_temp_c": round(float(data.ambientTemp), 1),
            "track_temp_c": round(float(data.trackTemp), 1),
        },
        "car": {
            "lap": int(data.lapNumber),
            "lap_dist_m": round(float(data.lapDist), 1),
            "gear": int(data.gear),
            "rpm": round(float(data.engineRPM), 0),
            "rpm_max": round(float(data.engineMaxRPM), 0),
            "speed_kph": round(mps_to_kph(float(data.speed)), 1),
            "throttle": round(float(data.unfilteredThrottle), 2),
            "brake": round(float(data.unfilteredBrake), 2),
            "steer": round(float(data.unfilteredSteering), 2),
            "clutch": round(float(data.unfilteredClutch), 2),
            "fuel_l": round(float(data.fuel), 1),
            "water_temp_c": round(float(data.engineWaterTemp), 1),
            "oil_temp_c": round(float(data.engineOilTemp), 1),
            "scheduled_stops": int(data.scheduledStops),
            "overheating": bool(data.overheating),
            "last_impact_et_s": round(float(data.lastImpactET), 1),
            "last_impact_mag": round(float(data.lastImpactMagnitude), 2),
            "wheels": wheels,
        },
        "player": player,
        "standings": vehicles,
    }


def compact_frame(snap: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compact frame for PIT//CALL Next.js /api/live ingest."""
    snap = snap if snap is not None else snapshot()
    if not snap.get("ok"):
        return snap

    session = snap["session"]
    car = snap["car"]
    player = snap.get("player") or {}
    wheels = {w["corner"]: w for w in car.get("wheels", [])}

    def life(corner: str) -> float:
        return round(float(wheels.get(corner, {}).get("life_remaining", 1.0)) * 100, 1)

    def temp(corner: str) -> float:
        temps = wheels.get(corner, {}).get("temp_c") or [0, 0, 0]
        return round(float(temps[1] if len(temps) > 1 else temps[0]), 1)

    brakes = [float(wheels.get(c, {}).get("brake_temp_c", 0)) for c in ("FL", "FR", "RL", "RR")]
    standings = []
    for row in snap.get("standings") or []:
        gap = "LEADER" if row.get("place") == 1 else f"+{row.get('time_behind_leader_s', 0):.1f}s"
        standings.append(
            {
                "pos": row.get("place"),
                "driver": row.get("driver"),
                "gap_to_leader": gap,
                "is_player": row.get("is_player"),
            }
        )

    lap = int(car.get("lap") or 0)
    lap_dist = float(car.get("lap_dist_m") or 0)
    if lap_dist > 50:
        progress = max(0.0, min(0.999, (lap_dist % 5000.0) / 5000.0))
    else:
        progress = 0.05

    return {
        "ok": True,
        "ts": snap.get("ts") or time.time(),
        "track": session.get("track") or "Unknown",
        "session": f"S{session.get('session_id', 0)}",
        "lap": lap,
        "total_laps": int(session.get("max_laps") or 0) or None,
        "progress_frac": progress,
        "place": int(player.get("place") or 0),
        "driver": session.get("player") or player.get("driver"),
        "vehicle": session.get("vehicle"),
        "speed_kph": car.get("speed_kph"),
        "gear": car.get("gear"),
        "rpm": car.get("rpm"),
        "rpm_max": car.get("rpm_max"),
        "fuel_l": car.get("fuel_l"),
        "engine_temp_c": car.get("water_temp_c"),
        "oil_temp_c": car.get("oil_temp_c"),
        "brake_temp_c": round(max(brakes) if brakes else 0, 1),
        "throttle": car.get("throttle"),
        "brake": car.get("brake"),
        "clutch": car.get("clutch"),
        "steer": car.get("steer"),
        "in_pits": bool(player.get("in_pits")),
        "best_lap_s": player.get("best_lap_s"),
        "last_lap_s": player.get("last_lap_s"),
        "phase": session.get("phase"),
        "realtime": session.get("realtime"),
        "gap_ahead_sec": float(player.get("time_behind_next_s") or 0),
        "time_behind_leader_s": float(player.get("time_behind_leader_s") or 0),
        "tire_temps_c": {
            "FL": temp("FL"),
            "FR": temp("FR"),
            "RL": temp("RL"),
            "RR": temp("RR"),
        },
        "tire_life_pct": {
            "FL": life("FL"),
            "FR": life("FR"),
            "RL": life("RL"),
            "RR": life("RR"),
        },
        "weather": {
            "track_c": session.get("track_temp_c"),
            "air_c": session.get("ambient_temp_c"),
            "condition": "Dry",
            "wind_kmh": 0,
        },
        "standings": standings[:8],
    }


def summarize(snap: dict[str, Any] | None = None) -> str:
    """Short coach-friendly summary for Hermes."""
    snap = snap if snap is not None else snapshot()
    if not snap.get("ok"):
        return (
            f"rFactor telemetry unavailable: {snap.get('error', 'unknown error')}. "
            f"{snap.get('hint', '')}"
        ).strip()

    s = snap["session"]
    c = snap["car"]
    p = snap.get("player") or {}
    lines = [
        f"Live rFactor session: {s['player']} in {s['vehicle']} at {s['track']}.",
        (
            f"Phase={s['phase']}, realtime={s['realtime']}, "
            f"session_time={s['current_et_s']}s"
            + (f"/{s['end_et_s']}s" if s['end_et_s'] > 0 else "")
            + f", field={s['vehicles']} cars."
        ),
        (
            f"Player: lap {c['lap']}, P{p.get('place', '?')}, "
            f"{c['speed_kph']} km/h, gear {c['gear']}, "
            f"RPM {c['rpm']:.0f}/{c['rpm_max']:.0f}, "
            f"throttle {c['throttle']:.0%}, brake {c['brake']:.0%}."
        ),
        (
            f"Fuel {c['fuel_l']} L, water {c['water_temp_c']} C, oil {c['oil_temp_c']} C"
            + (", OVERHEATING" if c["overheating"] else "")
            + "."
        ),
    ]

    best = p.get("best_lap_s")
    last = p.get("last_lap_s")
    best_txt = f"{best:.3f}s" if best is not None else "n/a"
    last_txt = f"{last:.3f}s" if last is not None else "n/a"
    lines.append(
        f"Laps: best={best_txt}, last={last_txt}, "
        f"pitstops={p.get('pitstops', 0)}, in_pits={p.get('in_pits', False)}."
    )

    if p:
        if p.get("laps_behind_leader", 0):
            gap = f"{p['laps_behind_leader']} lap(s) behind leader"
        else:
            gap = f"{p.get('time_behind_leader_s', 0):.3f}s behind leader"
        if p.get("place", 1) > 1:
            lines.append(
                f"Gaps: {gap}; to car ahead={p.get('time_behind_next_s', 0):.3f}s."
            )
        else:
            lines.append("Gaps: leading the race.")

    if c["last_impact_mag"] > 1.0 and c["last_impact_et_s"] > 0:
        lines.append(
            f"Recent impact: mag={c['last_impact_mag']} at et={c['last_impact_et_s']}s."
        )

    worn = [
        w
        for w in c["wheels"]
        if w["life_remaining"] < 0.85 or w["flat"] or w["detached"]
    ]
    if worn:
        bits = [
            f"{w['corner']} life={w['life_remaining']:.0%}"
            + (" FLAT" if w["flat"] else "")
            + (" DETACHED" if w["detached"] else "")
            for w in worn
        ]
        lines.append("Tyre alerts: " + "; ".join(bits) + ".")

    # Compact standings top 5
    top = snap.get("standings") or []
    if top:
        board = []
        for row in top[:5]:
            mark = "*" if row["is_player"] else ""
            board.append(f"P{row['place']}{mark} {row['driver']}")
        lines.append("Standings: " + ", ".join(board) + (" ..." if len(top) > 5 else ""))

    if s["yellow_flag_state"]:
        lines.append(f"Yellow flag state code={s['yellow_flag_state']}.")

    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize())

"""
Periodic pit-radio coach: read rFactor snapshot -> Spur chat -> POST /api/agent.

Each cycle focuses on a different metric so calls stay specific (not generic).

Usage:
  python scripts/radio_coach_loop.py
  python scripts/radio_coach_loop.py --every 8 --url http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "Build-With-Gemma" / "frontend" / ".env.local")

from telemetry_live import compact_frame, summarize  # noqa: E402

SPUR_BASE = os.getenv("SPUR_BASE_URL", "https://ai.spuric.com/v1").rstrip("/")
SPUR_KEY = os.getenv("SPUR_API_KEY") or os.getenv("SPUR_CHAT_TOKEN") or ""
SPUR_MODEL = os.getenv("SPUR_CHAT_MODEL", "spur-chat")

# Rotate focus so consecutive calls cite different numbers.
FOCUS_CYCLE = (
    "pace",       # speed / gear / rpm / throttle-brake
    "tyres",      # corner temps + wear
    "powertrain", # water / oil / overheating
    "fuel",       # fuel remaining + stint advice
    "gaps",       # place, gap ahead, leader
    "brakes",     # brake temp + brake pressure
    "lap",        # lap / last / best / progress
)


def _fmt(v: object, digits: int = 1) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def metric_brief(frame: dict, focus: str) -> str:
    """Human-readable metric pack the model (or heuristic) must use."""
    tires = frame.get("tire_temps_c") or {}
    life = frame.get("tire_life_pct") or {}
    weather = frame.get("weather") or {}

    packs = {
        "pace": (
            f"speed={_fmt(frame.get('speed_kph'))}km/h gear={frame.get('gear')} "
            f"rpm={_fmt(frame.get('rpm'), 0)}/{_fmt(frame.get('rpm_max'), 0)} "
            f"throttle={_fmt((frame.get('throttle') or 0) * 100, 0)}% "
            f"brake={_fmt((frame.get('brake') or 0) * 100, 0)}%"
        ),
        "tyres": (
            f"temps FL/FR/RL/RR="
            f"{_fmt(tires.get('FL'))}/{_fmt(tires.get('FR'))}/"
            f"{_fmt(tires.get('RL'))}/{_fmt(tires.get('RR'))}C "
            f"life={_fmt(life.get('FL'), 0)}/{_fmt(life.get('FR'), 0)}/"
            f"{_fmt(life.get('RL'), 0)}/{_fmt(life.get('RR'), 0)}%"
        ),
        "powertrain": (
            f"water={_fmt(frame.get('engine_temp_c'))}C "
            f"oil={_fmt(frame.get('oil_temp_c'))}C "
            f"phase={frame.get('phase')} realtime={frame.get('realtime')}"
        ),
        "fuel": (
            f"fuel={_fmt(frame.get('fuel_l'))}L "
            f"lap={frame.get('lap')} total={frame.get('total_laps')} "
            f"in_pits={frame.get('in_pits')}"
        ),
        "gaps": (
            f"P{frame.get('place')} gap_ahead={_fmt(frame.get('gap_ahead_sec'))}s "
            f"behind_leader={_fmt(frame.get('time_behind_leader_s'))}s "
            f"driver={frame.get('driver')}"
        ),
        "brakes": (
            f"brake_temp={_fmt(frame.get('brake_temp_c'))}C "
            f"brake_input={_fmt((frame.get('brake') or 0) * 100, 0)}% "
            f"speed={_fmt(frame.get('speed_kph'))}km/h"
        ),
        "lap": (
            f"lap={frame.get('lap')} progress={_fmt((frame.get('progress_frac') or 0) * 100, 0)}% "
            f"last={_fmt(frame.get('last_lap_s'), 3)}s "
            f"best={_fmt(frame.get('best_lap_s'), 3)}s "
            f"track_temp={_fmt(weather.get('track_c'))}C"
        ),
    }
    return packs.get(focus, packs["pace"])


def heuristic_call(frame: dict, focus: str) -> dict:
    """Deterministic radio with real numbers when Spur is unavailable."""
    brief = metric_brief(frame, focus)
    speed = float(frame.get("speed_kph") or 0)
    fuel = float(frame.get("fuel_l") or 0)
    water = float(frame.get("engine_temp_c") or 0)
    brake_t = float(frame.get("brake_temp_c") or 0)
    tires = frame.get("tire_temps_c") or {}
    life = frame.get("tire_life_pct") or {}
    place = frame.get("place") or "?"
    gap = float(frame.get("gap_ahead_sec") or 0)
    pits = bool(frame.get("in_pits"))

    if focus == "tyres":
        fr = float(tires.get("FR") or 0)
        fl = float(tires.get("FL") or 0)
        text = f"Tyres: FL {fl:.0f}C FR {fr:.0f}C, life {float(life.get('FL') or 100):.0f}/{float(life.get('FR') or 100):.0f}%. Keep them in the window."
    elif focus == "powertrain":
        text = f"Water {water:.0f}C, oil {float(frame.get('oil_temp_c') or 0):.0f}C. {'Lift and cool.' if water >= 105 else 'Temps look OK — push.'}"
    elif focus == "fuel":
        text = f"Fuel {fuel:.1f} litres. {'Box this lap if clear.' if fuel < 8 else 'Fuel OK for the stint — stay out.'}"
    elif focus == "gaps":
        text = f"P{place}, gap ahead {gap:.1f}s. {'Hold position, no risks.' if gap < 0.4 and place != 1 else 'Keep the pressure on.'}"
    elif focus == "brakes":
        text = f"Brakes {brake_t:.0f}C at {speed:.0f} km/h. {'Short-brake and cool.' if brake_t >= 600 else 'Brake temps fine.'}"
    elif focus == "lap":
        last = frame.get("last_lap_s")
        last_txt = f"{float(last):.3f}s" if last else "no last lap"
        text = f"Lap {frame.get('lap')}, last {last_txt}. Stay clean through the next sector."
    else:  # pace
        if pits:
            text = f"In pits, {speed:.0f} km/h. Hold brakes, confirm fuel {fuel:.1f}L before release."
        elif speed < 5:
            text = f"Standing at {speed:.0f} km/h. Build tyre temps gently when you roll."
        else:
            gear = frame.get("gear")
            thr = float(frame.get("throttle") or 0) * 100
            text = f"{speed:.0f} km/h, gear {gear}, throttle {thr:.0f}%. Pace is live — keep it tidy."

    return {
        "call": text,
        "speak": text,
        "confidence_pct": 68,
        "evidence": [f"focus={focus}", brief],
        "rag_refs": [],
    }


def generate_call(summary: str, frame: dict, focus: str, recent: list[str]) -> dict:
    """Ask Spur for a short pit-wall radio message tied to the focus metrics."""
    if not SPUR_KEY:
        return heuristic_call(frame, focus)

    brief = metric_brief(frame, focus)
    recent_block = "\n".join(f"- {r}" for r in recent[-4:]) or "- (none yet)"

    system = (
        "You are an F1-style race engineer on the pit wall radio. "
        "Reply with ONLY compact JSON (no markdown): "
        '{"call":"...","speak":"...","confidence_pct":0-100,'
        '"evidence":["..."],"rag_refs":[]} . '
        "RULES: "
        "1) speak <= 28 words, driver radio voice. "
        "2) MUST include at least two concrete numbers from FOCUS METRICS. "
        "3) Stay on the assigned focus topic — do not give a generic 'stay out' only. "
        "4) Do not repeat the recent calls. "
        "5) Prefer actionable coaching (BOX / STAY OUT / MANAGE / LIFT & COAST / PUSH) when relevant."
    )
    user = (
        f"FOCUS TOPIC: {focus}\n"
        f"FOCUS METRICS (use these numbers): {brief}\n\n"
        f"Recent calls to avoid repeating:\n{recent_block}\n\n"
        f"Live summary:\n{summary}\n\n"
        f"Compact frame JSON:\n{json.dumps(frame)[:2200]}"
    )
    res = requests.post(
        f"{SPUR_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {SPUR_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": SPUR_MODEL,
            "temperature": 0.55,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=45,
    )
    res.raise_for_status()
    content = res.json()["choices"][0]["message"]["content"]
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = heuristic_call(frame, focus)
        data["evidence"] = [f"focus={focus}", "unparsed model — heuristic used", brief]
        return data

    data.setdefault("speak", data.get("call", "Stay out."))
    data.setdefault("confidence_pct", 72)
    evidence = list(data.get("evidence") or [])
    evidence = [f"focus={focus}", brief, *evidence][:6]
    data["evidence"] = evidence
    data.setdefault("rag_refs", [])
    return data


def post_agent(base_url: str, payload: dict) -> None:
    body = {
        "ts": time.time(),
        "call": payload.get("call") or payload.get("speak"),
        "speak": payload.get("speak") or payload.get("call"),
        "confidence_pct": int(payload.get("confidence_pct") or 70),
        "evidence": list(payload.get("evidence") or [])[:6],
        "rag_refs": list(payload.get("rag_refs") or [])[:4],
        "source": "coach",
    }
    res = requests.post(f"{base_url.rstrip('/')}/api/agent", json=body, timeout=20)
    res.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Periodic pit-radio coach loop")
    parser.add_argument("--url", default=os.getenv("PITCALL_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--every", type=float, default=8.0, help="Seconds between radio calls")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    print(f"Radio coach -> {args.url}/api/agent every {args.every}s model={SPUR_MODEL}")
    recent: list[str] = []
    tick = 0
    while True:
        try:
            frame = compact_frame()
            if not frame.get("ok"):
                print(f"  wait telemetry: {frame.get('error', 'unavailable')}")
            else:
                focus = FOCUS_CYCLE[tick % len(FOCUS_CYCLE)]
                tick += 1
                summary = summarize()
                payload = {k: v for k, v in frame.items() if k != "ok"}
                # Clamp nonsense unlimited-lap sentinel for the model
                total = payload.get("total_laps")
                if isinstance(total, int) and total > 500:
                    payload["total_laps"] = None
                call = generate_call(summary, payload, focus, recent)
                post_agent(args.url, call)
                speak = str(call.get("speak") or call.get("call") or "")
                recent.append(speak)
                recent = recent[-6:]
                print(f"  [{focus}] radio: {speak}")
        except Exception as exc:  # noqa: BLE001
            print(f"  coach error: {exc}")
        if args.once:
            return 0
        time.sleep(max(4.0, args.every))


if __name__ == "__main__":
    raise SystemExit(main())

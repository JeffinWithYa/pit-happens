"""
Periodic pit-radio coach: read rFactor snapshot -> Spur chat -> POST /api/agent.

This keeps the web transcript + TTS fed even when Hermes isn't in an interactive loop.
Hermes can still post via pitcall_post_agent(); this is the auto-radio path.

Usage:
  python scripts/radio_coach_loop.py
  python scripts/radio_coach_loop.py --every 20 --url http://127.0.0.1:3000
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


def generate_call(summary: str, frame: dict) -> dict:
    """Ask Spur for a short pit-wall radio message."""
    if not SPUR_KEY:
        # Deterministic fallback so radio still works without Spur
        speed = frame.get("speed_kph") or 0
        fuel = frame.get("fuel_l") or 0
        water = frame.get("engine_temp_c") or 0
        pits = frame.get("in_pits")
        if pits:
            text = "In pits. Hold brakes, confirm tyre set and fuel before release."
        elif water >= 105:
            text = "Lift and coast. Water temp is high — short-shift and cool the power unit."
        elif speed < 5:
            text = "Standing. Build temps gently when you roll — no flat-spot on cold tyres."
        elif fuel < 8:
            text = "Fuel is low. Box this lap if the window is clear."
        else:
            text = "Stay out. Pace looks stable — keep tyre temps in the window."
        return {
            "call": text,
            "speak": text,
            "confidence_pct": 60,
            "evidence": ["local heuristic (no Spur key)"],
            "rag_refs": [],
        }

    system = (
        "You are an F1-style race engineer on the pit wall radio. "
        "Given live sim telemetry, reply with ONLY compact JSON: "
        '{"call":"...","speak":"...","confidence_pct":0-100,'
        '"evidence":["..."],"rag_refs":[]} . '
        "speak must be <= 25 words, spoken aloud to the driver. "
        "call can be slightly longer. Prefer BOX / STAY OUT / MANAGE TYRES / LIFT & COAST "
        "when relevant. No markdown."
    )
    user = f"Live summary:\n{summary}\n\nCompact frame JSON:\n{json.dumps(frame)[:1800]}"
    res = requests.post(
        f"{SPUR_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {SPUR_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": SPUR_MODEL,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=60,
    )
    res.raise_for_status()
    content = res.json()["choices"][0]["message"]["content"]
    # Strip fences if model wraps JSON
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {
            "call": text[:200],
            "speak": text[:160],
            "confidence_pct": 70,
            "evidence": ["unparsed model text"],
            "rag_refs": [],
        }
    data.setdefault("speak", data.get("call", "Stay out."))
    data.setdefault("confidence_pct", 70)
    data.setdefault("evidence", [])
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
        # UI auto-TTS only for source=coach (LIVE RF1 / Hermes posts stay silent)
        "source": "coach",
    }
    res = requests.post(f"{base_url.rstrip('/')}/api/agent", json=body, timeout=30)
    res.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Periodic pit-radio coach loop")
    parser.add_argument("--url", default=os.getenv("PITCALL_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--every", type=float, default=18.0, help="Seconds between radio calls")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    print(f"Radio coach -> {args.url}/api/agent every {args.every}s model={SPUR_MODEL}")
    while True:
        try:
            frame = compact_frame()
            if not frame.get("ok"):
                print(f"  wait telemetry: {frame.get('error', 'unavailable')}")
            else:
                summary = summarize()
                payload = {k: v for k, v in frame.items() if k != "ok"}
                call = generate_call(summary, payload)
                post_agent(args.url, call)
                print(f"  radio: {call.get('speak') or call.get('call')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  coach error: {exc}")
        if args.once:
            return 0
        time.sleep(max(5.0, args.every))


if __name__ == "__main__":
    raise SystemExit(main())

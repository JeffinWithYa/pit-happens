"""
Post a Hermes / Gemma pit-wall call to the Next.js /api/agent endpoint.

Usage:
  python scripts/post_agent_to_web.py --call "STAY OUT. Manage rears." --speak "Stay out. Manage the rears."
  python scripts/post_agent_to_web.py --call "BOX NOW" --confidence 90 --evidence "FR cliff" "SC window"
"""

from __future__ import annotations

import argparse
import json
import time

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Post agent recommendation to PIT//CALL")
    parser.add_argument("--url", default="http://127.0.0.1:3000")
    parser.add_argument("--call", required=True, help="Decision / coaching text")
    parser.add_argument("--speak", default=None, help="TTS text (defaults to --call)")
    parser.add_argument("--confidence", type=int, default=75)
    parser.add_argument("--evidence", nargs="*", default=[])
    parser.add_argument("--rag-ref", action="append", default=[])
    parser.add_argument("--citation", default=None)
    args = parser.parse_args()

    payload = {
        "ts": time.time(),
        "call": args.call,
        "speak": args.speak or args.call,
        "confidence_pct": args.confidence,
        "evidence": args.evidence,
        "rag_refs": args.rag_ref,
        "regulation_citation": args.citation,
    }
    endpoint = args.url.rstrip("/") + "/api/agent"
    res = requests.post(endpoint, json=payload, timeout=10)
    print(res.status_code, json.dumps(res.json(), indent=2)[:1200])
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

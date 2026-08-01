from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import fastf1
import pandas as pd

from rag.config import FASTF1_CACHE, SEASONS, SESSION_TYPES


@dataclass
class SessionBundle:
    year: int
    round_number: int
    event_name: str
    country: str
    location: str
    session_type: str
    session_name: str
    session: Any


def configure_cache() -> None:
    FASTF1_CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(FASTF1_CACHE))


def iter_target_sessions(
    seasons: tuple[int, ...] = SEASONS,
    session_types: tuple[str, ...] = SESSION_TYPES,
) -> Iterator[tuple[int, pd.Series, str]]:
    """Yield (year, event_row, session_type) for completed race/sprint sessions."""
    today = pd.Timestamp.utcnow().tz_localize(None)
    for year in seasons:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            if int(event.get("RoundNumber", 0) or 0) <= 0:
                continue
            for stype in session_types:
                date_col = {
                    "R": "Session5Date",
                    "S": "Session3Date",
                }.get(stype)
                # Prefer official session date columns when present.
                event_date = event.get("EventDate")
                if date_col and date_col in event and pd.notna(event.get(date_col)):
                    event_date = event.get(date_col)
                if pd.isna(event_date):
                    continue
                ts = pd.Timestamp(event_date).tz_localize(None)
                if ts > today:
                    continue
                # Sprint only when the weekend actually has one.
                if stype == "S":
                    fmt = str(event.get("EventFormat", "")).lower()
                    if "sprint" not in fmt:
                        continue
                yield year, event, stype


def load_session(
    year: int,
    event: pd.Series,
    session_type: str,
    *,
    retries: int = 4,
) -> SessionBundle | None:
    round_number = int(event["RoundNumber"])
    event_name = str(event["EventName"])
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            session = fastf1.get_session(year, round_number, session_type)
            # No telemetry/weather: keeps cache and RAM small for RAG text docs.
            session.load(laps=True, telemetry=False, weather=False, messages=True)
            if session.laps is None or session.laps.empty:
                print(f"  skip {year} R{round_number} {session_type}: no lap data")
                return None
            return SessionBundle(
                year=year,
                round_number=round_number,
                event_name=event_name,
                country=str(event.get("Country", "")),
                location=str(event.get("Location", "")),
                session_type=session_type,
                session_name=str(getattr(session, "name", session_type)),
                session=session,
            )
        except Exception as exc:  # noqa: BLE001 - FastF1 raises varied errors for missing sessions
            last_exc = exc
            msg = str(exc).lower()
            if "500 calls" in msg or "rate" in msg:
                wait = 60 * (attempt + 1)
                print(
                    f"  rate-limited {year} R{round_number} {session_type}; "
                    f"sleeping {wait}s (attempt {attempt + 1}/{retries})"
                )
                time.sleep(wait)
                continue
            print(f"  skip {year} R{round_number} {session_type}: {exc}")
            return None

    print(f"  skip {year} R{round_number} {session_type}: {last_exc}")
    return None

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from rag.config import MAX_COMPARISONS_PER_SESSION, MAX_TURNING_POINTS_PER_SESSION
from rag.fetch_sessions import SessionBundle
from rag.utils import doc_id, safe_str, timedelta_to_str


def _base_meta(bundle: SessionBundle, doc_type: str, **extra: Any) -> dict[str, Any]:
    meta = {
        "doc_type": doc_type,
        "year": bundle.year,
        "round": bundle.round_number,
        "event": bundle.event_name,
        "country": bundle.country,
        "location": bundle.location,
        "session_type": bundle.session_type,
        "session_name": bundle.session_name,
    }
    meta.update(extra)
    # Chroma metadata values must be str/int/float/bool
    clean: dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def _make_doc(
    bundle: SessionBundle,
    doc_type: str,
    title: str,
    text: str,
    **extra: Any,
) -> dict[str, Any]:
    body = f"{title}\n\n{text.strip()}".strip()
    return {
        "id": doc_id(
            bundle.year,
            bundle.round_number,
            bundle.session_type,
            doc_type,
            title,
            body[:120],
        ),
        "text": body,
        "metadata": _base_meta(bundle, doc_type, title=title, **extra),
    }


def race_control_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    msgs = bundle.session.race_control_messages
    if msgs is None or msgs.empty:
        return []

    docs: list[dict[str, Any]] = []
    # Chunk ~8 messages to keep retrieval granular without exploding count.
    chunk_size = 8
    rows = msgs.reset_index(drop=True)
    for start in range(0, len(rows), chunk_size):
        chunk = rows.iloc[start : start + chunk_size]
        lines = []
        for _, row in chunk.iterrows():
            t = timedelta_to_str(row.get("Time"))
            cat = safe_str(row.get("Category"), "Message")
            flag = safe_str(row.get("Flag"))
            msg = safe_str(row.get("Message"))
            racing = safe_str(row.get("RacingNumber"))
            bits = [f"[{t}]" if t else "[--]", cat]
            if flag:
                bits.append(f"flag={flag}")
            if racing:
                bits.append(f"car={racing}")
            bits.append(msg)
            lines.append(" ".join(bits))
        title = (
            f"{bundle.year} {bundle.event_name} {bundle.session_name} "
            f"race control messages {start + 1}-{start + len(chunk)}"
        )
        docs.append(
            _make_doc(
                bundle,
                "race_control",
                title,
                "\n".join(lines),
                chunk_index=start // chunk_size,
            )
        )
    return docs


def _driver_label(laps: pd.DataFrame, driver: str) -> str:
    subset = laps[laps["Driver"] == driver]
    if subset.empty:
        return driver
    team = safe_str(subset.iloc[0].get("Team"))
    return f"{driver} ({team})" if team else driver


def lap_summary_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    """One compact per-driver lap summary (not one doc per lap)."""
    laps = bundle.session.laps
    docs: list[dict[str, Any]] = []
    for driver in sorted(laps["Driver"].dropna().unique()):
        dlaps = laps.pick_drivers(driver).pick_accurate()
        if dlaps.empty:
            dlaps = laps.pick_drivers(driver)
        if dlaps.empty:
            continue

        valid = dlaps[dlaps["LapTime"].notna()]
        best = valid["LapTime"].min() if not valid.empty else None
        avg = valid["LapTime"].mean() if not valid.empty else None
        start_pos = dlaps.iloc[0].get("Position")
        end_pos = dlaps.iloc[-1].get("Position")
        pits = int(dlaps["PitInTime"].notna().sum())
        deleted = dlaps[dlaps.get("Deleted") == True] if "Deleted" in dlaps else dlaps.iloc[0:0]  # noqa: E712
        compounds = [
            safe_str(c)
            for c in dlaps["Compound"].dropna().unique().tolist()
            if safe_str(c)
        ]

        lines = [
            f"Driver: {_driver_label(laps, driver)}",
            f"Event: {bundle.year} {bundle.event_name} — {bundle.session_name}",
            f"Laps completed: {int(dlaps['LapNumber'].max() or len(dlaps))}",
            f"Best lap: {timedelta_to_str(best) or 'n/a'}",
            f"Average lap: {timedelta_to_str(avg) or 'n/a'}",
            f"Position start→end: {safe_str(start_pos, '?')} → {safe_str(end_pos, '?')}",
            f"Pit entries: {pits}",
            f"Tyre compounds used: {', '.join(compounds) or 'unknown'}",
        ]
        if not deleted.empty:
            reasons = []
            for _, row in deleted.iterrows():
                reasons.append(
                    f"lap {safe_str(row.get('LapNumber'))}: "
                    f"{safe_str(row.get('DeletedReason'), 'deleted')}"
                )
            lines.append("Deleted laps: " + "; ".join(reasons[:6]))

        # Highlight a few notable laps: best + biggest position gain/loss.
        notable = []
        if best is not None and not valid.empty:
            best_lap = valid.loc[valid["LapTime"].idxmin()]
            notable.append(
                f"personal best on lap {safe_str(best_lap.get('LapNumber'))} "
                f"({timedelta_to_str(best_lap.get('LapTime'))}, {safe_str(best_lap.get('Compound'))})"
            )
        pos = dlaps[dlaps["Position"].notna()].copy()
        if len(pos) >= 2:
            pos["delta"] = pos["Position"].diff()
            drop = pos["delta"].min()
            rise = pos["delta"].max()
            if pd.notna(drop) and drop <= -2:
                row = pos.loc[pos["delta"].idxmin()]
                notable.append(
                    f"gained positions around lap {safe_str(row.get('LapNumber'))} "
                    f"(to P{safe_str(row.get('Position'))})"
                )
            if pd.notna(rise) and rise >= 2:
                row = pos.loc[pos["delta"].idxmax()]
                notable.append(
                    f"lost positions around lap {safe_str(row.get('LapNumber'))} "
                    f"(to P{safe_str(row.get('Position'))})"
                )
        if notable:
            lines.append("Notable moments: " + "; ".join(notable))

        docs.append(
            _make_doc(
                bundle,
                "lap_summary",
                f"{bundle.year} {bundle.event_name} {bundle.session_name} lap summary — {driver}",
                "\n".join(lines),
                driver=driver,
            )
        )
    return docs


def stint_summary_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    laps = bundle.session.laps
    docs: list[dict[str, Any]] = []
    for driver in sorted(laps["Driver"].dropna().unique()):
        dlaps = laps.pick_drivers(driver)
        if dlaps.empty or "Stint" not in dlaps:
            continue
        for stint_no, stint in dlaps.groupby("Stint"):
            if pd.isna(stint_no):
                continue
            compound = safe_str(stint.iloc[0].get("Compound"), "UNKNOWN")
            tyre_life_start = stint.iloc[0].get("TyreLife")
            lap_from = int(stint["LapNumber"].min())
            lap_to = int(stint["LapNumber"].max())
            valid = stint[stint["LapTime"].notna()]
            best = valid["LapTime"].min() if not valid.empty else None
            avg = valid["LapTime"].mean() if not valid.empty else None
            start_pos = stint.iloc[0].get("Position")
            end_pos = stint.iloc[-1].get("Position")
            fresh = stint.iloc[0].get("FreshTyre")

            text = "\n".join(
                [
                    f"Driver: {_driver_label(laps, driver)}",
                    f"Event: {bundle.year} {bundle.event_name} — {bundle.session_name}",
                    f"Stint {int(stint_no)}: laps {lap_from}-{lap_to} ({len(stint)} laps)",
                    f"Compound: {compound}",
                    f"Fresh tyre at stint start: {safe_str(fresh, 'unknown')}",
                    f"Tyre life at stint start: {safe_str(tyre_life_start, 'unknown')}",
                    f"Best lap in stint: {timedelta_to_str(best) or 'n/a'}",
                    f"Average lap in stint: {timedelta_to_str(avg) or 'n/a'}",
                    f"Position start→end of stint: {safe_str(start_pos, '?')} → {safe_str(end_pos, '?')}",
                ]
            )
            docs.append(
                _make_doc(
                    bundle,
                    "stint_summary",
                    (
                        f"{bundle.year} {bundle.event_name} {bundle.session_name} "
                        f"stint {int(stint_no)} — {driver} on {compound}"
                    ),
                    text,
                    driver=driver,
                    stint=int(stint_no),
                    compound=compound,
                )
            )
    return docs


def strategy_summary_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    laps = bundle.session.laps
    docs: list[dict[str, Any]] = []
    for driver in sorted(laps["Driver"].dropna().unique()):
        dlaps = laps.pick_drivers(driver).sort_values("LapNumber")
        if dlaps.empty:
            continue
        stints = []
        if "Stint" in dlaps:
            for stint_no, stint in dlaps.groupby("Stint"):
                if pd.isna(stint_no):
                    continue
                compound = safe_str(stint.iloc[0].get("Compound"), "?")
                lap_from = int(stint["LapNumber"].min())
                lap_to = int(stint["LapNumber"].max())
                stints.append(f"Stint {int(stint_no)}: {compound} laps {lap_from}-{lap_to}")
        pit_laps = [
            int(x)
            for x in dlaps.loc[dlaps["PitInTime"].notna(), "LapNumber"].tolist()
            if pd.notna(x)
        ]
        start_pos = dlaps.iloc[0].get("Position")
        end_pos = dlaps.iloc[-1].get("Position")
        finish = ""
        results = getattr(bundle.session, "results", None)
        if results is not None and not results.empty:
            row = results[results["Abbreviation"] == driver]
            if not row.empty:
                status = safe_str(row.iloc[0].get("Status"))
                classified = safe_str(row.iloc[0].get("ClassifiedPosition"))
                points = row.iloc[0].get("Points")
                finish = f"Result: P{classified or safe_str(end_pos)} ({status}), points={safe_str(points, '0')}"

        lines = [
            f"Strategy summary for {_driver_label(laps, driver)}",
            f"Event: {bundle.year} {bundle.event_name} — {bundle.session_name}",
            f"Grid/start position → finish position: {safe_str(start_pos, '?')} → {safe_str(end_pos, '?')}",
            finish,
            f"Pit laps: {', '.join(str(p) for p in pit_laps) or 'none'}",
            "Stint plan:",
        ]
        if stints:
            lines.extend(f"- {s}" for s in stints)
        else:
            lines.append("- unavailable")
        text = "\n".join(line for line in lines if line)
        docs.append(
            _make_doc(
                bundle,
                "strategy_summary",
                f"{bundle.year} {bundle.event_name} {bundle.session_name} strategy — {driver}",
                text,
                driver=driver,
            )
        )
    return docs


def incident_summary_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    msgs = bundle.session.race_control_messages
    docs: list[dict[str, Any]] = []
    if msgs is None or msgs.empty:
        return docs

    keywords = (
        "incident",
        "collision",
        "crash",
        "accident",
        "penalty",
        "investigat",
        "black and white",
        "track limits",
        "safety car",
        "virtual safety",
        "red flag",
        "debris",
        "stopped",
        "retired",
        "unsafe release",
        "forcing",
        "causing a collision",
    )
    incidents = []
    for _, row in msgs.iterrows():
        msg = safe_str(row.get("Message")).lower()
        cat = safe_str(row.get("Category")).lower()
        flag = safe_str(row.get("Flag")).lower()
        blob = f"{cat} {flag} {msg}"
        if any(k in blob for k in keywords):
            incidents.append(row)

    if not incidents:
        return docs

    # Group into windows of ~5 related messages chronologically.
    for i in range(0, len(incidents), 5):
        group = incidents[i : i + 5]
        lines = []
        cars = set()
        for row in group:
            t = timedelta_to_str(row.get("Time"))
            lines.append(
                f"[{t or '--'}] {safe_str(row.get('Category'))}: {safe_str(row.get('Message'))}"
            )
            rn = safe_str(row.get("RacingNumber"))
            if rn:
                cars.add(rn)
        title = (
            f"{bundle.year} {bundle.event_name} {bundle.session_name} "
            f"incident summary {i // 5 + 1}"
        )
        text = (
            f"Incident / race-control cluster from {bundle.year} {bundle.event_name} "
            f"{bundle.session_name}.\n"
            f"Cars referenced: {', '.join(sorted(cars)) or 'n/a'}\n\n"
            + "\n".join(lines)
        )
        docs.append(
            _make_doc(
                bundle,
                "incident_summary",
                title,
                text,
                cars=",".join(sorted(cars)),
            )
        )

    # Also summarize deleted laps as track-limits / stewarding incidents.
    laps = bundle.session.laps
    if "Deleted" in laps.columns:
        deleted = laps[laps["Deleted"] == True]  # noqa: E712
        if not deleted.empty:
            by_driver: dict[str, list[str]] = defaultdict(list)
            for _, row in deleted.iterrows():
                by_driver[safe_str(row.get("Driver"))].append(
                    f"lap {safe_str(row.get('LapNumber'))}: "
                    f"{safe_str(row.get('DeletedReason'), 'deleted')}"
                )
            lines = [
                f"Deleted-lap stewarding summary for {bundle.year} {bundle.event_name} "
                f"{bundle.session_name}:"
            ]
            for drv, items in sorted(by_driver.items()):
                lines.append(f"- {drv}: " + "; ".join(items[:8]))
            docs.append(
                _make_doc(
                    bundle,
                    "incident_summary",
                    f"{bundle.year} {bundle.event_name} {bundle.session_name} deleted laps summary",
                    "\n".join(lines),
                )
            )
    return docs


def comparison_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    laps = bundle.session.laps
    results = getattr(bundle.session, "results", None)
    docs: list[dict[str, Any]] = []
    pairs: list[tuple[str, str, str]] = []

    # Teammate comparisons.
    if results is not None and not results.empty and "TeamName" in results:
        for team, group in results.groupby("TeamName"):
            ab = [safe_str(x) for x in group["Abbreviation"].tolist() if safe_str(x)]
            if len(ab) >= 2:
                pairs.append((ab[0], ab[1], f"teammates at {team}"))

    # Close finishers / podium-adjacent.
    if results is not None and not results.empty and "ClassifiedPosition" in results:
        classified = results.copy()
        classified["_pos"] = pd.to_numeric(classified["ClassifiedPosition"], errors="coerce")
        classified = classified.dropna(subset=["_pos"]).sort_values("_pos")
        top = [safe_str(x) for x in classified["Abbreviation"].head(6).tolist()]
        for a, b in zip(top, top[1:]):
            pairs.append((a, b, "nearby classified finishers"))

    seen = set()
    for a, b, reason in pairs:
        key = tuple(sorted((a, b)))
        if key in seen or a == b:
            continue
        seen.add(key)
        if len(docs) >= MAX_COMPARISONS_PER_SESSION:
            break

        la = laps.pick_drivers(a)
        lb = laps.pick_drivers(b)
        if la.empty or lb.empty:
            continue
        va = la[la["LapTime"].notna()]
        vb = lb[lb["LapTime"].notna()]
        best_a = va["LapTime"].min() if not va.empty else None
        best_b = vb["LapTime"].min() if not vb.empty else None
        avg_a = va["LapTime"].mean() if not va.empty else None
        avg_b = vb["LapTime"].mean() if not vb.empty else None

        # Overlap pace on shared lap numbers.
        merged = pd.merge(
            va[["LapNumber", "LapTime", "Position", "Compound"]].rename(
                columns={
                    "LapTime": "LapTimeA",
                    "Position": "PosA",
                    "Compound": "CompA",
                }
            ),
            vb[["LapNumber", "LapTime", "Position", "Compound"]].rename(
                columns={
                    "LapTime": "LapTimeB",
                    "Position": "PosB",
                    "Compound": "CompB",
                }
            ),
            on="LapNumber",
            how="inner",
        )
        pace_note = "insufficient overlapping timed laps"
        if not merged.empty:
            merged["delta"] = (
                merged["LapTimeA"].dt.total_seconds() - merged["LapTimeB"].dt.total_seconds()
            )
            mean_delta = float(merged["delta"].mean())
            faster = a if mean_delta < 0 else b
            pace_note = (
                f"On {len(merged)} shared timed laps, {faster} was faster on average by "
                f"{abs(mean_delta):.3f}s/lap."
            )

        text = "\n".join(
            [
                f"Driver comparison: {a} vs {b}",
                f"Context: {reason}",
                f"Event: {bundle.year} {bundle.event_name} — {bundle.session_name}",
                f"{a} best/avg lap: {timedelta_to_str(best_a) or 'n/a'} / {timedelta_to_str(avg_a) or 'n/a'}",
                f"{b} best/avg lap: {timedelta_to_str(best_b) or 'n/a'} / {timedelta_to_str(avg_b) or 'n/a'}",
                f"{a} position start→end: {safe_str(la.iloc[0].get('Position'), '?')} → {safe_str(la.iloc[-1].get('Position'), '?')}",
                f"{b} position start→end: {safe_str(lb.iloc[0].get('Position'), '?')} → {safe_str(lb.iloc[-1].get('Position'), '?')}",
                pace_note,
            ]
        )
        docs.append(
            _make_doc(
                bundle,
                "driver_comparison",
                f"{bundle.year} {bundle.event_name} {bundle.session_name} comparison — {a} vs {b}",
                text,
                drivers=f"{a},{b}",
            )
        )
    return docs


def turning_point_docs(bundle: SessionBundle) -> list[dict[str, Any]]:
    laps = bundle.session.laps
    docs: list[dict[str, Any]] = []

    # Lead changes.
    leaders = (
        laps[laps["Position"] == 1][["LapNumber", "Driver", "Team"]]
        .dropna()
        .sort_values("LapNumber")
    )
    if not leaders.empty:
        prev = None
        for _, row in leaders.iterrows():
            drv = safe_str(row.get("Driver"))
            lap_no = int(row.get("LapNumber"))
            if prev is None:
                docs.append(
                    _make_doc(
                        bundle,
                        "turning_point",
                        f"{bundle.year} {bundle.event_name} {bundle.session_name} — early lead",
                        (
                            f"Turning point: {drv} led on lap {lap_no} at "
                            f"{bundle.year} {bundle.event_name} {bundle.session_name}. "
                            f"This established the early race lead."
                        ),
                        driver=drv,
                        lap=lap_no,
                    )
                )
            elif drv != prev:
                docs.append(
                    _make_doc(
                        bundle,
                        "turning_point",
                        f"{bundle.year} {bundle.event_name} {bundle.session_name} — lead change lap {lap_no}",
                        (
                            f"Turning point on lap {lap_no}: {drv} took the lead from {prev} "
                            f"during {bundle.year} {bundle.event_name} {bundle.session_name}. "
                            f"Lead changes often follow undercuts, safety cars, or on-track passes."
                        ),
                        driver=drv,
                        lap=lap_no,
                    )
                )
            prev = drv
            if len(docs) >= MAX_TURNING_POINTS_PER_SESSION:
                break

    # Safety car / VSC / red flag windows from race control.
    msgs = bundle.session.race_control_messages
    if msgs is not None and not msgs.empty and len(docs) < MAX_TURNING_POINTS_PER_SESSION:
        for _, row in msgs.iterrows():
            msg = safe_str(row.get("Message"))
            flag = safe_str(row.get("Flag")).lower()
            low = msg.lower()
            if not any(
                k in low or k in flag
                for k in ("safety car", "virtual safety", "red flag", "sc", "vsc")
            ):
                # Prefer explicit deployed/ending phrasing.
                if not any(k in low for k in ("deployed", "ending", "ended", "in this lap")):
                    continue
            if "safety car" not in low and "virtual safety" not in low and "red flag" not in low and flag not in {
                "sc",
                "vsc",
                "red",
            }:
                continue
            t = timedelta_to_str(row.get("Time"))
            docs.append(
                _make_doc(
                    bundle,
                    "turning_point",
                    f"{bundle.year} {bundle.event_name} {bundle.session_name} — race control turning point",
                    (
                        f"Turning point at session time {t or 'unknown'}: {msg}. "
                        f"Neutralizations and red flags reshuffle strategy windows and pit risk."
                    ),
                )
            )
            if len(docs) >= MAX_TURNING_POINTS_PER_SESSION:
                break

    # Big undercut-style position jumps after pits.
    if len(docs) < MAX_TURNING_POINTS_PER_SESSION:
        for driver in laps["Driver"].dropna().unique():
            dlaps = laps.pick_drivers(driver).sort_values("LapNumber")
            pit_idx = dlaps.index[dlaps["PitInTime"].notna()]
            for idx in pit_idx:
                loc = dlaps.index.get_loc(idx)
                if not isinstance(loc, int) or loc + 2 >= len(dlaps):
                    continue
                before = dlaps.iloc[loc].get("Position")
                after = dlaps.iloc[min(loc + 2, len(dlaps) - 1)].get("Position")
                if pd.isna(before) or pd.isna(after):
                    continue
                gain = float(before) - float(after)
                if gain >= 3:
                    lap_no = int(dlaps.iloc[loc].get("LapNumber"))
                    docs.append(
                        _make_doc(
                            bundle,
                            "turning_point",
                            f"{bundle.year} {bundle.event_name} {bundle.session_name} — pit gain for {driver}",
                            (
                                f"Turning point: {driver} pitted around lap {lap_no} and improved from "
                                f"P{int(before)} to P{int(after)} within two laps. "
                                f"This is consistent with an undercut or free pit under neutralization."
                            ),
                            driver=driver,
                            lap=lap_no,
                        )
                    )
                if len(docs) >= MAX_TURNING_POINTS_PER_SESSION:
                    break
            if len(docs) >= MAX_TURNING_POINTS_PER_SESSION:
                break

    return docs[:MAX_TURNING_POINTS_PER_SESSION]


def docs_for_session(bundle: SessionBundle) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    docs.extend(race_control_docs(bundle))
    docs.extend(lap_summary_docs(bundle))
    docs.extend(stint_summary_docs(bundle))
    docs.extend(strategy_summary_docs(bundle))
    docs.extend(incident_summary_docs(bundle))
    docs.extend(comparison_docs(bundle))
    docs.extend(turning_point_docs(bundle))
    return docs

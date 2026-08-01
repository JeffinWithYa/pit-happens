from __future__ import annotations

from typing import Any

from rag.utils import doc_id


TRACKS: list[dict[str, str]] = [
    {
        "name": "Bahrain International Circuit",
        "location": "Sakhir, Bahrain",
        "text": (
            "Desert venue with long straights, heavy traction zones out of slow corners, "
            "and high tyre stress especially on the rear axle. Sand on track and large "
            "day-night temperature swings often affect grip. Overtaking is aided by DRS "
            "on the main straight; soft-compound degradation can force multi-stop strategies."
        ),
    },
    {
        "name": "Jeddah Corniche Circuit",
        "location": "Jeddah, Saudi Arabia",
        "text": (
            "Very fast street circuit with flowing high-speed corners and walls close to "
            "the track. Commitment and precision matter more than mechanical grip. Safety "
            "car probability is historically elevated. Low downforce setups are common; "
            "small mistakes are heavily punished."
        ),
    },
    {
        "name": "Albert Park Circuit",
        "location": "Melbourne, Australia",
        "text": (
            "Semi-permanent park circuit with a mix of slow and medium-speed corners. "
            "Surface evolution across the weekend is significant. Recent layout changes "
            "improved overtaking into medium-speed braking zones. Tyre warm-up and traction "
            "out of slower corners are key."
        ),
    },
    {
        "name": "Suzuka Circuit",
        "location": "Suzuka, Japan",
        "text": (
            "Figure-eight layout famous for the high-speed S-curves. High downforce and "
            "stable aero platform are rewarded. Overtaking is difficult outside the pits "
            "and hairpin; race strategy and qualifying position are critical. Weather can "
            "change quickly in the region."
        ),
    },
    {
        "name": "Shanghai International Circuit",
        "location": "Shanghai, China",
        "text": (
            "Long winding Turn 1–2 complex and a lengthy back straight create a traction "
            "vs top-speed compromise. Rear tyre wear can be severe. DRS and slipstream "
            "matter on the long straight; undercut potential is often high."
        ),
    },
    {
        "name": "Miami International Autodrome",
        "location": "Miami, USA",
        "text": (
            "Purpose-built hard-walled circuit around Hard Rock Stadium. Heat, bumpy "
            "asphalt, and mixed corner speeds challenge cooling and tyre management. "
            "Overtaking opportunities concentrate around the main DRS zones."
        ),
    },
    {
        "name": "Imola (Autodromo Enzo e Dino Ferrari)",
        "location": "Imola, Italy",
        "text": (
            "Old-school narrow layout with limited run-off. Overtaking is difficult; "
            "track position is precious. Medium/high-speed corner stability and precise "
            "kerb usage are important. Safety cars can scramble otherwise static races."
        ),
    },
    {
        "name": "Circuit de Monaco",
        "location": "Monte Carlo, Monaco",
        "text": (
            "Slowest street circuit on the calendar. Qualifying is disproportionately "
            "important; overtaking is extremely hard. Soft walls, elevation changes, and "
            "low-speed traction define the challenge. Strategy often revolves around "
            "undercuts if a gap appears, or safety-car timing."
        ),
    },
    {
        "name": "Circuit Gilles Villeneuve",
        "location": "Montreal, Canada",
        "text": (
            "Stop-go layout with long straights and heavy braking zones, including the "
            "Wall of Champions. Brake wear and traction out of chicanes are central. "
            "DRS trains and late-braking moves are common; walls punish small errors."
        ),
    },
    {
        "name": "Circuit de Barcelona-Catalunya",
        "location": "Barcelona, Spain",
        "text": (
            "Classic aero-evaluation track with a long high-speed corner complex. "
            "Front-end precision and sustained downforce matter. Overtaking improved with "
            "layout tweaks but still rewards strong race pace and tyre life over raw "
            "qualifying heroics alone."
        ),
    },
    {
        "name": "Red Bull Ring",
        "location": "Spielberg, Austria",
        "text": (
            "Short, steeply undulating track with three strong overtaking zones into "
            "Turns 3, 4 and 7. Power unit performance and strong traction matter. "
            "Weather can be volatile. Races are often processional until DRS trains or "
            "strategy offsets break the order."
        ),
    },
    {
        "name": "Silverstone Circuit",
        "location": "Silverstone, United Kingdom",
        "text": (
            "Very high-speed flowing corners (Maggots-Becketts-Chapel) demand aero "
            "efficiency and confidence. Wind and changeable British weather frequently "
            "affect grip. Tyre stress is high; safety-car timing can decide strategy."
        ),
    },
    {
        "name": "Hungaroring",
        "location": "Budapest, Hungary",
        "text": (
            "Tight, twisty 'street circuit in the dirt' where downforce and tyre prep "
            "are vital. Overtaking is difficult; undercuts and track position dominate. "
            "Hot temperatures amplify degradation, especially on soft compounds."
        ),
    },
    {
        "name": "Spa-Francorchamps",
        "location": "Stavelot, Belgium",
        "text": (
            "Longest modern F1 circuit with elevation, Eau Rouge/Raidillon, and frequent "
            "weather splits across the lap. Setup is a downforce compromise. Safety cars "
            "and wet/dry transitions often decide races; intermediate timing is critical."
        ),
    },
    {
        "name": "Zandvoort",
        "location": "Zandvoort, Netherlands",
        "text": (
            "Narrow banked seaside circuit. Banking aids grip but overtaking remains "
            "hard outside strategy. Wind and sand can affect balance. High tyre sidewall "
            "loads and precise entry speeds characterize the challenge."
        ),
    },
    {
        "name": "Monza",
        "location": "Monza, Italy",
        "text": (
            "Temple of Speed: long straights and heavy braking chicanes. Lowest downforce "
            "packages of the year. Slipstream and DRS are decisive; tyre preparation into "
            "braking zones and straight-line efficiency dominate."
        ),
    },
    {
        "name": "Baku City Circuit",
        "location": "Baku, Azerbaijan",
        "text": (
            "Longest street-circuit straight plus a tight castle section. High overtaking "
            "potential and high incident risk. Tyre temperature management between slow "
            "and ultra-fast sections is difficult; safety cars are common."
        ),
    },
    {
        "name": "Marina Bay Street Circuit",
        "location": "Singapore",
        "text": (
            "Night street race with heat, humidity, and relentless low-speed corners. "
            "Physical and braking demands are extreme. Safety cars are frequent; strategy "
            "flexibility and traffic management often outweigh pure one-lap pace."
        ),
    },
    {
        "name": "Circuit of the Americas",
        "location": "Austin, USA",
        "text": (
            "Inspired by classic European corners with a steep run into Turn 1. Mixed "
            "corner profile rewards a well-balanced car. Overtaking is possible into T1 "
            "and the stadium section; wind can unsettle high-speed balance."
        ),
    },
    {
        "name": "Autódromo Hermanos Rodríguez",
        "location": "Mexico City, Mexico",
        "text": (
            "High altitude reduces aero downforce and cooling capacity. Cars run high "
            "downforce wings that still produce less load than at sea level. Stadium "
            "section and long straight create an overtaking/DRS trade-off; tyre overheating "
            "can appear despite thinner air."
        ),
    },
    {
        "name": "Interlagos (Autódromo José Carlos Pace)",
        "location": "São Paulo, Brazil",
        "text": (
            "Anti-clockwise, bumpy, and often wet. Strong overtaking into Senna S and "
            "high strategy volatility. Intermediate/wet calls are historically decisive. "
            "Altitude is moderate; mechanical grip and adaptability matter."
        ),
    },
    {
        "name": "Las Vegas Strip Circuit",
        "location": "Las Vegas, USA",
        "text": (
            "Night street race with very long straights and cool desert temperatures. "
            "Low tyre temperatures can hinder grip, especially on softs early in stints. "
            "Top speed and battery deployment are crucial; walls punish over-optimism."
        ),
    },
    {
        "name": "Losail International Circuit",
        "location": "Lusail, Qatar",
        "text": (
            "Fast, flowing desert circuit with sustained lateral loads that can punish "
            "tyres and drivers. Night race conditions help cooling, but track evolution "
            "and wind remain factors. Abrasion and kerb strikes can accelerate degradation."
        ),
    },
    {
        "name": "Yas Marina Circuit",
        "location": "Abu Dhabi, UAE",
        "text": (
            "Twilight/night season finale venue. Mix of long straights and tighter "
            "technical sections after layout revisions improved racing. Tyre management "
            "and undercut threat around mid-race often decide podium fights."
        ),
    },
]


REGULATION_DOCS: list[dict[str, str]] = [
    {
        "title": "F1 points system (current era overview)",
        "text": (
            "In modern Formula 1, the top ten classified race finishers score "
            "25-18-15-12-10-8-6-4-2-1 points. An additional point is awarded for the "
            "fastest lap if that driver finishes inside the top ten. Sprint weekends "
            "award a smaller points scale to the top eight sprint finishers "
            "(typically 8-7-6-5-4-3-2-1). Drivers must be classified under sporting "
            "regulations (generally completing the required race distance percentage) "
            "to score."
        ),
    },
    {
        "title": "Tyre rules and compound usage",
        "text": (
            "Pirelli supplies dry compounds labeled Soft (C softest available that "
            "weekend), Medium, and Hard, plus Intermediate and Full Wet weather tyres. "
            "In dry races, drivers who reach Q3 have historically had parc-ferme tyre "
            "constraints tied to qualifying; dry races generally require using at least "
            "two different dry compounds unless wet tyres are used. Teams manage "
            "stints around cliff degradation, track temperature, and pit-loss time."
        ),
    },
    {
        "title": "Safety Car, VSC, and red flags",
        "text": (
            "A Safety Car neutralizes the race at reduced speed with limited overtaking. "
            "The Virtual Safety Car (VSC) enforces a minimum time delta without bunching "
            "the field as tightly. Red flags stop the session; restart procedures depend "
            "on whether a standing or rolling restart is used. Pit lane may be closed or "
            "restricted during some safety periods. Neutralizations often create 'free "
            "stop' opportunities if a driver can pit while others are slowed."
        ),
    },
    {
        "title": "DRS (Drag Reduction System)",
        "text": (
            "DRS opens the rear wing flap in designated zones when a driver is within "
            "one second of the car ahead at the detection point, reducing drag to aid "
            "overtaking. DRS is disabled in certain conditions (for example early race "
            "laps after the start/restart, or during wet/safety conditions). It is a "
            "passing aid, not a guarantee—battery deployment, slipstream, and braking "
            "performance still decide the move."
        ),
    },
    {
        "title": "Penalties and stewarding basics",
        "text": (
            "Common penalties include time penalties (5s/10s), drive-throughs, stop-go "
            "penalties, grid drops, and reprimands. Causes include causing a collision, "
            "track-limits violations, unsafe releases, ignoring yellow flags, or "
            "speeding in the pit lane. Lap times can be deleted for track limits. "
            "Stewards issue decisions via race control messaging; some investigations "
            "are resolved after the race and can revise provisional classifications."
        ),
    },
    {
        "title": "Parc fermé and setup restrictions",
        "text": (
            "After qualifying, cars enter parc fermé conditions that heavily restrict "
            "setup changes before the race. Major changes can force a pit-lane start. "
            "This links qualifying performance to race competitiveness: teams must "
            "qualify with a race-capable balance. Exceptions exist for safety-related "
            "changes under steward approval."
        ),
    },
    {
        "title": "Sprint weekend format (2024+)",
        "text": (
            "Sprint weekends compress the schedule: Sprint Qualifying sets the sprint "
            "grid; the Sprint awards points but does not set Sunday's grid; separate "
            "Qualifying sets the Grand Prix grid. Because parc fermé and tyre "
            "allocations differ from a conventional weekend, teams balance risk across "
            "sprint pace and Sunday race tyre life."
        ),
    },
    {
        "title": "Power unit and allocation constraints",
        "text": (
            "Each driver has a limited allocation of power-unit elements and gearbox "
            "components across the season. Exceeding allocations typically incurs grid "
            "penalties. Teams may take strategic penalties at tracks where overtaking "
            "is easier. ERS deployment strategy (battery charge/discharge) also shapes "
            "defensive and attacking performance in DRS zones."
        ),
    },
]


def build_static_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for reg in REGULATION_DOCS:
        title = reg["title"]
        text = f"{title}\n\n{reg['text']}"
        docs.append(
            {
                "id": doc_id("regulation", title),
                "text": text,
                "metadata": {
                    "doc_type": "regulation",
                    "title": title,
                    "year": 0,
                    "event": "general",
                    "session_type": "none",
                },
            }
        )
    for track in TRACKS:
        title = f"Track guide — {track['name']}"
        text = (
            f"{title}\nLocation: {track['location']}\n\n{track['text']}"
        )
        docs.append(
            {
                "id": doc_id("track", track["name"]),
                "text": text,
                "metadata": {
                    "doc_type": "track_info",
                    "title": title,
                    "location": track["location"],
                    "track": track["name"],
                    "year": 0,
                    "event": "general",
                    "session_type": "none",
                },
            }
        )
    return docs

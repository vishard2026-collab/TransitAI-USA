# TransitAI USA — Passenger Tracker V4

An unofficial college prototype using published MARTA GTFS schedules and GTFS-Realtime vehicle locations.

## Install on macOS

```bash
cd TransitAI_Passenger_V4
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Features
- Waiting for my bus: choose public route number and boarding stop; choose a reported vehicle on a scheduled trip serving that stop; see its reported GPS location, estimated nearby stop, approximate stop count and official ETA if available.
- Already on my bus: select bus and destination; see its last reported location and approximate remaining stops.
- Supports route 140, 185, 85 and other routes present in MARTA's published schedule.

## Important
- Internet required. Feeds may be unavailable or change format.
- GPS is reported intermittently; the marker is NOT guaranteed to be the vehicle's exact current location.
- The nearby-stop and stop count logic is a prototype heuristic. Loops, trip changes and feed mismatches can produce wrong results. Do not use as your sole source for important travel decisions.
- If official arrival trip updates are absent, the app does not invent an ETA.
- This prototype has not been verified against live feeds in this environment.

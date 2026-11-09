
import io
import math
import zipfile
from datetime import datetime, timezone

import folium
import pandas as pd
import requests
import streamlit as st
from google.transit import gtfs_realtime_pb2
from streamlit_folium import st_folium


# ============================================
# TRANSITAI USA - MARTA BUS AND TRAIN TRACKER
# ============================================

STATIC_URL = (
    "https://itsmarta.com/google_transit_feed/"
    "google_transit.zip"
)

VEHICLE_URL = (
    "https://gtfs-rt.itsmarta.com/"
    "TMGTFSRealTimeWebService/vehicle/vehiclepositions.pb"
)

TRIP_URL = (
    "https://gtfs-rt.itsmarta.com/"
    "TMGTFSRealTimeWebService/tripupdate/tripupdates.pb"
)

HEADERS = {
    "User-Agent": "TransitAI-USA-Student-Project/1.2"
}


st.set_page_config(
    page_title="TransitAI USA",
    page_icon="🚌",
    layout="wide"
)

st.title("🚌🚆 TransitAI USA")
st.write("Track MARTA buses and trains in Atlanta.")

st.caption(
    "Unofficial student project using published "
    "MARTA schedules and real-time data."
)


# ============================================
# LOAD MARTA SCHEDULE DATA
# ============================================

@st.cache_data(ttl=86400, show_spinner=False)
def load_static_data():

    response = requests.get(
        STATIC_URL,
        headers=HEADERS,
        timeout=60
    )
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:

        def read_file(filename):
            with z.open(filename) as file:
                return pd.read_csv(
                    file,
                    dtype=str
                ).fillna("")

        routes = read_file("routes.txt")
        trips = read_file("trips.txt")
        stops = read_file("stops.txt")
        stop_times = read_file("stop_times.txt")

    return routes, trips, stops, stop_times


# Cache downloaded bytes, not protobuf objects
@st.cache_data(ttl=25, show_spinner=False)
def download_feed(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=25
    )
    response.raise_for_status()

    return response.content


def read_feed(url):

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(download_feed(url))

    return feed


# ============================================
# HELPER FUNCTIONS
# ============================================

def distance_miles(lat1, lon1, lat2, lon2):

    lat1 = math.radians(float(lat1))
    lat2 = math.radians(float(lat2))

    dlat = lat2 - lat1

    dlon = math.radians(
        float(lon2) - float(lon1)
    )

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 3958.7613 * 2 * math.asin(
        min(1, math.sqrt(a))
    )


def stop_label(stop_id, lookup):

    stop = lookup.get(str(stop_id))

    if stop is None:
        return f"Stop {stop_id}"

    return (
        f"{stop['stop_name']} "
        f"(Stop {stop_id})"
    )


def route_sort_key(name):

    first = name.split(" - ")[0]

    if first.isdigit():
        return (0, int(first))

    return (1, name)


def route_display(row, service_type):

    short_name = str(
        row.get("route_short_name", "")
    ).strip()

    long_name = str(
        row.get("route_long_name", "")
    ).strip()

    if service_type == "🚌 MARTA Bus":

        if short_name and long_name:
            return f"{short_name} - {long_name}"

        return short_name or long_name

    return long_name or short_name


# ============================================
# LOAD MARTA SCHEDULES
# ============================================

try:

    with st.spinner("Loading MARTA schedules..."):

        routes, trips, stops, stop_times = (
            load_static_data()
        )

except Exception as error:

    st.error(
        f"Could not load MARTA schedules: {error}"
    )
    st.stop()


# ============================================
# CHOOSE BUS OR TRAIN
# ============================================

service = st.radio(
    "1. Choose transportation",
    ["🚌 MARTA Bus", "🚆 MARTA Train"],
    horizontal=True
)

if service == "🚌 MARTA Bus":
    route_type = "3"
else:
    route_type = "1"


available_routes = routes[
    routes["route_type"] == route_type
].copy()

if available_routes.empty:

    st.warning(
        "No routes found for this transportation type."
    )
    st.stop()


# ============================================
# SELECT BUS NUMBER OR TRAIN LINE
# ============================================

available_routes["display"] = (
    available_routes.apply(
        lambda row: route_display(row, service),
        axis=1
    )
)

route_choices = sorted(
    available_routes["display"].unique(),
    key=route_sort_key
)

# Put familiar bus routes first
if service == "🚌 MARTA Bus":

    favorites = []

    for number in ["140", "185", "85"]:

        for choice in route_choices:

            if choice.split(" - ")[0] == number:
                favorites.append(choice)

    route_choices = favorites + [
        choice for choice in route_choices
        if choice not in favorites
    ]


selected_route = st.selectbox(
    "2. Select bus number or train line",
    route_choices
)

selected_route_ids = set(
    available_routes.loc[
        available_routes["display"] == selected_route,
        "route_id"
    ]
)


# ============================================
# GET TRIPS FOR SELECTED ROUTE
# ============================================

route_trips = trips[
    trips["route_id"].isin(selected_route_ids)
].copy()

if route_trips.empty:

    st.warning(
        "No scheduled trips found for this route."
    )
    st.stop()


# ============================================
# CHOOSE DIRECTION BY DESTINATION NAME
# ============================================

def direction_name(direction_id):

    direction_trips = route_trips[
        route_trips["direction_id"] == direction_id
    ]

    if "trip_headsign" in direction_trips.columns:

        headsigns = direction_trips[
            "trip_headsign"
        ].dropna()

        headsigns = headsigns[
            headsigns.str.strip() != ""
        ]

        if not headsigns.empty:

            destination = (
                headsigns.value_counts().index[0]
            )

            return f"Toward {destination}"

    return f"Direction {direction_id}"


directions = sorted(
    route_trips["direction_id"].unique()
)

direction = st.selectbox(
    "3. Where are you going?",
    directions,
    format_func=direction_name
)

route_trips = route_trips[
    route_trips["direction_id"] == direction
].copy()

trip_ids = set(
    route_trips["trip_id"]
)


# ============================================
# GET STOPS FOR SELECTED ROUTE AND DIRECTION
# ============================================

route_times = stop_times[
    stop_times["trip_id"].isin(trip_ids)
].copy()

route_times["seq"] = pd.to_numeric(
    route_times["stop_sequence"],
    errors="coerce"
)

route_times = route_times.dropna(
    subset=["seq"]
)

stop_lookup = (
    stops.drop_duplicates("stop_id")
    .set_index("stop_id")
    .to_dict("index")
)

trip_stops = {
    trip_id: group.sort_values("seq")
    for trip_id, group in route_times.groupby("trip_id")
}

route_stop_ids = set(
    route_times["stop_id"]
)

route_stops = stops[
    stops["stop_id"].isin(route_stop_ids)
].drop_duplicates("stop_id")

if route_stops.empty:

    st.warning(
        "No stops found for this route and direction."
    )
    st.stop()


# ============================================
# SHOW STOPS ON SELECTED ROUTE
# ============================================

st.subheader(
    f"🚏 Stops on {selected_route}"
)

trip_lengths = (
    route_times.groupby("trip_id")
    .size()
    .sort_values(ascending=False)
)

representative_trip = trip_lengths.index[0]

representative_stops = (
    trip_stops[representative_trip]
    .drop_duplicates("stop_id")
    .sort_values("seq")
)

with st.expander(
    "View scheduled stops in order",
    expanded=True
):

    for number, (_, row) in enumerate(
        representative_stops.iterrows(),
        start=1
    ):

        st.write(
            f"{number}. "
            f"{stop_label(row['stop_id'], stop_lookup)}"
        )

st.caption(
    "This is one representative scheduled trip. "
    "Some trips may use different stop patterns."
)


# ============================================
# PASSENGER MODE
# ============================================

mode = st.radio(
    "4. What are you doing?",
    [
        "Waiting for my bus/train",
        "Already riding"
    ],
    horizontal=True
)

if st.button("🔄 Refresh live data"):

    download_feed.clear()
    st.rerun()


# ============================================
# LIVE GPS VEHICLE POSITIONS
# ============================================

try:

    vehicle_feed = read_feed(VEHICLE_URL)

except Exception as error:

    st.error(
        f"Live GPS feed unavailable: {error}"
    )
    st.stop()


now = int(
    datetime.now(timezone.utc).timestamp()
)

vehicles = []

for entity in vehicle_feed.entity:

    if not entity.HasField("vehicle"):
        continue

    vehicle = entity.vehicle

    if not vehicle.HasField("position"):
        continue

    if not vehicle.HasField("trip"):
        continue

    trip_id = str(
        vehicle.trip.trip_id
    )

    # Direction is matched using trip_id
    if trip_id not in trip_ids:
        continue

    latitude = float(
        vehicle.position.latitude
    )

    longitude = float(
        vehicle.position.longitude
    )

    if not (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        continue

    timestamp = int(
        vehicle.timestamp
        or vehicle_feed.header.timestamp
        or 0
    )

    vehicles.append({
        "id": str(
            vehicle.vehicle.id or entity.id
        ),
        "trip": trip_id,
        "lat": latitude,
        "lon": longitude,
        "age": now - timestamp
    })


st.write(
    f"**Reported vehicles for this direction: "
    f"{len(vehicles)}**"
)


# ============================================
# OFFICIAL ARRIVAL PREDICTIONS
# ============================================

predictions = {}

try:

    trip_feed = read_feed(TRIP_URL)

    for entity in trip_feed.entity:

        if not entity.HasField("trip_update"):
            continue

        update = entity.trip_update

        trip_id = str(
            update.trip.trip_id
        )

        if trip_id not in trip_ids:
            continue

        for item in update.stop_time_update:

            if item.HasField("arrival"):
                event = item.arrival

            elif item.HasField("departure"):
                event = item.departure

            else:
                continue

            if event.HasField("time"):

                predictions[
                    (trip_id, str(item.stop_id))
                ] = int(event.time)

except Exception:

    st.info(
        "Official arrival predictions are unavailable."
    )


# ============================================
# ESTIMATE NEAREST SCHEDULED STOP
# ============================================

def get_progress(vehicle):

    ordered = trip_stops.get(
        vehicle["trip"]
    )

    if ordered is None or ordered.empty:
        return None, None, None

    candidates = []

    for _, row in ordered.iterrows():

        sid = str(
            row["stop_id"]
        )

        stop = stop_lookup.get(sid)

        if stop is None:
            continue

        try:

            distance = distance_miles(
                vehicle["lat"],
                vehicle["lon"],
                stop["stop_lat"],
                stop["stop_lon"]
            )

            candidates.append(
                (
                    distance,
                    float(row["seq"]),
                    sid
                )
            )

        except (ValueError, TypeError):
            continue

    if not candidates:
        return None, None, None

    nearest = min(candidates)

    return (
        nearest[1],
        nearest[2],
        ordered
    )


def remaining_stops(ordered, current, target):

    return int(
        (
            (ordered["seq"] > current)
            & (ordered["seq"] <= target)
        ).sum()
    )


# ============================================
# WAITING FOR MY BUS OR TRAIN
# ============================================

if mode == "Waiting for my bus/train":

    selected_stop_id = st.selectbox(
        "5. Choose your waiting stop or station",
        route_stops["stop_id"].tolist(),
        format_func=lambda sid: stop_label(
            sid, stop_lookup
        )
    )

    target = stop_lookup[
        selected_stop_id
    ]

    matching = []

    for vehicle in vehicles:

        current_seq, near_id, ordered = (
            get_progress(vehicle)
        )

        if ordered is None:
            continue

        rows = ordered[
            ordered["stop_id"] == selected_stop_id
        ]

        if rows.empty:
            continue

        target_seq = float(
            rows.iloc[0]["seq"]
        )

        remaining = remaining_stops(
            ordered,
            current_seq,
            target_seq
        )

        distance = distance_miles(
            vehicle["lat"],
            vehicle["lon"],
            target["stop_lat"],
            target["stop_lon"]
        )

        matching.append({
            **vehicle,
            "near_id": near_id,
            "remaining": remaining,
            "distance": distance,
            "target_seq": target_seq,
            "current_seq": current_seq
        })

    matching.sort(
        key=lambda item: item["distance"]
    )

    if not matching:

        st.warning(
            "No matching live vehicles are currently "
            "reported for this stop and direction."
        )

        selected = None

    else:

        selected_index = st.selectbox(
            "6. Choose a reported vehicle",
            range(len(matching)),
            format_func=lambda i: (
                f"Vehicle {matching[i]['id']} "
                f"- {matching[i]['distance']:.1f} "
                f"miles from stop"
            )
        )

        selected = matching[
            selected_index
        ]

        st.write(
            "**Last reported near:** "
            + stop_label(
                selected["near_id"],
                stop_lookup
            )
        )

        st.metric(
            "Approximate stops remaining",
            selected["remaining"]
        )

        if (
            selected["current_seq"]
            > selected["target_seq"]
        ):

            st.warning(
                "This vehicle may already have passed "
                "your selected stop."
            )

    target_location = [
        float(target["stop_lat"]),
        float(target["stop_lon"])
    ]


# ============================================
# ALREADY RIDING MODE
# ============================================

else:

    if not vehicles:

        st.warning(
            "No live vehicles are currently reported "
            "for this route and direction."
        )

        selected = None

        selected_stop_id = (
            representative_stops.iloc[-1]["stop_id"]
        )

        target = stop_lookup[
            selected_stop_id
        ]

    else:

        selected_index = st.selectbox(
            "5. Select your vehicle",
            range(len(vehicles)),
            format_func=lambda i: (
                f"Vehicle {vehicles[i]['id']}"
            )
        )

        selected = vehicles[
            selected_index
        ]

        current_seq, near_id, ordered = (
            get_progress(selected)
        )

        if ordered is None:

            st.warning(
                "No matching scheduled trip was found."
            )

            selected = None
            ordered = representative_stops

        selected_stop_id = st.selectbox(
            "6. Choose your destination",
            ordered["stop_id"].tolist(),
            format_func=lambda sid: stop_label(
                sid, stop_lookup
            )
        )

        target = stop_lookup[
            selected_stop_id
        ]

        if selected is not None:

            target_seq = float(
                ordered.loc[
                    ordered["stop_id"] == selected_stop_id,
                    "seq"
                ].iloc[0]
            )

            remaining = remaining_stops(
                ordered,
                current_seq,
                target_seq
            )

            st.write(
                "**Last reported near:** "
                + stop_label(
                    near_id,
                    stop_lookup
                )
            )

            st.metric(
                "Approximate stops remaining",
                remaining
            )

            if target_seq < current_seq:

                st.warning(
                    "Your destination may already "
                    "be behind this vehicle."
                )

    target_location = [
        float(target["stop_lat"]),
        float(target["stop_lon"])
    ]


# ============================================
# ARRIVAL ESTIMATE
# ============================================

if selected is not None:

    st.write(
        f"**GPS report age:** "
        f"{selected['age']} seconds"
    )

    if (
        selected["age"] > 120
        or selected["age"] < -60
    ):

        st.warning(
            "This GPS position may be outdated."
        )

    eta = predictions.get(
        (
            selected["trip"],
            selected_stop_id
        )
    )

    if eta is not None and eta >= now - 60:

        minutes = max(
            0,
            math.ceil((eta - now) / 60)
        )

        st.metric(
            "Official predicted arrival",
            f"{minutes} minutes"
        )

    else:

        st.info(
            "No matching official arrival prediction "
            "is currently available."
        )


# ============================================
# INTERACTIVE MARTA MAP
# ============================================

st.subheader("🗺️ MARTA Tracking Map")

transit_map = folium.Map(
    location=target_location,
    zoom_start=13,
    tiles="OpenStreetMap"
)


# Display stops from the representative trip
for _, row in representative_stops.iterrows():

    sid = str(
        row["stop_id"]
    )

    stop = stop_lookup.get(sid)

    if stop is None:
        continue

    try:

        folium.CircleMarker(
            location=[
                float(stop["stop_lat"]),
                float(stop["stop_lon"])
            ],
            radius=4,
            color="orange",
            fill=True,
            fill_opacity=0.8,
            tooltip=stop["stop_name"]
        ).add_to(transit_map)

    except (ValueError, TypeError):
        continue


# Selected stop or station
folium.Marker(
    location=target_location,
    tooltip=target["stop_name"],
    popup=target["stop_name"],
    icon=folium.Icon(
        color="green",
        icon="flag"
    )
).add_to(transit_map)


# Add reported vehicle locations
for vehicle in vehicles:

    folium.Marker(
        location=[
            vehicle["lat"],
            vehicle["lon"]
        ],
        tooltip=f"Vehicle {vehicle['id']}",
        popup=(
            f"Route: {selected_route}<br>"
            f"Vehicle: {vehicle['id']}<br>"
            f"GPS age: {vehicle['age']} seconds"
        ),
        icon=folium.Icon(
            color=(
                "blue"
                if (
                    selected is not None
                    and vehicle["id"] == selected["id"]
                )
                else "gray"
            ),
            icon="info-sign"
        )
    ).add_to(transit_map)


if selected is not None:

    transit_map.fit_bounds([
        [selected["lat"], selected["lon"]],
        target_location
    ])


st_folium(
    transit_map,
    height=520,
    width=None,
    returned_objects=[]
)


st.caption(
    "TransitAI USA is an unofficial student project. "
    "GPS positions may be delayed. "
    "Nearby-stop and remaining-stop counts are "
    "approximate estimates. Train GPS positions "
    "appear only when included in the published feed. "
    "Not affiliated with MARTA."
)


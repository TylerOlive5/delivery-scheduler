import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import os

# Constants
START_LOCATIONS = {
    "22064 - Duncan Warehouse - 1 Tungsten Way, Duncan SC 29334": "1 Tungsten Way, Duncan SC 29334",
    "22060 - Florence Warehouse - 4511 Helton Dr Florence AL, 35630": "4511 Helton Dr Florence AL, 35630",
    "1000 Example Blvd, Charlotte, NC": "1000 Example Blvd, Charlotte, NC",
    "500 Distribution Dr, Atlanta, GA": "500 Distribution Dr, Atlanta, GA"
}
STOP_DURATION = timedelta(minutes=15)  # Updated from 45 to 15 minutes
MEAL_BREAK = timedelta(hours=2)

# Round to nearest 15 minutes
def round_to_nearest_15(dt):
    discard = timedelta(minutes=dt.minute % 15,
                        seconds=dt.second,
                        microseconds=dt.microsecond)
    dt -= discard
    if discard >= timedelta(minutes=7.5):
        dt += timedelta(minutes=15)
    return dt

# Estimate drive time using Google Maps API (required)
def estimate_drive_time(from_address, to_address):
    import googlemaps
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        st.error("Google Maps API key not found. Please set the GOOGLE_MAPS_API_KEY environment variable.")
        st.stop()
    gmaps = googlemaps.Client(key=api_key)
    directions = gmaps.directions(from_address, to_address, mode="driving")
    seconds = directions[0]['legs'][0]['duration']['value']
    base_drive_time = timedelta(seconds=seconds)
    buffer_time = base_drive_time * 0.3  # 30% slow truck buffer
    total_drive_time = base_drive_time + buffer_time
    return base_drive_time, total_drive_time

# Optimize stop order using Google Maps API
def optimize_stop_order(origin, stop_addresses):
    import googlemaps
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        st.error("Google Maps API key not found. Please set the GOOGLE_MAPS_API_KEY environment variable.")
        st.stop()
    gmaps = googlemaps.Client(key=api_key)
    directions_result = gmaps.directions(
        origin,
        origin,
        mode="driving",
        waypoints=["optimize:true"] + stop_addresses,
        optimize_waypoints=True
    )
    order = directions_result[0]['waypoint_order']
    return order

# Streamlit UI
st.title("Delivery Route Scheduler")

route_name = st.text_input("Route Name", "TNT9999")
departure_time = st.time_input("Departure Time", datetime.strptime("08:00", "%H:%M").time())
selected_origin_label = st.selectbox("Start Location", list(START_LOCATIONS.keys()))
origin = START_LOCATIONS[selected_origin_label]

st.markdown("### Enter Stops (one per line, format: LOC#, Address)")
stops_input = st.text_area(
    "Stops Input",
    placeholder="Drop locations and address here in the format: LOC#, Address"
)

if st.button("Generate Schedule"):
    # Parse input stops
    stops = []
    addresses = []
    for line in stops_input.strip().splitlines():
        if line.strip():
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                loc, addr = parts
                stops.append({"Loc #": loc.strip(), "Address": addr.strip()})
                addresses.append(addr.strip())

    # Optimize stop order
    order = optimize_stop_order(origin, addresses)
    ordered_stops = [stops[i] for i in order]

    # Initialize schedule
    departure_datetime = datetime.combine(datetime.today(), departure_time)
    current_time = departure_datetime
    current_location = origin
    schedule = []

    # Generate schedule
    for stop in ordered_stops:
        base_drive_time, buffered_drive_time = estimate_drive_time(current_location, stop['Address'])
        arrival_time = round_to_nearest_15(current_time + base_drive_time)
        max_arrival_time = round_to_nearest_15(current_time + buffered_drive_time)
        schedule.append({
            "Route": route_name,
            "Loc #": stop['Loc #'],
            "Address": stop['Address'],
            "Arrival Time": arrival_time.strftime("%I:%M %p"),
            "Delivery Window": f"{arrival_time.strftime('%I:%M %p')} – {(arrival_time + timedelta(hours=4)).strftime('%I:%M %p')}"
        })
        current_time = max(current_time + STOP_DURATION, max_arrival_time + STOP_DURATION)
        current_location = stop['Address']

    # Add return to origin
    base_return_time, max_return_time = estimate_drive_time(current_location, origin)
    min_return = round_to_nearest_15(current_time + base_return_time + MEAL_BREAK)
    max_return = round_to_nearest_15(current_time + max_return_time + MEAL_BREAK)
    schedule.append({
        "Route": route_name,
        "Loc #": "RETURN",
        "Address": origin,
        "Arrival Time": min_return.strftime("%I:%M %p"),
        "Delivery Window": f"{min_return.strftime('%I:%M %p')} – {max_return.strftime('%I:%M %p')}"
    })

    df = pd.DataFrame(schedule)
    st.write("### Generated Schedule")
    st.dataframe(df)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Schedule")
    output.seek(0)

    st.download_button(
        label="Download Schedule as Excel",
        data=output,
        file_name=f"{route_name}_schedule.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

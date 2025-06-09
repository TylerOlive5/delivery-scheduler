import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# Constants
ORIGIN = "1 Tungsten Way, Duncan, SC"
STOP_DURATION = timedelta(minutes=45)
DRIVE_TOLERANCE = timedelta(minutes=30)
MEAL_BREAK = timedelta(hours=2)

# Realistic drive time estimator

def estimate_drive_time(from_address, to_address):
    from_lower = from_address.lower()
    to_lower = to_address.lower()

    # Specific known routes (adjust these as needed)
    if "duncan" in from_lower and "lilburn" in to_lower:
        return timedelta(hours=2, minutes=20) + DRIVE_TOLERANCE
    elif "lilburn" in from_lower and "east point" in to_lower:
        return timedelta(minutes=35) + DRIVE_TOLERANCE
    elif "east point" in from_lower and "college park" in to_lower:
        return timedelta(minutes=25) + DRIVE_TOLERANCE
    elif "college park" in from_lower and "duncan" in to_lower:
        return timedelta(hours=3, minutes=20) + MEAL_BREAK
    else:
        return timedelta(hours=1) + DRIVE_TOLERANCE

# Streamlit UI
st.title("Delivery Route Scheduler")

route_name = st.text_input("Route Name", "TNT9999")
departure_time = st.time_input("Departure Time", datetime.strptime("08:00", "%H:%M").time())

st.markdown("### Enter Stops (one per line, format: LOC#, Address)")
stops_input = st.text_area("Stops Input", 
"""
FSC3724, 332 Stonewall Jackson Blvd, Orangeburg, SC 29115
FSC2503, 1500 US 17 N, Mt Pleasant, SC 29464
""")

if st.button("Generate Schedule"):
    # Parse input stops
    stops = []
    for line in stops_input.strip().splitlines():
        if line.strip():
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                loc, addr = parts
                stops.append({"Loc #": loc.strip(), "Address": addr.strip()})

    # Initialize schedule
    departure_datetime = datetime.combine(datetime.today(), departure_time)
    current_time = departure_datetime
    current_location = ORIGIN
    schedule = []

    # Generate schedule
    for stop in stops:
        drive_time = estimate_drive_time(current_location, stop['Address'])
        arrival_time = current_time + drive_time
        schedule.append({
            "Route": route_name,
            "Loc #": stop['Loc #'],
            "Address": stop['Address'],
            "Arrival Time": arrival_time.strftime("%I:%M %p"),
            "Delivery Window": f"{arrival_time.strftime('%I:%M %p')} – {(arrival_time + timedelta(hours=4)).strftime('%I:%M %p')}"
        })
        current_time = arrival_time + STOP_DURATION
        current_location = stop['Address']

    # Add return to origin
    return_drive = estimate_drive_time(current_location, ORIGIN)
    return_time = current_time + return_drive + MEAL_BREAK
    schedule.append({
        "Route": route_name,
        "Loc #": "RETURN",
        "Address": ORIGIN,
        "Arrival Time": return_time.strftime("%I:%M %p"),
        "Delivery Window": "Estimated Return w/ Meal Break"
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

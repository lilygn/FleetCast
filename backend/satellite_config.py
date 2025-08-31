import random
import math
from datetime import datetime, timedelta
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv()

# --- Robust CA path resolution (relative to this file) ---
HERE = Path(__file__).resolve().parent                 # .../OrbitalApp/backend
CA_PATH = HERE / "tidb-ca.pem"                         # expects cert at backend/tidb-ca.pem
if not CA_PATH.is_file():
    raise FileNotFoundError(f"TiDB CA not found at: {CA_PATH}")

# --- DB envs ---
TIDB_HOST = os.getenv("TIDB_HOST")
TIDB_PORT = int(os.getenv("TIDB_PORT", "4000"))
TIDB_USER = os.getenv("TIDB_USER")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "satellite_sim")

def get_conn():
    """Single source of truth for DB connections (TLS with CA)."""
    return pymysql.connect(
        host=TIDB_HOST,
        port=TIDB_PORT,
        user=TIDB_USER,
        password=TIDB_PASSWORD,
        database=TIDB_DATABASE,
        ssl={"ca": str(CA_PATH)},          # only 'ca' is needed; PyMySQL verifies cert
        autocommit=True,
        connect_timeout=8,
        cursorclass=pymysql.cursors.DictCursor,
    )

# --- Sim data ---
SATELLITES = [
    {"id": f"SAT-{i}", "orbit_period": random.randint(90, 180), "priority": random.choice([1, 2, 3])}
    for i in range(1, 101)
]
GROUND_STATIONS = [
    {
        "id": f"GS-{i}",
        "location": f"Location-{i}",
        "capacity": random.randint(1, 10),
        "lon": random.randint(-180, 180),
        "lat": random.randint(-60, 60),
    }
    for i in range(1, 8)
]

def simulate_satellite_position(orbit_period, timestamp=None, sat_id=None):
    if timestamp is None:
        timestamp = datetime.utcnow()
    offset = int(sat_id.split("-")[1]) if sat_id else 0
    minutes = timestamp.minute + timestamp.hour * 60 + offset
    angle = (360 * minutes / orbit_period) % 360
    lat = math.sin(math.radians(angle)) * 60
    lon = (angle - 180) % 360 - 180
    return lat, lon

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = map(math.radians, [lat1, lat2])
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

def generate_contact_windows(satellite, ground_stations, timestamp=None):
    if timestamp is None:
        timestamp = datetime.utcnow()
    lat, lon = simulate_satellite_position(satellite["orbit_period"], timestamp, satellite["id"])
    contact_windows = []
    for gs in ground_stations:
        distance = haversine(lat, lon, gs["lat"], gs["lon"])
        print(f"  → Distance to {gs['id']} (lat={gs['lat']}, lon={gs['lon']}): {distance:.2f} km")
        if distance < 5000:
            duration = random.randint(5, 15)
            contact_windows.append({
                "satellite_id": satellite["id"],
                "ground_station_id": gs["id"],
                "start_time": timestamp.isoformat(),
                "end_time": (timestamp + timedelta(minutes=duration)).isoformat(),
                "timestamp": timestamp.isoformat(),
                "distance": float(distance),
                "datavolume": random.randint(100, 1000),
                "priority": satellite["priority"],
                # 'assigned' set later by assign_contacts
            })
    return contact_windows

def generate_all_contact_windows(satellites, ground_stations, timestamp=None):
    if timestamp is None:
        timestamp = datetime.utcnow()
    all_contact_windows = []
    shuffled = satellites.copy()
    random.shuffle(shuffled)
    for satellite in shuffled:
        all_contact_windows.extend(generate_contact_windows(satellite, ground_stations, timestamp))
    return all_contact_windows

def log_contact_to_tidb(contact):
    print(f"Logging contact: {contact}")
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO contact_windows "
                "(satellite_id, ground_station_id, start_time, end_time, timestamp, distance, datavolume, priority, assigned) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    contact["satellite_id"], contact["ground_station_id"],
                    contact["start_time"], contact["end_time"], contact["timestamp"],
                    contact["distance"], contact["datavolume"], contact["priority"],
                    bool(contact.get("assigned", False)),
                ),
            )
    finally:
        conn.close()

def assign_contacts(contact_windows, ground_stations):
    print("--called assign_contacts--")
    sorted_windows = sorted(contact_windows, key=lambda x: (x["priority"], x["start_time"]))
    assignments = []
    gs_schedules = {gs["id"]: [] for gs in ground_stations}
    for contact in sorted_windows:
        gs_id = contact["ground_station_id"]
        start = datetime.fromisoformat(contact["start_time"])
        end = datetime.fromisoformat(contact["end_time"])
        overlaps = sum(
            not (end <= datetime.fromisoformat(existing["end_time"]) or
                 start >= datetime.fromisoformat(existing["start_time"]))
            for existing in gs_schedules[gs_id]
        )
        print(f"{gs_id} overlaps: {overlaps}")
        capacity = next(gs["capacity"] for gs in ground_stations if gs["id"] == gs_id)
        if overlaps < capacity:
            gs_schedules[gs_id].append(contact)
            contact["assigned"] = True
            print(f"Assigned contact {contact['satellite_id']} to ground station {gs_id}")
        else:
            contact["assigned"] = False
            print(f"Could not assign {contact['satellite_id']} to {gs_id}")
        assignments.append(contact)
    return assignments

def simulate_telemetry(contact, orbit_period):
    timestamp = datetime.fromisoformat(contact["timestamp"])
    lat, lon = simulate_satellite_position(orbit_period, timestamp, contact["satellite_id"])
    return {
        "satellite_id": contact["satellite_id"],
        "ground_station_id": contact["ground_station_id"],
        "timestamp": contact["timestamp"],
        "battery_level": round(random.uniform(20.0, 100.0), 2),
        "temperature": round(random.uniform(-40, 85), 1),
        "position_lat": round(lat, 6),
        "position_lon": round(lon, 6),
        "status": random.choice(["OK", "LOW_POWER", "ERROR", "MAINTENANCE"]),
    }

def log_telemetry_to_tidb(telemetry):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO telemetry "
                "(satellite_id, ground_station_id, timestamp, battery_level, temperature, position_lat, position_lon, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    telemetry["satellite_id"], telemetry["ground_station_id"], telemetry["timestamp"],
                    telemetry["battery_level"], telemetry["temperature"],
                    telemetry["position_lat"], telemetry["position_lon"], telemetry["status"],
                ),
            )
    finally:
        conn.close()

def main():
    timestamp = datetime.utcnow()

    # housekeeping: delete expired windows
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM contact_windows WHERE end_time < UTC_TIMESTAMP()")
    finally:
        conn.close()

    all_contact_windows = generate_all_contact_windows(SATELLITES, GROUND_STATIONS, timestamp)
    print(f"Generated {len(all_contact_windows)} contact windows.")

    assigned_contacts = assign_contacts(all_contact_windows, GROUND_STATIONS)
    assigned = [c for c in assigned_contacts if c.get("assigned")]
    print(f"Assigned {len(assigned)} contact windows.")

    for contact in assigned:
        log_contact_to_tidb(contact)
        orbit_period = next(s["orbit_period"] for s in SATELLITES if s["id"] == contact["satellite_id"])
        telemetry = simulate_telemetry(contact, orbit_period)
        print(f"Simulating telemetry for {contact['satellite_id']} at {contact['timestamp']}")
        log_telemetry_to_tidb(telemetry)
        print(f"Assigned & logged: {contact['satellite_id']} -> {contact['ground_station_id']}")

if __name__ == "__main__":
    main()

simulate_and_log = main

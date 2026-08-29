"""
data_generator.py
Since we don't have a real ground station, this module IS the "satellite".
It creates a fleet of fictional satellites and produces realistic-looking
telemetry: smooth orbital cycles (LEO satellites swing through hot/cold
and light/dark every ~90 minutes) plus sensor noise, with occasional
injected faults so the anomaly detector and dashboard have something to
find, both in the seeded history and in the live feed.
"""

import math
import random
from datetime import datetime, timedelta

SATELLITES = [
    {"name": "Aryabhata-Sim-1", "type": "Earth Observation", "orbit_type": "LEO",
     "nominal_altitude_km": 550, "nominal_velocity_kms": 7.6, "launch_date": "2022-03-14"},
    {"name": "VaruNet-2",        "type": "Weather",          "orbit_type": "LEO",
     "nominal_altitude_km": 820, "nominal_velocity_kms": 7.4, "launch_date": "2021-11-02"},
    {"name": "Comsat-Delta",     "type": "Communication",    "orbit_type": "GEO",
     "nominal_altitude_km": 35786, "nominal_velocity_kms": 3.07, "launch_date": "2019-07-21"},
    {"name": "NavIC-Lite-4",     "type": "Navigation",       "orbit_type": "MEO",
     "nominal_altitude_km": 20200, "nominal_velocity_kms": 3.9, "launch_date": "2020-01-30"},
    {"name": "HeliosScope-1",    "type": "Scientific",       "orbit_type": "LEO",
     "nominal_altitude_km": 610, "nominal_velocity_kms": 7.55, "launch_date": "2023-05-18"},
    {"name": "TerraLink-7",      "type": "Communication",    "orbit_type": "LEO",
     "nominal_altitude_km": 500, "nominal_velocity_kms": 7.62, "launch_date": "2022-09-09"},
]

ORBIT_PERIOD_MIN = {"LEO": 95, "MEO": 720, "GEO": 1436}


def _base_values(sat, minutes_elapsed):
    """Smooth, physically-flavoured baseline for one satellite at time t."""
    period = ORBIT_PERIOD_MIN.get(sat["orbit_type"], 95)
    phase = (minutes_elapsed % period) / period * 2 * math.pi

    # Sun-lit vs eclipse swings temperature and solar output
    sunlit = math.sin(phase)  # -1..1

    temperature = 20 + sunlit * 25          # roughly -5 .. 45 C
    solar_output = 95 + max(sunlit, -0.2) * 30  # drops sharply in eclipse
    battery_voltage = 29 + math.sin(phase * 2) * 1.5
    battery_current = 2.2 + max(0, -sunlit) * 1.2  # draws more from battery in eclipse
    signal_strength = 85 + math.sin(phase * 3 + 1) * 8
    fuel_level = max(5, 80 - minutes_elapsed / 4000)  # slow depletion over the sim
    altitude = sat["nominal_altitude_km"] + math.sin(phase / 3) * 1.5
    velocity = sat["nominal_velocity_kms"] + math.cos(phase / 3) * 0.02
    attitude_error = 0.5 + abs(math.sin(phase * 5)) * 0.6

    return {
        "temperature": temperature,
        "battery_voltage": battery_voltage,
        "battery_current": battery_current,
        "solar_panel_output": solar_output,
        "signal_strength": signal_strength,
        "fuel_level": fuel_level,
        "altitude": altitude,
        "velocity": velocity,
        "attitude_error": attitude_error,
    }


def _add_noise(values):
    noisy = {}
    noise_pct = {
        "temperature": 1.2, "battery_voltage": 0.15, "battery_current": 0.1,
        "solar_panel_output": 3, "signal_strength": 2, "fuel_level": 0.05,
        "altitude": 0.3, "velocity": 0.005, "attitude_error": 0.08,
    }
    for k, v in values.items():
        noisy[k] = v + random.gauss(0, noise_pct.get(k, 0.1))
    return noisy


FAULT_RECIPES = [
    # (param, delta_fn) -- injected faults, roughly half "low" severity, half "high"
    ("temperature", lambda v: v + random.choice([1, -1]) * random.uniform(45, 70)),
    ("battery_voltage", lambda v: v - random.uniform(6, 11)),
    ("battery_current", lambda v: v + random.uniform(3, 6)),
    ("solar_panel_output", lambda v: v - random.uniform(50, 80)),
    ("signal_strength", lambda v: v - random.uniform(45, 70)),
    ("fuel_level", lambda v: max(1, v - random.uniform(15, 40))),
    ("attitude_error", lambda v: v + random.uniform(3, 8)),
    ("temperature", lambda v: v + random.uniform(15, 22)),       # milder -> low severity
    ("signal_strength", lambda v: v - random.uniform(20, 35)),   # milder -> low severity
    ("battery_voltage", lambda v: v - random.uniform(3, 5)),     # milder -> low severity
]


def generate_point(sat, minutes_elapsed, force_fault=False):
    """Generate one telemetry reading. Occasionally injects a fault."""
    values = _add_noise(_base_values(sat, minutes_elapsed))

    if force_fault or random.random() < 0.035:  # ~3.5% of points are faulty
        param, fn = random.choice(FAULT_RECIPES)
        values[param] = fn(values[param])

    return values


def seed_history(conn, hours_back=18, interval_minutes=2):
    """Populate satellites table + a history of telemetry so the app isn't empty on first run."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM satellites")
    if cur.fetchone()["c"] > 0:
        return  # already seeded

    sat_ids = []
    for sat in SATELLITES:
        cur.execute("""
            INSERT INTO satellites (name, type, orbit_type, nominal_altitude_km,
                                     nominal_velocity_kms, launch_date, status)
            VALUES (?, ?, ?, ?, ?, ?, 'operational')
        """, (sat["name"], sat["type"], sat["orbit_type"], sat["nominal_altitude_km"],
              sat["nominal_velocity_kms"], sat["launch_date"]))
        sat_ids.append(cur.lastrowid)

    now = datetime.utcnow()
    total_points = int(hours_back * 60 / interval_minutes)
    start = now - timedelta(hours=hours_back)

    rows = []
    for sat, sat_id in zip(SATELLITES, sat_ids):
        for i in range(total_points):
            minutes_elapsed = i * interval_minutes
            ts = start + timedelta(minutes=minutes_elapsed)
            values = generate_point(sat, minutes_elapsed)
            rows.append((
                sat_id, ts.isoformat(), values["temperature"], values["battery_voltage"],
                values["battery_current"], values["solar_panel_output"],
                values["signal_strength"], values["altitude"], values["velocity"],
                values["fuel_level"], values["attitude_error"]
            ))

    cur.executemany("""
        INSERT INTO telemetry (satellite_id, timestamp, temperature, battery_voltage,
                                battery_current, solar_panel_output, signal_strength,
                                altitude, velocity, fuel_level, attitude_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"Seeded {len(rows)} telemetry rows across {len(SATELLITES)} satellites.")

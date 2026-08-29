"""
database.py
Handles all SQLite database setup and connections.
The DB is a single file (satellite_monitor.db) that lives right next to this
script -- this is the "database in VS Code itself" Pandu asked for. No
external DB server, no cloud service, nothing else to install.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "satellite_monitor.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS satellites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            orbit_type TEXT NOT NULL,
            nominal_altitude_km REAL NOT NULL,
            nominal_velocity_kms REAL NOT NULL,
            launch_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'operational'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            satellite_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            temperature REAL,
            battery_voltage REAL,
            battery_current REAL,
            solar_panel_output REAL,
            signal_strength REAL,
            altitude REAL,
            velocity REAL,
            fuel_level REAL,
            attitude_error REAL,
            FOREIGN KEY (satellite_id) REFERENCES satellites(id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_sat_time
        ON telemetry (satellite_id, timestamp)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            satellite_id INTEGER NOT NULL,
            telemetry_id INTEGER,
            timestamp TEXT NOT NULL,
            parameter TEXT NOT NULL,
            value REAL NOT NULL,
            severity TEXT NOT NULL,       -- 'high' or 'low'
            anomaly_score REAL,
            description TEXT,
            resolved INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (satellite_id) REFERENCES satellites(id)
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

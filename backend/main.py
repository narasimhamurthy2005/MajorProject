"""
main.py -- FastAPI backend entry point.

Run with:  uvicorn main:app --reload --port 8000
(from inside the backend/ folder)

On startup this:
  1. Creates the SQLite DB file + tables if they don't exist.
  2. Seeds ~18 hours of synthetic history for 6 satellites (only once).
  3. Runs anomaly detection over that seeded history.
  4. Starts a background task that appends a new "live" telemetry point
     for every satellite every few seconds, and re-runs detection --
     this is what makes the dashboard feel like it's watching a real feed.
"""

import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_connection
from data_generator import SATELLITES, seed_history, generate_point
from anomaly_detector import run_detection_all, detect_for_satellite
from chatbot import RAGChatbot

LIVE_INTERVAL_SECONDS = 5     # how often a new telemetry point is appended
MINUTES_PER_TICK = 2          # simulated minutes that pass per tick

_rag = None
_sim_minutes_elapsed = {}     # satellite_id -> simulated minute counter


async def _live_feed_loop():
    """Background task: keeps appending telemetry + running detection."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM satellites")
    sats = [dict(r) for r in cur.fetchall()]

    # seed the per-satellite minute counters from how much history already exists
    for sat in sats:
        cur.execute("""SELECT COUNT(*) AS c FROM telemetry WHERE satellite_id = ?""", (sat["id"],))
        count = cur.fetchone()["c"]
        _sim_minutes_elapsed[sat["id"]] = count * MINUTES_PER_TICK

    while True:
        try:
            for sat in sats:
                minutes = _sim_minutes_elapsed[sat["id"]]
                values = generate_point(sat, minutes)
                ts = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO telemetry (satellite_id, timestamp, temperature, battery_voltage,
                                            battery_current, solar_panel_output, signal_strength,
                                            altitude, velocity, fuel_level, attitude_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sat["id"], ts, values["temperature"], values["battery_voltage"],
                      values["battery_current"], values["solar_panel_output"],
                      values["signal_strength"], values["altitude"], values["velocity"],
                      values["fuel_level"], values["attitude_error"]))
                _sim_minutes_elapsed[sat["id"]] += MINUTES_PER_TICK
            conn.commit()

            for sat in sats:
                detect_for_satellite(conn, sat, lookback=60)
        except Exception as e:
            print(f"[live feed] error: {e}")

        await asyncio.sleep(LIVE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag
    init_db()
    conn = get_connection()
    seed_history(conn)
    run_detection_all(conn)
    conn.close()
    _rag = RAGChatbot()

    task = asyncio.create_task(_live_feed_loop())
    yield
    task.cancel()


app = FastAPI(title="Satellite Telemetry Monitoring System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------- #
#  Schemas
# ---------------------------------------------------------------------- #
class ChatQuery(BaseModel):
    message: str


# ---------------------------------------------------------------------- #
#  Satellite endpoints
# ---------------------------------------------------------------------- #
@app.get("/api/satellites")
def list_satellites():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM satellites ORDER BY name")
    sats = [dict(r) for r in cur.fetchall()]
    for sat in sats:
        cur.execute("""
            SELECT COUNT(*) AS c FROM anomalies
            WHERE satellite_id = ? AND resolved = 0 AND severity = 'high'
        """, (sat["id"],))
        sat["open_high_priority"] = cur.fetchone()["c"]
    conn.close()
    return sats


@app.get("/api/satellites/{sat_id}/latest")
def latest_telemetry(sat_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM telemetry WHERE satellite_id = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (sat_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "No telemetry yet for this satellite")
    return dict(row)


@app.get("/api/satellites/{sat_id}/telemetry")
def telemetry_history(sat_id: int, limit: int = 60):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM telemetry WHERE satellite_id = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (sat_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    rows.reverse()
    return rows


# ---------------------------------------------------------------------- #
#  Anomaly endpoints
# ---------------------------------------------------------------------- #
@app.get("/api/anomalies")
def list_anomalies(severity: str = None, resolved: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT anomalies.*, satellites.name AS satellite_name
        FROM anomalies JOIN satellites ON anomalies.satellite_id = satellites.id
        WHERE anomalies.resolved = ?
    """
    params = [resolved]
    if severity in ("high", "low"):
        query += " AND anomalies.severity = ?"
        params.append(severity)
    query += " ORDER BY anomalies.timestamp DESC LIMIT 200"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/anomalies/stats")
def anomaly_stats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT severity, COUNT(*) AS c FROM anomalies WHERE resolved = 0 GROUP BY severity")
    counts = {r["severity"]: r["c"] for r in cur.fetchall()}
    conn.close()
    return {"high": counts.get("high", 0), "low": counts.get("low", 0)}


@app.post("/api/anomalies/{anomaly_id}/resolve")
def resolve_anomaly(anomaly_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE anomalies SET resolved = 1 WHERE id = ?", (anomaly_id,))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        raise HTTPException(404, "Anomaly not found")
    return {"ok": True}


# ---------------------------------------------------------------------- #
#  Chatbot endpoint (RAG)
# ---------------------------------------------------------------------- #
@app.post("/api/chat")
def chat(query: ChatQuery):
    conn = get_connection()
    result = _rag.generate_answer(query.message, conn)
    conn.close()
    return result


@app.get("/api/health")
def health():
    return {"status": "ok"}

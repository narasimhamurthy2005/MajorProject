"""
anomaly_detector.py

Two-stage detection, the same pattern used in real ops pipelines (and the
one described in Pandu's review deck: autoencoder / isolation-forest style
unsupervised detection, then human-readable triage):

  1. ML stage -- an IsolationForest is fit per-satellite on its recent
     telemetry (all 9 numeric channels together) to flag points that are
     statistically unusual as a whole.
  2. Rule stage -- for any point the model flags, thresholds.py decides
     WHICH parameter is responsible and whether it's a high-priority
     (critical) or low-priority (warning) anomaly, in plain language.

This keeps detection genuinely ML-driven while keeping severity
explainable, which is what the dashboard's high/low priority stats need.
"""

import numpy as np
from sklearn.ensemble import IsolationForest

from thresholds import classify_param, PARAM_LABELS

NUMERIC_COLUMNS = [
    "temperature", "battery_voltage", "battery_current", "solar_panel_output",
    "signal_strength", "altitude", "velocity", "fuel_level", "attitude_error",
]


def _rows_to_matrix(rows):
    return np.array([[r[c] for c in NUMERIC_COLUMNS] for r in rows], dtype=float)


def detect_for_satellite(conn, satellite, lookback=300):
    """
    Runs IsolationForest over the satellite's most recent `lookback` telemetry
    rows, flags anomalous rows, classifies severity per parameter, and writes
    new rows into the `anomalies` table (skipping ones already recorded).
    Returns the number of new anomalies inserted.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM telemetry WHERE satellite_id = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (satellite["id"], lookback))
    rows = [dict(r) for r in cur.fetchall()]
    if len(rows) < 20:
        return 0
    rows.reverse()  # chronological order

    X = _rows_to_matrix(rows)
    # contamination: expected fraction of anomalous points; matches our ~3.5% fault rate
    model = IsolationForest(n_estimators=150, contamination=0.05, random_state=42)
    preds = model.fit_predict(X)          # -1 = anomaly, 1 = normal
    scores = model.decision_function(X)   # lower = more anomalous

    # Which telemetry ids already have an anomaly logged (avoid duplicates)
    cur.execute("SELECT DISTINCT telemetry_id FROM anomalies WHERE satellite_id = ?",
                (satellite["id"],))
    already_flagged = {r["telemetry_id"] for r in cur.fetchall()}

    inserted = 0
    for row, pred, score in zip(rows, preds, scores):
        if pred != -1 or row["id"] in already_flagged:
            continue

        # Find which specific parameter(s) explain the flag
        worst = None  # (severity_rank, param, severity, desc, value)
        for param in NUMERIC_COLUMNS:
            nom_alt = satellite["nominal_altitude_km"] if param == "altitude" else None
            nom_vel = satellite["nominal_velocity_kms"] if param == "velocity" else None
            sev, desc = classify_param(param, row[param], nom_alt, nom_vel)
            if sev is None:
                continue
            rank = 2 if sev == "high" else 1
            if worst is None or rank > worst[0]:
                worst = (rank, param, sev, desc, row[param])

        if worst is None:
            # Model flagged it but no single parameter breached a band on its own --
            # it's an unusual *combination* rather than one bad sensor. Log as low priority.
            severity = "low"
            param = "combined"
            desc = "Unusual combination of readings flagged by the anomaly model"
            value = float(score)
        else:
            _, param, severity, desc, value = worst

        cur.execute("""
            INSERT INTO anomalies (satellite_id, telemetry_id, timestamp, parameter,
                                    value, severity, anomaly_score, description, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (satellite["id"], row["id"], row["timestamp"], param, value, severity,
              float(score), desc))
        inserted += 1

    conn.commit()
    return inserted


def run_detection_all(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM satellites")
    sats = [dict(r) for r in cur.fetchall()]
    total = 0
    for sat in sats:
        total += detect_for_satellite(conn, sat)
    return total

# OrbitWatch — AI Satellite Telemetry Monitoring System

A full-stack demo project: synthetic satellite telemetry, ML-based anomaly
detection (Isolation Forest), a priority (high/low) anomaly board, a 3D
animated home page, and a RAG chatbot — all running locally with a SQLite
database file, no cloud services required.

## What's inside

```
satellite-monitor/
├── backend/                  FastAPI + SQLite + ML
│   ├── main.py                API entrypoint, background live-feed simulation
│   ├── database.py            SQLite schema + connection
│   ├── data_generator.py      Fake satellite fleet + synthetic telemetry generator
│   ├── anomaly_detector.py    IsolationForest + rule-based severity triage
│   ├── thresholds.py          Normal/warning/critical bands per parameter
│   ├── chatbot.py             RAG chatbot (TF-IDF retrieval + live data)
│   ├── knowledge/*.txt        Knowledge base the chatbot retrieves from
│   ├── requirements.txt
│   └── satellite_monitor.db   (created automatically on first run)
└── frontend/                  Plain HTML/CSS/JS (no build step)
    ├── index.html              Home page — 3D rotating satellite (Three.js)
    ├── dashboard.html          Satellite selector + live health + charts
    ├── anomalies.html          Priority board (high/low) + resolve action
    ├── css/style.css
    └── js/                     api.js, three-satellite.js, dashboard.js,
                                 anomalies.js, chatbot.js (floating widget)
```

## How to run it (VS Code)

### 1. Backend

Open a terminal in VS Code, inside `backend/`:

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The first time you run this it will:
- create `satellite_monitor.db` right there in the `backend/` folder (this
  **is** your database — open it any time with the SQLite VS Code
  extension or `sqlite3 satellite_monitor.db` to look at the raw tables),
- seed ~18 hours of synthetic telemetry for 6 satellites,
- run anomaly detection over that history,
- and then start appending a new "live" telemetry point per satellite
  every 5 seconds in the background, re-running detection each time —
  this is what makes the dashboard feel like a live feed.

Leave this terminal running. Check `http://127.0.0.1:8000/api/health`
in a browser — you should see `{"status":"ok"}`.

### 2. Frontend

The frontend is plain HTML/CSS/JS, so it doesn't need a build step — just
don't open the file with `file://` directly (browsers block some things,
like fetch to a different origin cleanly, and modules need a real server).
Easiest option in VS Code: install the **Live Server** extension, right
click `frontend/index.html` → "Open with Live Server".

Or, from a second terminal, no extension needed:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://127.0.0.1:5500` in your browser.

If your frontend runs on a different port than 5500 that's fine — it just
needs to be a `http://` address, not `file://`. If your **backend** runs
anywhere other than `127.0.0.1:8000`, update `API_BASE` at the top of
`frontend/js/api.js`.

## Using it

- **Home** — the 3D satellite scene. Drag to rotate the camera, scroll to
  zoom (Three.js `OrbitControls`, auto-rotating by default).
- **Dashboard** — pick a satellite from the dropdown to see its live health
  cards (color-coded green/amber/red), rolling charts, and its own recent
  anomalies. Auto-refreshes every 5 seconds.
- **Anomalies** — fleet-wide priority board: open high vs low priority
  counts, a filterable table, and a **Resolve** button per anomaly.
- **Chatbot** (bottom-right on every page) — ask things like *"how is
  Comsat-Delta doing?"*, *"what does attitude error mean?"*, or *"how does
  anomaly detection work?"*. It retrieves from `backend/knowledge/*.txt`
  via TF-IDF similarity and blends in live telemetry/anomaly data when you
  name a satellite. See the comment block at the bottom of `chatbot.py`
  for how to swap in a real LLM (e.g. the Anthropic API) later if you want
  more natural answers.

## Notes on the "AI" pieces (useful for your review/report)

- **Anomaly detection** is genuinely unsupervised ML: `IsolationForest`
  (scikit-learn) is fit per-satellite on its 9 telemetry channels together
  and flags statistically unusual points, with no fault labels given to
  it in advance. `thresholds.py` then explains *why* a flagged point is
  unusual and assigns it "high" (critical) or "low" (warning) priority —
  this two-stage design (unsupervised detection → rule-based triage) is a
  standard, defensible real-world pattern, and matches an
  autoencoder/isolation-forest based approach if that's what your review
  slides describe.
- **The chatbot is RAG** in the literal sense: retrieval (TF-IDF + cosine
  similarity over chunked knowledge text) plus augmented generation (the
  retrieved chunks and live DB data are combined into the final answer).
  It runs fully offline; there's a clearly marked spot in `chatbot.py` to
  plug in a real LLM API if you want it to phrase answers more fluently.
- **The data is synthetic** because there's no real satellite ground
  station to connect to — `data_generator.py` produces physically-flavored
  telemetry (orbital heating/cooling cycles, eclipse power dips, slow fuel
  depletion) with randomly injected faults, which is what the ML model and
  dashboard operate on. This is a normal, honest thing to state in a
  project report: "synthetic telemetry generated to emulate realistic
  satellite subsystem behavior, since live satellite access wasn't
  available."

## Extending it later

- Swap `IsolationForest` for the autoencoder / LSTM reconstruction-error
  approach mentioned in your review deck — same `anomaly_detector.py` slot.
- Swap the chatbot's templated answer for a real LLM call (see the comment
  in `chatbot.py`).
- Swap SQLite for Postgres later if you need multi-user access — the rest
  of the app only talks to `database.py`, so it's a small, contained change.

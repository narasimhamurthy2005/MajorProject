"""
thresholds.py
Defines the "normal / warning / critical" bands for every telemetry
parameter. These bands are what turn a raw number into a severity
(high priority / low priority), the same way a real ground-control
ops console works: ML flags "this looks statistically off", these
rules turn that into "and here's how bad it is, in human terms".

Altitude and velocity are checked relative to each satellite's own
nominal orbit (passed in), since that differs satellite to satellite.
"""

# (warn_low, crit_low, crit_high, warn_high)
PARAM_BANDS = {
    "temperature":        (-10, -25, 80, 65),      # deg C
    "battery_voltage":    (24, 21, 37, 35),         # V
    "battery_current":    (0.5, 0.2, 6.5, 5.0),     # A
    "solar_panel_output": (50, 30, 160, 145),       # W
    "signal_strength":    (40, 20, 100, 100),       # % (no real high-side risk)
    "fuel_level":         (20, 10, 100, 100),       # % (no high-side risk)
    "attitude_error":     (-999, -999, 5.0, 2.0),   # deg (only a "too high" is bad)
}

PARAM_UNITS = {
    "temperature": "°C",
    "battery_voltage": "V",
    "battery_current": "A",
    "solar_panel_output": "W",
    "signal_strength": "%",
    "fuel_level": "%",
    "altitude": "km",
    "velocity": "km/s",
    "attitude_error": "°",
}

PARAM_LABELS = {
    "temperature": "Temperature",
    "battery_voltage": "Battery Voltage",
    "battery_current": "Battery Current",
    "solar_panel_output": "Solar Panel Output",
    "signal_strength": "Signal Strength",
    "fuel_level": "Fuel Level",
    "altitude": "Altitude",
    "velocity": "Velocity",
    "attitude_error": "Attitude Error",
}


def classify_param(param, value, nominal_altitude=None, nominal_velocity=None):
    """
    Returns ('high'|'low'|None, description) for a single parameter reading.
    'high' = critical / high priority, 'low' = warning / low priority.
    """
    if param == "altitude" and nominal_altitude is not None:
        drift = abs(value - nominal_altitude)
        if drift > 20:
            return "high", f"Altitude drifted {drift:.1f} km from nominal orbit"
        if drift > 8:
            return "low", f"Altitude drifted {drift:.1f} km from nominal orbit"
        return None, None

    if param == "velocity" and nominal_velocity is not None:
        drift = abs(value - nominal_velocity)
        if drift > 0.3:
            return "high", f"Velocity deviates {drift:.3f} km/s from nominal"
        if drift > 0.12:
            return "low", f"Velocity deviates {drift:.3f} km/s from nominal"
        return None, None

    band = PARAM_BANDS.get(param)
    if not band:
        return None, None
    warn_low, crit_low, crit_high, warn_high = band

    if value <= crit_low or value >= crit_high:
        return "high", f"{PARAM_LABELS.get(param, param)} at {value:.2f}{PARAM_UNITS.get(param,'')} — critical threshold breached"
    if value <= warn_low or value >= warn_high:
        return "low", f"{PARAM_LABELS.get(param, param)} at {value:.2f}{PARAM_UNITS.get(param,'')} — outside normal range"
    return None, None

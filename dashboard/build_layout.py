"""Generate the NETPIE freeboard panes for the Charging Safety Monitor dashboard.

Writes dashboard/netpie_dashboard_layout.json containing only the "panes" list
(widgets and their settings). It contains NO datasource tokens or device keys,
so it is safe to commit. Layout follows dashboard/field-mapping.md section 5.

Usage (from the repo root):
    python dashboard/build_layout.py

To apply it, open the dashboard in the NETPIE portal, click Edit, and in the
browser console of the dashboard iframe run:
    cfg = freeboard.serialize(); cfg.panes = <panes JSON>; freeboard.loadDashboard(cfg)
then click Save. (Or rebuild the widgets by hand from field-mapping.md.)
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV = 'EV_Gateway'
SHADOW = f'#["{DEV}"]["shadow"]'
FEED = f'#["{DEV}"]["feed"]'
STATUS = f'#["{DEV}"]["status"]'

_id = 0


def wid() -> str:
    global _id
    _id += 1
    return f"w{_id:03d}"


def shadow(field: str) -> str:
    return f'{SHADOW}["{field}"]'


def fmt(field: str, decimals: int, scale: float = 1.0) -> str:
    """Text value that shows an em dash instead of 0/undefined when a reading is missing."""
    scaled = "Number(v)" if scale == 1.0 else f"Number(v) * {scale}"
    return (f'(function (v) {{ return (v === null || v === undefined || v === "") ? "—" : '
            f'({scaled}).toFixed({decimals}); }})({shadow(field)})')


def text(title, value, units="", size="regular", sparkline=False):
    return {"type": "text_widget", "settings": {
        "title": title, "size": size, "value": value, "sparkline": sparkline,
        "animate": False, "units": units}}


def gauge(title, field, units, lo, hi, decimals=1):
    return {"type": "gauge", "settings": {
        "title": title, "value": shadow(field), "units": units, "min_value": lo, "max_value": hi,
        "decimal": decimals, "human_friendly": False, "rangecolor": [], "rangeonpercent": False}}


def indicator(title, value, on_color, off_color, on_text, off_text, blinking="false"):
    return {"type": "indicator", "settings": {
        "title": title, "value": value, "oncolor": on_color, "offcolor": off_color,
        "var_oncolor": "", "var_offcolor": "", "blinking": blinking, "blinkfrequency": "2",
        "on_text": f'"{on_text}"', "off_text": f'"{off_text}"'}}


def html(path: str, height: int):
    body = (HERE / "widgets" / path).read_text(encoding="utf-8")
    return {"type": "html", "settings": {"html": body, "height": height}}


def chart(title, fields, minutes, y_title, axes=1, step=False):
    return {"type": "Chart", "settings": {
        "title": title, "datasource": FEED, "filter": ",".join(fields),
        "query_range": f"{minutes}m" if minutes < 60 else f"{minutes // 60}h",
        "stricttimerange": False, "mode": "autoslide", "type": "step" if step else "line",
        "xaxis": "", "yaxis": y_title, "yzero": False, "marker": False, "colors": "",
        "totalyaxis": axes, "height_block": 3}}


def pane(title, col_width, widgets, row, col):
    """row/col are freeboard grid positions for a 4-column screen; narrower screens stack panes."""
    for w in widgets:
        w["id"] = wid()
        w["settings"]["id"] = w["id"]
    rows = {"1": row, "2": row, "3": row, "4": row}
    cols = {"1": 1, "2": 1 if col == 1 else 2, "3": min(col, 3), "4": col}
    return {"title": title, "width": 1, "col_width": col_width, "row": rows, "col": cols, "widgets": widgets}


PANES = [
    pane("1. System status", 4, row=1, col=1, widgets=[
        html("state_banner.html", 2),
        indicator("Charging power", f'{shadow("power_cut")} === true', "#C62828", "#2E7D32",
                  "POWER CUT", "CHARGING ALLOWED"),
        indicator("Gateway link (NETPIE)", f'{STATUS} == 1', "#2E7D32", "#616161",
                  "Gateway online", "Gateway OFFLINE"),
    ]),
    pane("2. Battery", 2, row=9, col=1, widgets=[
        text("Battery surface temp (DS18B20)", fmt("temp_bat_c", 1), "°C", size="big"),
        gauge("Battery surface temp", "temp_bat_c", "°C", 0, 100),
        text("Temp rise rate dT/dt", fmt("temp_rate_c_per_s", 2), "°C/s"),
        chart("Battery temp & dT/dt (last 10 min)", ["temp_bat_c", "temp_rate_c_per_s"], 10, "°C | °C/s", axes=2),
    ]),
    pane("3. Fire / gas", 2, row=9, col=3, widgets=[
        indicator("Flame (KY-026)", f'{shadow("flame_detected")} === true', "#C62828", "#9E9E9E",
                  "FLAME DETECTED", "No flame", blinking=f'{shadow("flame_detected")} === true'),
        text("Gas MQ-135 (raw ADC, uncalibrated - not ppm)", fmt("gas_raw", 0), "raw"),
        chart("Gas raw (last 10 min)", ["gas_raw"], 10, "raw ADC"),
    ]),
    pane("4. Charging", 2, row=31, col=1, widgets=[
        text("Charging current (ACS712)", fmt("current_a", 2), "A", size="big"),
        gauge("Charging current", "current_a", "A", 0, 5, decimals=2),
        chart("Charging current (last 10 min)", ["current_a"], 10, "A"),
    ]),
    pane("5. Ambient (DHT11)", 2, row=31, col=3, widgets=[
        text("Ambient temp", fmt("temp_ambient_c", 1), "°C"),
        text("Humidity", fmt("humidity_pct", 1), "%"),
        chart("Ambient (last 1 h)", ["temp_ambient_c", "humidity_pct"], 60, "°C | %", axes=2),
    ]),
    pane("6. Diagnostics", 4, row=51, col=1, widgets=[
        html("sensor_health.html", 4),
        text("Node data age", fmt("node_age_ms", 1, scale=0.001), "s"),
        text("Node message #", fmt("node_sequence", 0)),
        text("Last button event (KY-004)",
             f'(function (v) {{ return v ? v : "—"; }})({shadow("button_event")})'),
        text("Gateway uptime", fmt("timestamp_ms", 0, scale=0.001), "s"),
        text("Contract version", fmt("schema_version", 0)),
        chart("Power cut / flame events (last 10 min)", ["power_cut", "flame_detected"], 10, "1 = on", step=True),
    ]),
]


def main() -> None:
    out = HERE / "netpie_dashboard_layout.json"
    out.write_text(json.dumps({"panes": PANES}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote dashboard/{out.name} ({sum(len(p['widgets']) for p in PANES)} widgets in {len(PANES)} panes)")


if __name__ == "__main__":
    main()

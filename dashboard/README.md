# NETPIE Dashboard

This folder holds dashboard planning and exported/configuration artifacts for the charging safety monitor.

## Planned dashboard view

- System state: `NORMAL`, `WARNING`, `HAZARD`, `SENSOR_ERROR`, or `OFFLINE` (confirm final state names).
- Battery-surface temperature (`temp_bat_c`) with units and history.
- Temperature trend (`temp_rate_c_per_s`), if implemented.
- Ambient temperature and humidity, if those sensors are used.
- Current, gas, and flame readings only when the corresponding sensor is in scope and its value is interpreted correctly.
- Last update time, connection status, and power-cut state.

## Setup notes

1. Confirm the team's NETPIE account, project/device model, and the currently supported dashboard/data-ingestion workflow.
2. Use the shared contract in `../docs/data-contract.md` as the starting point for field mapping.
3. Connect simulator telemetry first, then validate with ESP32 data.
4. Keep credentials, access tokens, and webhook URLs in local configuration or the service's secret store. Never commit them here.
5. Add dashboard screenshots, export files, or setup notes to this directory when available. Check provider terms and export format before committing generated files.

## Widget mapping draft

| Display | Contract field | Display notes |
| --- | --- | --- |
| System state | `state` | Prominent text/status indicator |
| Battery temperature | `temp_bat_c` | °C; show missing/stale data distinctly |
| Temperature trend | `temp_rate_c_per_s` | °C/s; include only if trend calculation is implemented |
| Ambient temperature | `temp_ambient_c` | °C; optional |
| Humidity | `humidity_pct` | %RH; optional |
| Charging current | `current_a` | A; only after sensor calibration/interpretation |
| Gas reading | `gas_raw` | Raw value unless calibrated |
| Flame | `flame_detected` | Boolean/status |
| Cut-off status | `power_cut` | Show the Gateway's reported state |
| Freshness/connectivity | `timestamp_ms` plus device connection | Define stale-data timeout in the implementation |

Remote cut/reset controls are not included in this scaffold. Add them only after a safe command path and local confirmation behavior have been designed and tested.

# Data Contract

The simulator and firmware should use one shared, versioned message contract. The schema below is a planning draft; confirm field names, sensor assignments, units, and transport with the team before implementation.

## Draft telemetry fields

| Field | Type | Unit / meaning |
| --- | --- | --- |
| `schema_version` | integer | Contract version |
| `sequence` | integer | Increasing message number |
| `timestamp_ms` | integer | Uptime timestamp, or use a documented wall-clock format |
| `temp_bat_c` | number or null | Battery-surface temperature in °C |
| `temp_ambient_c` | number or null | Ambient temperature in °C |
| `humidity_pct` | number or null | Relative humidity, percent |
| `current_a` | number or null | Current in amperes, if measured and calibrated |
| `gas_raw` | integer or null | Raw gas-sensor reading unless calibration defines another unit |
| `flame_detected` | boolean or null | Flame sensor state |
| `temp_rate_c_per_s` | number or null | Temperature trend in °C/s, if implemented |
| `state` | string | Agreed system state |
| `power_cut` | boolean | Whether the local cut-off output is active |
| `validity` | object | Per-sensor validity or error information |

## Contract rules to settle

- [ ] Choose exact required and optional fields.
- [ ] Define missing, stale, invalid, and out-of-range reading behavior.
- [ ] Define message frequency and stale-message timeout.
- [ ] Define state names and allowed transitions.
- [ ] Define transport framing and maximum message size.
- [ ] Keep sensor values distinguishable from zero when unavailable (use `null` plus validity information, or an agreed equivalent).

Do not use uncalibrated gas/current values as precise physical measurements. Document calibration and units before displaying engineering values.

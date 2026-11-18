# Data Contract

The Sensor Node and Gateway should share a versioned ESP-NOW message format. The simulator, Gateway cloud publisher, and NETPIE dashboard should use the same field meanings. This schema is the agreed hardware-oriented draft; confirm sample rates, ranges, and encoding with the team before implementation.

## Sensor Node to Gateway telemetry

| Field | Type | Unit / meaning |
| --- | --- | --- |
| `schema_version` | integer | Message contract version |
| `sequence` | integer | Increasing Node message number |
| `uptime_ms` | integer | Node uptime when sampled |
| `temp_bat_c` | number or null | DS18B20 battery-surface temperature in °C |
| `gas_raw` | integer or null | MQ-135 raw ADC reading; not a calibrated gas concentration |
| `flame_detected` | boolean | KY-026 digital state; document active-high/active-low polarity after wiring |
| `flame_event` | boolean | Whether the interrupt captured a new flame transition/event since the prior report |
| `sensor_status` | object | Per-sensor validity/error flags |

## Gateway aggregate telemetry

| Field | Type | Unit / meaning |
| --- | --- | --- |
| `schema_version` | integer | Message contract version |
| `timestamp_ms` | integer | Gateway uptime, or use a separately documented wall-clock format |
| `node_sequence` | integer or null | Most recently accepted Node sequence |
| `node_age_ms` | integer or null | Age of last accepted Node message |
| `temp_bat_c` | number or null | Forwarded DS18B20 reading in °C |
| `gas_raw` | integer or null | Forwarded MQ-135 raw reading |
| `flame_detected` | boolean or null | Forwarded KY-026 level |
| `temp_ambient_c` | number or null | DHT11 ambient temperature in °C |
| `humidity_pct` | number or null | DHT11 relative humidity in percent |
| `current_a` | number or null | ACS712 current in amperes after calibration |
| `temp_rate_c_per_s` | number or null | Optional battery-temperature trend in °C/s |
| `state` | string | Agreed system state |
| `power_cut` | boolean | Gateway-reported cut-off state |
| `button_event` | string or null | KY-004 event, using agreed values such as `STOP` or `RESET` |
| `validity` | object | Sensor and message validity/error information |

## Contract rules to settle

- [ ] Define exact field encoding for ESP-NOW and cloud publication.
- [ ] Define Node and Gateway sample/publish rates and stale-message timeout.
- [ ] Confirm KY-026 active polarity and interrupt event/latching behavior.
- [ ] Define missing, stale, invalid, and out-of-range reading behavior.
- [ ] Define ACS712 zero offset, calibration, current direction, and safe ADC scaling.
- [ ] Define state names and allowed transitions.
- [ ] Treat `gas_raw` as raw until the sensor is warmed up and a calibration/interpretation method is selected.
- [ ] Ensure unavailable readings are distinguishable from zero.
- [ ] Define KY-004 stop/reset event semantics and ensure reset cannot silently re-enable charging.

Do not use uncalibrated gas/current readings as precise physical measurements.

# Sample Messages

Example **Gateway aggregate telemetry** messages that follow [`../data-contract.md`](../data-contract.md). They are shared test inputs for the dashboard, the simulator, and later the Gateway firmware.

| File | Scenario |
| --- | --- |
| `gateway_normal.json` | Stable charging, all sensors valid |
| `gateway_warning.json` | Battery temperature rising faster than normal, power still supplied |
| `gateway_hazard.json` | Rapid temperature rise, high gas reading, and flame detected. The Gateway reports power cut, and current has dropped. |
| `gateway_sensor_error.json` | DS18B20 reading unavailable (`temp_bat_c: null`, `validity.temp_bat: false`) |
| `gateway_node_stale.json` | No fresh ESP-NOW message for 8.2 s (`node_age_ms`, `validity.node_link: false`) |

## Important

- **All values are illustrative.** They are chosen to exercise the dashboard and are not validated thresholds or safety limits.
- The files are transport-neutral. For NETPIE, publish them to `@shadow/data/update` wrapped as `{"data": <file contents>}` (see [`../../dashboard/field-mapping.md`](../../dashboard/field-mapping.md)).
- Draft parts still need team agreement:
  - The `validity` object shape (`node_link`, `temp_bat`, `gas`, `flame`, `ambient`, `current` booleans).
  - The state names. The samples use names proposed in `software_checklist.md`.
  - Which state the Gateway reports when Node data goes stale. `gateway_node_stale.json` uses `SENSOR_ERROR` as a placeholder.
  - What the Gateway does on a sensor error. Both error samples keep `power_cut: false`, which is not a decision.
- `schema_version` is `1`. Bump it in every sample when the contract changes.

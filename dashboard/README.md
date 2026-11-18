# NETPIE Dashboard

This folder contains dashboard planning and safe-to-commit setup/export artifacts for the charging safety monitor. NETPIE is the planned platform; verify the team's account and currently supported dashboard/data-ingestion workflow before implementation.

## Planned displays

- System state and last update / connectivity freshness.
- DS18B20 battery-surface temperature (`temp_bat_c`) and history.
- MQ-135 raw reading (`gas_raw`), clearly labeled as raw until calibrated.
- KY-026 flame level/event (`flame_detected`, optionally `flame_event`).
- ACS712 charging current (`current_a`) after calibration.
- DHT11 ambient temperature (`temp_ambient_c`) and humidity (`humidity_pct`).
- Gateway cut-off state (`power_cut`).
- Optional temperature trend (`temp_rate_c_per_s`) if implemented.

Use `../docs/data-contract.md` as the source of field definitions. Show invalid or stale readings distinctly from zero. Remote stop/reset controls are not planned until a safe command path and reset behavior are defined and tested.

Never commit access tokens, credentials, or webhook URLs.

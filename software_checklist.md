# Charging Safety Alarm Software Checklist

## Project goal

Build the software for an embedded charging safety monitor. The system should monitor battery temperature and other available sensor signals, identify unsafe conditions, alert the user, and support a controlled power cut. The first development target is a computer simulator and dashboard; the firmware will run on ESP32 hardware later.

> Progress update 2026-11-20: simulator, safety-logic prototype, sample messages, and the NETPIE dashboard are built and tested. See `simulator/README.md` and `dashboard/field-mapping.md`.

> Confirmed hardware plan: two ESP32 DevKit V1 30-pin boards. The Sensor Node uses DS18B20/KY-001, MQ-135, and interrupt-driven KY-026; the Gateway uses ACS712 5 A, DHT11, MG90S servo, and KY-004. ESP-NOW and NETPIE are planned. Pin mappings, thresholds, calibration, protocol details, and button stop/reset behavior still need agreement.

## 1. Define the software requirements

- [ ] Write a short system description and the exact problem the software solves.
- [x] Select the two main board roles: ESP32 DevKit V1 30-pin Sensor Node and ESP32 DevKit V1 30-pin Gateway.
- [x] Assign sensors: Node reads DS18B20/KY-001, MQ-135, and interrupt-driven KY-026; Gateway reads ACS712 5 A and DHT11, and controls MG90S servo and KY-004.
- [ ] Confirm the required sensor set and which readings are optional or only for demonstration (for example, gas, flame, and charging current).
- [ ] Agree on operating modes and user-visible states, such as `STARTING`, `NORMAL`, `WARNING`, `HAZARD`, `SENSOR_ERROR`, and `OFFLINE`.
- [ ] Agree on what the system does for each state, including whether a hazard automatically triggers power cut.
- [ ] Choose safe, explainable threshold values and document their source. Keep thresholds configurable; do not treat example values in chat notes as validated safety limits.
- [ ] Define how to recover/reset after an alert and who is allowed to request a reset.
- [ ] Document limits of the prototype: it is a classroom demonstrator, not a certified charger or battery protection device.

## 2. Set up the software repository

- [x] Create and document a clean project layout:
  - [x] `firmware_node/` — sensor reading and ESP-NOW transport
  - [x] `firmware_gateway/` — sensor aggregation, decision logic, actuator, alerts, and cloud connection
  - [x] `simulator/` — computer-based simulated sensor data and scenarios
  - [x] `dashboard/` — NETPIE dashboard planning and field mapping
  - [x] `docs/` — architecture, data contract, wiring references, setup, and test notes
- [x] Add root and component README files with project purpose, responsibilities, and current decisions.
- [x] Add `.gitignore` entries for local secrets and common generated/build files.
- [ ] Add a tracked `config.example.h` or equivalent template with placeholder values only. _(simulator done: `simulator/.env.example`; firmware `config.example.h` still needed)_
- [x] Keep real cloud credentials and webhook URLs out of source control; use local config or environment variables. _(NETPIE keys live in ignored `simulator/.env`)_
- [ ] Choose and record the firmware toolchain (Arduino IDE or PlatformIO) and the simulator Python version. _(simulator: Python 3.9+ recorded in `simulator/README.md`; firmware toolchain not chosen)_

## 3. Agree on the data contract

- [x] Define one versioned message format shared by the simulator, firmware, dashboard, and alert code. _(`docs/data-contract.md`, `schema_version` 1; used by simulator and dashboard)_
- [x] Include fields only when they have a clear source and unit. Suggested starting fields:
  - [x] `timestamp` or sequence number
  - [x] `temp_bat_c`
  - [x] `temp_ambient_c`
  - [x] `humidity_pct`
  - [x] `current_a`
  - [x] `gas_raw` (or a calibrated unit if calibration is available)
  - [x] `flame_detected`
  - [x] `temp_rate_c_per_s`
  - [x] `state`
  - [x] `power_cut`
  - [x] sensor validity / error flags _(`validity` object; shape is still a draft)_
- [ ] Specify types, units, valid ranges, missing-value behavior, and message frequency. _(types/units done; tested that NETPIE deletes `null` fields; ranges and publish rate still open, free quota limits ~1 msg/6 s continuous)_
- [ ] Define how Node-to-Gateway messages are identified and how stale or duplicate readings are handled.
- [x] Save sample normal, warning, hazard, and sensor-error messages in `docs/`. _(`docs/samples/`, plus a stale-Node sample)_
- [x] Keep the contract transport-neutral so cloud/ESP-NOW details can change without changing field meanings. _(NETPIE `{"data": ...}` wrapper is added only by the publisher)_

## 4. Build the computer simulator first

- [x] Create `simulator/virtual_gateway.py` to generate readings using the agreed data contract.
- [x] Add repeatable scenarios for: _(9 scenarios incl. node_stale and button_reset; fixed seed)_
  - [x] Normal, stable charging
  - [x] Gradual temperature increase
  - [x] Rapid temperature rise
  - [x] Over-temperature condition
  - [x] Flame or gas warning (if those sensors are in project scope)
  - [x] Disconnected or invalid sensor
  - [x] Lost network connection and reconnection
- [x] Make scenario rate and values configurable from command-line options or a local config file. _(`--interval`, `--speed`, `--duration`, `--seed`, `--thresholds`)_
- [x] Print readable logs showing readings, state changes, and alert decisions.
- [x] First validate simulator behavior locally without cloud credentials. _(21 unit tests)_
- [x] Add a dry-run mode that never sends external alerts or commands. _(default mode; `--publish` is opt-in)_

## 5. Implement and review the safety decision logic

- [x] Separate sensor acquisition, filtering, trend calculation, state decision, and output actions into distinct modules/functions. _(simulator prototype; firmware port pending)_
- [ ] Decide how to filter noisy readings and reject impossible values. _(not done yet)_
- [x] Define behavior when readings are missing, stale, or inconsistent; fail to a clearly visible safe state. _(prototype: `SENSOR_ERROR`, power not cut automatically; team decision pending)_
- [x] If using a temperature trend (`dT/dt`), define its sample window, units, minimum data needed, and handling of noisy or missing samples. _(least-squares over 10 s, min 5 samples, °C/s)_
- [x] If using a decision tree or other classifier, write down its rules in plain language and make them inspectable. _(`simulator/README.md` decision rules)_
- [x] Add hysteresis or a deliberate recovery rule to avoid rapidly switching between `NORMAL` and `WARNING` near a threshold. _(5 clear samples)_
- [ ] Ensure alert and power-cut actions are triggered once per event or are rate-limited, rather than repeating on every sample. _(power cut latched until local RESET; alerts not implemented yet)_
- [x] Log why each state transition happened (for example, threshold crossed, sensor fault, or manual cut command).
- [ ] Review all thresholds and actions with the class team before hardware operation. _(current thresholds are placeholders)_

## 6. Create the dashboard

- [x] Confirm which cloud/dashboard service the team will use and verify that it currently supports the needed device, data, and dashboard features. _(NETPIE 2020, tested)_
- [x] Create the project/device and store its credentials locally, not in Git. _(project `Smart-EV-Battery-Guard`, device `EV_Gateway`)_
- [x] Connect the simulator to the service only after the data contract works locally. _(REST transport; MQTT TLS blocked by NEXPIE private CA)_
- [x] Build a dashboard that clearly shows: _(`Charging Safety Monitor`, 6 panels / 23 widgets)_
  - [x] Current system state (`NORMAL`, `WARNING`, `HAZARD`, etc.)
  - [x] Battery temperature and its history
  - [x] Temperature rise rate, if implemented
  - [x] Ambient temperature and humidity
  - [x] Current, gas, or flame values when those inputs are implemented
  - [ ] Last update time and connectivity status _(Node data age shown; online indicator follows MQTT only, so it stays offline during REST tests; no wall-clock last-update time yet)_
  - [x] Power-cut state
- [x] Use labels with units and sensible chart ranges; distinguish unavailable readings from zero.
- [ ] Test the dashboard with each simulator scenario and confirm displayed states match simulator logs. _(all samples and live `button_reset` passed; other scenarios not yet run live)_
- [ ] Add dashboard controls only if the cloud service and firmware support a safe command path. _(none added; dashboard has read-only privileges)_
- [ ] For any remote cut/reset control, require a deliberate action, show command status, and prevent a cloud command from silently re-enabling charging.

## 7. Implement notifications

- [ ] Choose and verify a notification channel that is currently available (the notes propose a Discord webhook).
- [ ] Keep webhook credentials private and out of repository history.
- [ ] Define which transitions create notifications and include the event, key readings, and timestamp.
- [ ] Add duplicate suppression or a cooldown so a persistent hazard does not flood the channel.
- [ ] Handle HTTP/network failures and log whether delivery succeeded.
- [ ] Test notifications using simulator scenarios and a private/test channel before group use.
- [ ] Ensure the system remains locally safe if cloud notification is unavailable.

## 8. Port the software to ESP32

- [ ] Confirm actual board model, sensor modules, pin assignments, voltage levels, and power arrangement before writing hardware-specific setup.
- [ ] Implement and validate each sensor driver independently on the target board.
- [ ] Implement Node-to-Gateway communication (the notes propose ESP-NOW) and test message loss, stale data, and reconnection behavior.
- [ ] Implement Gateway Wi-Fi/cloud publishing after local sensor and inter-board communication work.
- [ ] Keep hardware secrets in an ignored local configuration file.
- [ ] Add watchdog, bounded retries, startup diagnostics, and clear serial logs.
- [ ] Confirm memory/storage needs before selecting a flash filesystem or offline log strategy.
- [ ] Treat OTA updates, TLS, persistent buffering, and multi-core task separation as optional extensions; add them only after the basic monitoring and alert path works.
- [ ] Test the power-cut actuator separately with a safe low-voltage demonstration setup before connecting it to any charging path.

## 9. Integration and demonstration readiness

- [ ] Verify the same sample message works through simulator, decision logic, dashboard, and notification path.
- [ ] Compare simulator and ESP32 outputs for the same input sequence.
- [ ] Demonstrate normal, warning, hazard, sensor failure, and network failure behavior.
- [ ] Confirm an alert still appears locally (serial/status indicator) when cloud services are down.
- [ ] Record test steps, expected results, observed results, and known limitations in `docs/test-notes.md`.
- [ ] Prepare a short live-demo sequence and reset procedure.
- [ ] Capture screenshots or logs for the final project report.

## Suggested order of work

1. Requirements and sensor/board role decisions
2. Repository layout and data contract
3. Local simulator and decision logic
4. Dashboard using simulated data
5. Notification path using simulated hazards
6. ESP32 sensor drivers and Node-to-Gateway link
7. Cloud integration on hardware
8. Safe actuator demonstration and final integration



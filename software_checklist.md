# Charging Safety Alarm Software Checklist

## Project goal

Build the software for an embedded charging safety monitor. The system should monitor battery temperature and other available sensor signals, identify unsafe conditions, alert the user, and support a controlled power cut. The first development target is a computer simulator and dashboard; the firmware will run on ESP32 hardware later.

> Treat sensor assignments and cloud platform details below as planning assumptions from the project notes. Confirm the final hardware, thresholds, data protocol, and currently supported cloud features with the team before relying on them.

## 1. Define the software requirements

- [ ] Write a short system description and the exact problem the software solves.
- [ ] Decide which ESP32 boards are active roles: Sensor Node, Gateway, and whether any third board has a defined purpose.
- [ ] Confirm which sensors are read by each board (proposed: DS18B20 battery-surface temperature at the Node; DHT11 ambient temperature/humidity and other sensors at the Gateway).
- [ ] Confirm the required sensor set and which readings are optional or only for demonstration (for example, gas, flame, and charging current).
- [ ] Agree on operating modes and user-visible states, such as `STARTING`, `NORMAL`, `WARNING`, `HAZARD`, `SENSOR_ERROR`, and `OFFLINE`.
- [ ] Agree on what the system does for each state, including whether a hazard automatically triggers power cut.
- [ ] Choose safe, explainable threshold values and document their source. Keep thresholds configurable; do not treat example values in chat notes as validated safety limits.
- [ ] Define how to recover/reset after an alert and who is allowed to request a reset.
- [ ] Document limits of the prototype: it is a classroom demonstrator, not a certified charger or battery protection device.

## 2. Set up the software repository

- [ ] Create and document a clean project layout:
  - [ ] `firmware_node/` — sensor reading and Node-to-Gateway transport
  - [ ] `firmware_gateway/` — sensor aggregation, decision logic, alerts, and cloud connection
  - [ ] `simulator/` — computer-based simulated sensor data and scenarios
  - [ ] `docs/` — architecture, data format, wiring references, setup, and test notes
- [ ] Add a `README.md` with project purpose, setup steps, run instructions, and current status.
- [ ] Add `.gitignore` entries for local secrets, generated files, build outputs, and editor files.
- [ ] Add a tracked `config.example.h` or equivalent template with placeholder values only.
- [ ] Keep real cloud credentials and webhook URLs out of source control; use local config or environment variables.
- [ ] Choose and record the firmware toolchain (Arduino IDE or PlatformIO) and the simulator Python version.

## 3. Agree on the data contract

- [ ] Define one versioned message format shared by the simulator, firmware, dashboard, and alert code.
- [ ] Include fields only when they have a clear source and unit. Suggested starting fields:
  - [ ] `timestamp` or sequence number
  - [ ] `temp_bat_c`
  - [ ] `temp_ambient_c`
  - [ ] `humidity_pct`
  - [ ] `current_a`
  - [ ] `gas_raw` (or a calibrated unit if calibration is available)
  - [ ] `flame_detected`
  - [ ] `temp_rate_c_per_s`
  - [ ] `state`
  - [ ] `power_cut`
  - [ ] sensor validity / error flags
- [ ] Specify types, units, valid ranges, missing-value behavior, and message frequency.
- [ ] Define how Node-to-Gateway messages are identified and how stale or duplicate readings are handled.
- [ ] Save sample normal, warning, hazard, and sensor-error messages in `docs/`.
- [ ] Keep the contract transport-neutral so cloud/ESP-NOW details can change without changing field meanings.

## 4. Build the computer simulator first

- [ ] Create `simulator/virtual_gateway.py` to generate readings using the agreed data contract.
- [ ] Add repeatable scenarios for:
  - [ ] Normal, stable charging
  - [ ] Gradual temperature increase
  - [ ] Rapid temperature rise
  - [ ] Over-temperature condition
  - [ ] Flame or gas warning (if those sensors are in project scope)
  - [ ] Disconnected or invalid sensor
  - [ ] Lost network connection and reconnection
- [ ] Make scenario rate and values configurable from command-line options or a local config file.
- [ ] Print readable logs showing readings, state changes, and alert decisions.
- [ ] First validate simulator behavior locally without cloud credentials.
- [ ] Add a dry-run mode that never sends external alerts or commands.

## 5. Implement and review the safety decision logic

- [ ] Separate sensor acquisition, filtering, trend calculation, state decision, and output actions into distinct modules/functions.
- [ ] Decide how to filter noisy readings and reject impossible values.
- [ ] Define behavior when readings are missing, stale, or inconsistent; fail to a clearly visible safe state.
- [ ] If using a temperature trend (`dT/dt`), define its sample window, units, minimum data needed, and handling of noisy or missing samples.
- [ ] If using a decision tree or other classifier, write down its rules in plain language and make them inspectable.
- [ ] Add hysteresis or a deliberate recovery rule to avoid rapidly switching between `NORMAL` and `WARNING` near a threshold.
- [ ] Ensure alert and power-cut actions are triggered once per event or are rate-limited, rather than repeating on every sample.
- [ ] Log why each state transition happened (for example, threshold crossed, sensor fault, or manual cut command).
- [ ] Review all thresholds and actions with the class team before hardware operation.

## 6. Create the dashboard

- [ ] Confirm which cloud/dashboard service the team will use and verify that it currently supports the needed device, data, and dashboard features.
- [ ] Create the project/device and store its credentials locally, not in Git.
- [ ] Connect the simulator to the service only after the data contract works locally.
- [ ] Build a dashboard that clearly shows:
  - [ ] Current system state (`NORMAL`, `WARNING`, `HAZARD`, etc.)
  - [ ] Battery temperature and its history
  - [ ] Temperature rise rate, if implemented
  - [ ] Ambient temperature and humidity
  - [ ] Current, gas, or flame values when those inputs are implemented
  - [ ] Last update time and connectivity status
  - [ ] Power-cut state
- [ ] Use labels with units and sensible chart ranges; distinguish unavailable readings from zero.
- [ ] Test the dashboard with each simulator scenario and confirm displayed states match simulator logs.
- [ ] Add dashboard controls only if the cloud service and firmware support a safe command path.
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

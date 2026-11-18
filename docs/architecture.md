# Architecture

## Planned data flow

1. A Sensor Node reads the battery-surface temperature sensor and any other sensors assigned to that node.
2. The Node sends readings to the Gateway over the agreed local transport. ESP-NOW is the current proposal and must be confirmed against the selected boards.
3. The Gateway validates readings, calculates any temperature trend, decides the system state, and controls local outputs.
4. The Gateway may publish telemetry and send notifications when connectivity is available.
5. The simulator exercises the same data contract and state logic before hardware is connected.

## Planned software boundaries

- `firmware_node/`: sensor drivers, sampling, message encoding, and transport.
- `firmware_gateway/`: message intake, sensor validation, state logic, actuator interface, and optional cloud adapters.
- `simulator/`: generated readings and repeatable fault/hazard scenarios.
- `docs/`: decisions and verification notes.

## Decisions to confirm

- Active board roles and the purpose of any additional ESP32 board.
- Sensor-to-board assignment and final sensor list.
- Node-to-Gateway transport and message frequency.
- Cloud/dashboard service and notification channel.
- State names, thresholds, trend window, and recovery behavior.
- Hardware pin map and actuator behavior.

This is a classroom prototype plan. It is not a certified battery-management or charging-protection system.

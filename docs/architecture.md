# Architecture

## Planned data flow

1. A Sensor Node reads the battery-surface temperature sensor and any other sensors assigned to that node.
2. The Node sends readings to the Gateway over the agreed local transport. ESP-NOW is the current proposal and must be confirmed against the selected boards.
3. The Gateway validates readings, calculates any temperature trend, decides the system state, and controls local outputs.
4. When network connectivity is available, the Gateway publishes telemetry to the selected cloud service. NETPIE is the planned platform; confirm the team's account and currently supported ingestion/dashboard workflow before implementation.
5. The NETPIE dashboard displays the latest state and readings, along with their history and connectivity/freshness status where supported.
6. The Gateway may send notifications when configured. Local monitoring and safety behavior should not depend on the dashboard or cloud connection.
7. The simulator exercises the same data contract and state logic before hardware is connected, and can supply test data for the dashboard.

## Planned software boundaries

- `firmware_node/`: sensor drivers, sampling, message encoding, and transport.
- `firmware_gateway/`: message intake, sensor validation, state logic, actuator interface, and optional cloud adapters.
- `simulator/`: generated readings and repeatable fault/hazard scenarios.
- `dashboard/`: NETPIE dashboard planning, field-to-widget mapping, and any safe-to-commit exported artifacts or setup notes.
- `docs/`: architecture, data contract, wiring notes, decisions, and verification records.

## Dashboard responsibilities

The dashboard should make the current condition easy to understand and help inspect recent readings. Planned displays include system state, battery temperature, and—if implemented—temperature trend. Ambient readings and current, gas, and flame values should appear only when those sensors are in scope and their units or interpretation are clear. Show missing or stale readings distinctly from zero.

Remote cut/reset controls are not part of the initial design. Add them only after a safe command path and local confirmation behavior have been designed and tested.

## Decisions to confirm

- Active board roles and the purpose of any additional ESP32 board.
- Sensor-to-board assignment and final sensor list.
- Node-to-Gateway transport and message frequency.
- NETPIE project/device setup and the supported telemetry/dashboard workflow.
- Dashboard field mapping, history needs, and stale-data timeout.
- Notification channel and trigger rules.
- State names, thresholds, trend window, and recovery behavior.
- Hardware pin map and actuator behavior.

This is a classroom prototype plan. It is not a certified battery-management or charging-protection system.

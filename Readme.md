# Charging Safety Alarm

Embedded systems class project for monitoring charging-device temperature, identifying unsafe conditions, and notifying the user. The software is being prepared for ESP32 hardware, with a computer simulator for development before the boards are available.

## Repository layout

- `firmware_node/` — Sensor Node firmware and its ESP-NOW message handling.
- `firmware_gateway/` — Gateway firmware, safety-state logic, notifications, and cloud connection.
- `simulator/` — Computer-based sensor and Gateway simulator.
- `dashboard/` — NETPIE dashboard plan, field mapping, and exported artifacts.
- `docs/` — Architecture, data contract, wiring notes, and test records.
- `software_checklist.md` — Work breakdown and implementation checklist.

## Current development status

The team has selected two ESP32 DevKit V1 30-pin boards: a Sensor Node with DS18B20/KY-001, MQ-135, and interrupt-driven KY-026; and a Gateway with ACS712 5 A, DHT11, MG90S servo, and KY-004 button. The proposed link is ESP-NOW, and NETPIE is the planned dashboard platform. Pin mappings, thresholds, message timing, sensor calibration, and stop/reset behavior still need to be confirmed. Keep thresholds configurable and do not treat example values as validated battery-protection limits.

## Getting started

1. Read `docs/architecture.md` and `docs/data-contract.md`.
2. Confirm the project decisions listed in those documents with the team.
3. Build the simulator and local decision logic before connecting cloud services.
4. Add ESP32-specific code after confirming the actual board and wiring.

## Secrets

Do not commit Wi-Fi passwords, cloud credentials, webhook URLs, or real local config files. Use the ignored local config files described in each component. Example templates may be committed only when they contain placeholders.




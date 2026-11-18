# Sensor Node Firmware

Target board: ESP32 DevKit V1, 30-pin.

## Assigned inputs

- DS18B20 / KY-001 — battery-surface temperature.
- MQ-135 — raw gas/smoke sensor reading.
- KY-026 — flame sensor digital input, captured with a hardware interrupt.

## Responsibilities

- Sample DS18B20 and MQ-135 and track per-sensor validity.
- Capture KY-026 transitions in a short, safe interrupt handler; process and report events outside the interrupt handler.
- Package readings using `../docs/data-contract.md`.
- Send telemetry to the Gateway over ESP-NOW.
- Track sequence numbers and make stale/lost messages detectable.

## Before hardware-specific implementation

- Confirm GPIO assignments and KY-026 output polarity.
- Confirm the exact ESP32 DevKit V1 revision and sensor module output voltages.
- Record wiring and power details in `../docs/`.
- Use a local ignored config for radio/network settings if needed; commit only templates with placeholder values.

# Gateway Firmware

Target board: ESP32 DevKit V1, 30-pin.

## Assigned inputs and outputs

Inputs:

- ESP-NOW telemetry from the Sensor Node: DS18B20/KY-001 temperature, MQ-135 raw reading, and KY-026 flame status/event.
- ACS712 5 A — DC charging current.
- DHT11 — ambient temperature and humidity.
- KY-004 push button — intended manual stop/reset control; exact press/hold and reset behavior must be agreed before implementation.

Output:

- MG90S 180-degree metal-gear servo, commanded to rotate about 90 degrees to operate the toggle switch and cut charging power to the demonstration power bank.

## Power arrangement

The project plan uses a breadboard power module and 9 V, 1 A adapter to provide a separate 5 V supply for the servo and MQ-135. Confirm actual module output and current capacity, common-ground requirements, and each signal's voltage compatibility before wiring. Never drive a servo from an ESP32 GPIO.

## Responsibilities

- Receive and validate Node messages; detect stale or missing data.
- Read ACS712 and DHT11 and maintain sensor validity.
- Apply the documented state logic and local actuator behavior independently of cloud availability.
- Publish telemetry to NETPIE and send configured notifications when network access is available.
- Report cut-off state and button events consistently with `../docs/data-contract.md`.

Keep credentials in ignored local configuration. Confirm GPIO pins, thresholds, calibration, servo travel limits, switch orientation, and the KY-004 interaction before implementation or live demonstration.

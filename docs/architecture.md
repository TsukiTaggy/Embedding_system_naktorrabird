# Architecture

## Confirmed hardware

The prototype uses two ESP32 DevKit V1 boards with 30 pins.

### Sensor Node

The Sensor Node reads three sensors:

- DS18B20 on the KY-001 module for battery-surface temperature.
- MQ-135 for gas/smoke readings.
- KY-026 flame sensor, with its digital signal connected to a hardware interrupt input.

The Node sends readings wirelessly to the Gateway over ESP-NOW.

### Gateway

The Gateway receives Sensor Node messages over ESP-NOW and reads:

- ACS712 5 A module for DC charging current.
- DHT11 for ambient temperature and humidity.

The Gateway also controls the MG90S 180-degree metal-gear servo. The servo rotates about 90 degrees to operate a toggle switch that disconnects charging power to the demonstration power bank. The KY-004 push button is intended for manual stop/reset; its exact interaction and reset behavior still need to be defined.

A breadboard power module and 9 V, 1 A adapter provide a separate 5 V supply for the servo and MQ-135. Confirm the module output, grounding, and sensor/bus voltage compatibility when wiring. Do not power the servo from an ESP32 GPIO.

## Planned data flow

1. The Sensor Node samples DS18B20 and MQ-135 readings and captures KY-026 flame events through its interrupt input.
2. The Node packages the readings and sends them to the Gateway over ESP-NOW.
3. The Gateway validates the received values, reads ACS712 and DHT11, determines the system state, and controls the local servo/button behavior.
4. When network connectivity is available, the Gateway publishes telemetry to NETPIE.
5. The NETPIE dashboard displays the latest state and sensor readings, with history and freshness/connectivity status where supported.
6. The Gateway may send configured notifications. Local monitoring and cut-off behavior must not depend on the dashboard or cloud connection.
7. The simulator uses the same data contract and state logic before hardware is connected and can supply test data for the dashboard.

## Planned software boundaries

- `firmware_node/`: DS18B20 and MQ-135 acquisition, KY-026 interrupt handling, message encoding, and ESP-NOW transmission.
- `firmware_gateway/`: ESP-NOW reception, ACS712 and DHT11 acquisition, state logic, servo and KY-004 handling, and optional cloud/notification adapters.
- `simulator/`: generated readings and repeatable normal, hazard, sensor-fault, and network-failure scenarios.
- `dashboard/`: NETPIE dashboard field mapping, setup notes, and safe-to-commit exported artifacts.
- `docs/`: architecture, data contract, wiring/pin map, decisions, and verification records.

## Dashboard responsibilities

The NETPIE dashboard should show system state, battery-surface temperature, gas/smoke reading, flame status, charging current, ambient temperature, and humidity. It should also show the Gateway-reported cut-off state and data freshness/connectivity where supported. Label each value with its unit or mark it as a raw sensor reading until calibrated. Show unavailable or stale values distinctly from zero.

Remote cut/reset controls are not part of the initial design. The physical KY-004 button behavior and any remote command path must be defined and tested before exposing reset or re-enable behavior.

## Decisions and implementation details still needed

- GPIO pin map for both boards and interrupt-capable pin selection for KY-026.
- ESP-NOW message structure, sampling rate, timeout, and loss/retry behavior.
- KY-004 interaction: separate stop and reset actions or a documented press/hold sequence; define whether reset can ever re-enable power.
- Toggle-switch orientation, servo travel limits, and how the Gateway confirms the switch position (if position feedback exists).
- State names, thresholds, filtering, trend window, and recovery rules.
- ACS712 calibration and ADC scaling; MQ-135 warm-up/calibration and interpretation; DS18B20 validity handling.
- Safe power wiring, common ground requirements, and voltage compatibility for every module.
- NETPIE project/device setup and supported telemetry/dashboard workflow.
- Notification channel and trigger rules.

This is a classroom prototype plan. It is not a certified battery-management or charging-protection system. Test the servo and toggle only in a safe, low-voltage demonstration setup.

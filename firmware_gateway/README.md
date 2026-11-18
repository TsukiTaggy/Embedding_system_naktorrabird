# Gateway Firmware

Place Gateway ESP32 source here. Suggested responsibilities:

- receive and validate Node messages
- read Gateway-local sensors
- calculate state and temperature trend, if adopted
- drive the local indicator/cut-off interface
- publish telemetry and send notifications when configured

Keep safety logic independent of cloud connectivity. Confirm state rules, thresholds, board pins, and actuator behavior with the team before hardware testing.

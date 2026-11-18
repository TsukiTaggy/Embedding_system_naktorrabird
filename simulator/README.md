# Simulator

The computer-based simulator should model the planned two-board system while using the same fields described in `../docs/data-contract.md`.

## Planned scenarios

- Normal temperature/current readings.
- Gradual and rapid battery temperature rise.
- Over-temperature state.
- MQ-135 raw reading changes and KY-026 flame event.
- Missing/stale Sensor Node message.
- Invalid sensor value and Gateway network loss.
- KY-004 stop/reset event and reported servo cut-off state (simulated only).

Begin with local output and dry-run behavior. Keep cloud publishing and external notifications optional. Never commit credentials. Sensor values and thresholds in simulations are for software behavior demonstrations, not validated safety limits.

# Simulator

A computer-based model of the two-board system (Sensor Node → ESP-NOW → Gateway). It produces Gateway aggregate telemetry messages that follow [`../docs/data-contract.md`](../docs/data-contract.md), so the dashboard and alert path can be built before the ESP32 boards arrive.

**Default mode is a local dry run.** The simulator prints readings, state changes, and messages, and never opens a network connection. It publishes to NETPIE only when `--publish` is given.

> Sensor values and thresholds are placeholders for exercising the software. They are **not** validated battery safety limits.

## Files

| File | Purpose |
| --- | --- |
| `virtual_gateway.py` | Command-line entry point: runs scenarios, logs, writes JSON lines, and optionally publishes |
| `safety_logic.py` | Gateway decision logic: dT/dt linear regression, state rules, hysteresis, latched power cut, button handling. Written to be ported to the Gateway firmware. |
| `scenarios.py` | Scripted, repeatable sensor and link profiles |
| `netpie_publisher.py` | Optional NETPIE MQTT publisher (only imported with `--publish`) |
| `thresholds.example.json` | Copy and edit to try other placeholder thresholds with `--thresholds` |
| `.env.example` | Template for NETPIE Device keys. Copy it to `.env`, which Git ignores. |
| `requirements.txt` | `paho-mqtt`, needed only for `--publish` |
| `tests/` | Unit tests (standard library `unittest`) |

## Requirements

- Python 3.9 or newer. Local runs and tests use only the standard library.
- To publish to NETPIE, install the requirements in a virtual environment (the `.venv/` folder is ignored by Git):

```powershell
python -m venv simulator\.venv
```

```powershell
simulator\.venv\Scripts\python -m pip install -r simulator\requirements.txt
```

## Run locally (no network)

Run from the repository root:

```powershell
python simulator\virtual_gateway.py --list
```

```powershell
python simulator\virtual_gateway.py --scenario rapid_rise --speed 0
```

Useful options:

| Option | Meaning |
| --- | --- |
| `--scenario NAME` | One of the scenarios below (default `normal`) |
| `--speed X` | `1` = real time (default), `5` = five times faster, `0` = no waiting |
| `--interval S` | Simulated seconds between messages (default `1.0`) |
| `--duration S` | Override the scenario length |
| `--quiet` | Print only state transitions and events |
| `--json` | Also print the full contract message every step |
| `--out run.jsonl` | Save every message as one JSON line |
| `--seed N` | Noise seed; the same seed gives identical output |
| `--thresholds FILE` | Override placeholder thresholds (keys as in `thresholds.example.json`) |
| `--sample FILE` | Print (or publish) one message file such as `docs/samples/gateway_hazard.json`, then exit |

## Scenarios

| Name | What happens | Expected result (placeholder thresholds) |
| --- | --- | --- |
| `normal` | Stable charging | `STARTING` → `NORMAL` |
| `gradual_rise` | Battery temperature rises 0.12 °C/s | `WARNING` by temperature at about t = 109 s, no `HAZARD` |
| `rapid_rise` | Temperature jumps 35 → 49 °C at 2 °C/s, then cools | `WARNING` → `HAZARD` by dT/dt; stays latched, power cut, current drops to ~0 |
| `over_temp` | Temperature climbs 0.3 °C/s to 58 °C | `WARNING` by dT/dt → `HAZARD` by temperature |
| `gas_flame` | Gas raw rises to warning level, then flame for 8 s | `WARNING` by gas → `HAZARD` by flame |
| `sensor_fault` | DS18B20 gives no reading for t = 20–35 s | `SENSOR_ERROR`; `temp_bat_c` is `null` (not 0); recovers to `NORMAL` |
| `node_stale` | ESP-NOW link lost for t = 20–35 s | `SENSOR_ERROR` once Node data is older than 5 s; recovers |
| `network_loss` | Gateway cloud link lost for t = 20–40 s | Local logic keeps running; messages are queued and replayed on reconnect |
| `button_reset` | Hazard with flame, then KY-004 events | RESET rejected while the flame is present, RESET accepted after, then STOP cuts power, RESET clears it |

## Decision rules (summary)

Full detail is in the `SafetyLogic` docstring in `safety_logic.py`.

1. `HAZARD` is **latched**. Power stays cut until a local **RESET** arrives while no hazard condition is present. A RESET during an active hazard is rejected and logged.
2. Hazard conditions: flame, battery temp ≥ `hazard_temp_c`, dT/dt ≥ `hazard_rate_c_per_s`, or gas raw ≥ `hazard_gas_raw`.
3. Missing battery temperature or stale Node data gives `SENSOR_ERROR`. Power is **not** cut automatically, because that behaviour is still a team decision.
4. `STARTING` is used only after boot, until the 10 s dT/dt window has enough samples.
5. `WARNING` clears only after `warning_clear_samples` consecutive clear samples (hysteresis).
6. STOP cuts power manually. RESET clears it when no hazard is present.

dT/dt is a least-squares slope over the last `rate_window_s` seconds of valid battery temperatures. It is `null` until `rate_min_samples` are available.

## Publish to NETPIE

1. Create the NETPIE Device `EV_Gateway` and set up the dashboard (see [`../dashboard/field-mapping.md`](../dashboard/field-mapping.md)).
2. Copy `simulator/.env.example` to `simulator/.env` and fill in the Device Client ID and Token (Secret is optional per the NETPIE docs). REST needs only the Client ID and Token. You can also set the environment variables `NETPIE_CLIENT_ID`, `NETPIE_TOKEN`, `NETPIE_SECRET` instead.
3. Run, for example:

```powershell
simulator\.venv\Scripts\python simulator\virtual_gateway.py --scenario gas_flame --publish
```

### Transports

| `--transport` | How | Status |
| --- | --- | --- |
| `rest` (default) | HTTPS Device API `api.netpie.io` (`PUT /v2/device/shadow/data`; queued messages are replayed with `PUT /v2/device/shadow/batch`). Standard library only. | **Tested on 2026-11-20.** The certificate is publicly trusted, so normal verification works. |
| `mqtt` | `mqtt.netpie.io` port **1884** (MQTTS; the manual lists 1884, not 8883), topic `@shadow/data/update`, QoS 1 | Tested only against a local stub broker. With the real broker, TLS verification **fails**: it presents certificates from a private "NEXPIE Device Broker" CA that is not in the system trust store, and several different leaf certificates rotate between connections. Use `--ca-file` once the team obtains NEXPIE's CA certificate (for example from contact@nexpie.com). The Gateway firmware will face the same issue. |

Notes for REST:

- Turn on the Device's **LivenessTTL** (10 s) in the NETPIE portal so the REST `/status` API reports online for a few seconds after each write.
- The dashboard's own online indicator follows MQTT connections only, so it shows offline during REST runs. Everything else updates normally.
- Writing `null` removes the field from the Shadow. The dashboard handles this.
- Each message is one Shadow write. The free quota is 500,000 writes per month, so keep long runs short (see `dashboard/field-mapping.md` section 2).

Never commit `simulator/.env` or any real Token or Secret.

## Tests

```powershell
python -m unittest discover -s simulator/tests -v
```

The tests check the regression and state rules, every scenario's expected outcome, that every generated message and every file in `docs/samples/` has exactly the contract fields, and the NETPIE payload wrapper.

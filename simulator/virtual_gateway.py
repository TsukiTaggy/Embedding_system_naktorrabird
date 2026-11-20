"""Virtual Gateway: simulates the Sensor Node + Gateway and emits contract messages.

Default mode is LOCAL ONLY (dry run): it prints readings, state changes and
the messages it would publish, and never opens a network connection.
Use --publish to send to NETPIE (credentials from env vars or simulator/.env).

Examples:
  python simulator/virtual_gateway.py --list
  python simulator/virtual_gateway.py --scenario rapid_rise --speed 0
  python simulator/virtual_gateway.py --scenario rapid_rise --json --out run.jsonl --speed 0
  python simulator/virtual_gateway.py --sample docs/samples/gateway_hazard.json
  python simulator/virtual_gateway.py --scenario gas_flame --publish

Message fields follow docs/data-contract.md (Gateway aggregate telemetry).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from safety_logic import GatewayInputs, SafetyLogic, Thresholds  # noqa: E402
from scenarios import SCENARIOS, Scenario  # noqa: E402

SCHEMA_VERSION = 1
GAS_ADC_MAX = 4095          # ESP32 12-bit ADC; verify against the final wiring
BOOT_OFFSET_MS = 5000       # pretend the Gateway booted 5 s before the scenario starts


class VirtualGateway:
    """Models the Node -> ESP-NOW -> Gateway path and builds contract messages."""

    def __init__(self, scenario: Scenario, thresholds: Thresholds, seed: int = 42, interval_s: float = 1.0):
        self.scenario = scenario
        self.interval_s = interval_s
        self.rng = random.Random(seed)
        self.logic = SafetyLogic(thresholds)
        self.power_cut = False
        # Node-side state as seen by the Gateway
        self.node_sequence = 0
        self.last_node_ms: Optional[int] = None
        self.last_node_latency_ms = 0
        self.node_values = {"temp_bat_c": None, "gas_raw": None, "flame_detected": None, "temp_ok": False}

    def _receive_node(self, now_ms: int, world) -> None:
        if not world.node_link_up:
            return
        self.node_sequence += 1
        self.last_node_ms = now_ms
        self.last_node_latency_ms = self.rng.randint(300, 600)
        self.node_values = {
            "temp_bat_c": round(world.temp_bat_c, 2) if world.temp_sensor_ok else None,
            "gas_raw": int(max(0, min(GAS_ADC_MAX, round(world.gas_raw)))),
            "flame_detected": bool(world.flame),
            "temp_ok": world.temp_sensor_ok,
        }

    def steps(self, duration_s: float) -> Iterator[tuple]:
        n_steps = int(round(duration_s / self.interval_s)) + 1
        for k in range(n_steps):
            t = k * self.interval_s
            now_ms = BOOT_OFFSET_MS + int(round(t * 1000))
            world = self.scenario.world(t, self.rng, self.interval_s)
            self._receive_node(now_ms, world)

            node_age_ms = None
            if self.last_node_ms is not None:
                node_age_ms = now_ms - self.last_node_ms + self.last_node_latency_ms

            measured_current = (0.0 + self.rng.gauss(0, 0.01)) if self.power_cut else world.charge_current_a
            current_a = round(measured_current, 2)
            temp_ambient_c = round(world.temp_ambient_c, 1)
            humidity_pct = round(world.humidity_pct, 1)
            nv = self.node_values

            decision = self.logic.step(GatewayInputs(
                now_ms=now_ms,
                temp_bat_c=nv["temp_bat_c"],
                gas_raw=nv["gas_raw"],
                flame_detected=nv["flame_detected"],
                node_age_ms=node_age_ms,
                temp_ambient_c=temp_ambient_c,
                humidity_pct=humidity_pct,
                current_a=current_a,
                button_event=world.button,
            ))
            self.power_cut = decision.power_cut

            message = {
                "schema_version": SCHEMA_VERSION,
                "timestamp_ms": now_ms,
                "node_sequence": self.node_sequence or None,
                "node_age_ms": node_age_ms,
                "temp_bat_c": nv["temp_bat_c"],
                "gas_raw": nv["gas_raw"],
                "flame_detected": nv["flame_detected"],
                "temp_ambient_c": temp_ambient_c,
                "humidity_pct": humidity_pct,
                "current_a": current_a,
                "temp_rate_c_per_s": decision.temp_rate_c_per_s,
                "state": decision.state,
                "power_cut": decision.power_cut,
                "button_event": world.button,
                # DRAFT validity shape (see dashboard/field-mapping.md section 7)
                "validity": {
                    "node_link": decision.node_link_ok,
                    "temp_bat": decision.node_link_ok and nv["temp_bat_c"] is not None,
                    "gas": decision.node_link_ok and nv["gas_raw"] is not None,
                    "flame": decision.node_link_ok and nv["flame_detected"] is not None,
                    "ambient": True,
                    "current": True,
                },
            }
            yield t, world, decision, message


def _fmt(v, spec: str, none: str = "--") -> str:
    return none if v is None else format(v, spec)


def format_line(t: float, m: dict, cloud_up: bool) -> str:
    return (
        f"t={t:6.1f}s {m['state']:<12} "
        f"bat={_fmt(m['temp_bat_c'], '5.1f')}C "
        f"dT/dt={_fmt(m['temp_rate_c_per_s'], '+5.2f', '  -- ')} "
        f"gas={_fmt(m['gas_raw'], '4d', '  --')} "
        f"flame={'--' if m['flame_detected'] is None else int(m['flame_detected'])} "
        f"I={m['current_a']:5.2f}A "
        f"amb={m['temp_ambient_c']:4.1f}C/{m['humidity_pct']:4.1f}% "
        f"cut={int(m['power_cut'])} "
        f"node_age={_fmt(None if m['node_age_ms'] is None else m['node_age_ms'] / 1000, '4.1f')}s"
        + ("" if cloud_up else " [cloud DOWN]")
        + (f" button={m['button_event']}" if m["button_event"] else "")
    )


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Virtual Gateway simulator for the Charging Safety Alarm project.")
    p.add_argument("--list", action="store_true", help="list scenarios and exit")
    p.add_argument("--scenario", default="normal", choices=sorted(SCENARIOS), help="scenario to run")
    p.add_argument("--duration", type=float, help="override scenario duration (simulated seconds)")
    p.add_argument("--interval", type=float, default=1.0, help="simulated seconds per message (default 1.0)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="real-time factor: 1 = real time, 2 = twice as fast, 0 = no waiting (default 1)")
    p.add_argument("--seed", type=int, default=42, help="random seed for repeatable noise (default 42)")
    p.add_argument("--thresholds", type=Path, help="JSON file overriding placeholder thresholds")
    p.add_argument("--json", action="store_true", help="print the full contract message every step")
    p.add_argument("--quiet", action="store_true", help="print only state transitions and events")
    p.add_argument("--out", type=Path, help="write every message as one JSON line to this file")
    p.add_argument("--sample", type=Path, help="send/print one message file (e.g. docs/samples/*.json) and exit")
    net = p.add_argument_group("NETPIE (only used with --publish)")
    net.add_argument("--publish", action="store_true", help="publish to NETPIE (default: local dry run)")
    net.add_argument("--transport", choices=("rest", "mqtt"), default="rest",
                     help="rest = HTTPS Device API (default, verified TLS); mqtt = MQTT broker")
    net.add_argument("--env-file", type=Path, default=HERE / ".env", help="credentials file (default simulator/.env)")
    net.add_argument("--host", default=None, help="MQTT host (default mqtt.netpie.io)")
    net.add_argument("--port", type=int, default=None, help="MQTT port (default 1884 TLS, 1883 with --no-tls)")
    net.add_argument("--no-tls", action="store_true", help="use plain MQTT (not recommended)")
    net.add_argument("--ca-file", default=None, help="CA certificate (PEM) that signs the MQTT broker certificate")
    return p.parse_args(argv)


def make_publisher(args):
    from netpie_publisher import (DEFAULT_HOST, DEFAULT_PLAIN_PORT, DEFAULT_TLS_PORT,
                                  NetpiePublisher, NetpieRestPublisher, load_credentials)
    creds = load_credentials(args.env_file)
    missing = [k for k in ("client_id", "token") if not creds[k]]
    if missing:
        raise SystemExit(
            f"Missing NETPIE credentials: {', '.join('NETPIE_' + k.upper() for k in missing)}. "
            f"Set them as environment variables or in {args.env_file} (copy simulator/.env.example)."
        )
    if args.transport == "rest":
        pub = NetpieRestPublisher(creds["client_id"], creds["token"])
        pub.connect()
        return pub
    port = args.port or (DEFAULT_PLAIN_PORT if args.no_tls else DEFAULT_TLS_PORT)
    pub = NetpiePublisher(creds["client_id"], creds["token"], creds["secret"],
                          host=args.host or DEFAULT_HOST, port=port, use_tls=not args.no_tls,
                          ca_file=args.ca_file)
    pub.connect()
    return pub


def run_sample(args) -> int:
    message = json.loads(args.sample.read_text(encoding="utf-8"))
    from netpie_publisher import build_envelope
    envelope = build_envelope(message)
    print(json.dumps(envelope, indent=2, ensure_ascii=False))
    if not args.publish:
        print("[dry-run] not published (add --publish to send to NETPIE)")
        return 0
    pub = make_publisher(args)
    try:
        ok = pub.publish(envelope)
        time.sleep(0.5)
        print("[netpie] published" if ok else "[netpie] publish FAILED")
        return 0 if ok else 1
    finally:
        pub.close()


def run_scenario(args) -> int:
    scenario = SCENARIOS[args.scenario]
    thresholds = Thresholds()
    if args.thresholds:
        thresholds = Thresholds.from_dict(json.loads(args.thresholds.read_text(encoding="utf-8")))
    duration = args.duration if args.duration is not None else scenario.duration_s
    gw = VirtualGateway(scenario, thresholds, seed=args.seed, interval_s=args.interval)

    mode = "PUBLISH to NETPIE" if args.publish else "dry run (local only)"
    print(f"Scenario '{scenario.name}': {scenario.description}")
    print(f"Duration {duration:g}s, interval {args.interval:g}s, speed {args.speed:g}x, seed {args.seed}, mode: {mode}")
    print("Thresholds are PLACEHOLDERS, not validated safety limits.\n")

    pub = make_publisher(args) if args.publish else None
    out = args.out.open("w", encoding="utf-8") if args.out else None
    cloud_was_up = True
    queued_dry = 0
    epoch_start_ms = int(time.time() * 1000)
    wall_start = time.monotonic()
    try:
        for t, world, decision, message in gw.steps(duration):
            if args.speed > 0:
                delay = wall_start + t / args.speed - time.monotonic()
                if delay > 0:
                    time.sleep(delay)

            if decision.transition:
                print(f"  >> t={t:.1f}s {decision.transition}")
            for reason in decision.reasons:
                if (reason.startswith("RESET") or reason.startswith("manual")) and \
                        not (decision.transition and reason in decision.transition):
                    print(f"  >> t={t:.1f}s {reason}")

            # Cloud link handling (store-and-forward demonstration)
            if world.cloud_link_up != cloud_was_up:
                print(f"  >> t={t:.1f}s cloud link {'RESTORED' if world.cloud_link_up else 'LOST'}")
                if pub:
                    (pub.go_online if world.cloud_link_up else pub.go_offline)()
                if world.cloud_link_up:
                    if pub:
                        print(f"  >> replaying {pub.flush_queue()} queued message(s) to NETPIE")
                    else:
                        print(f"  >> [dry-run] would replay {queued_dry} queued message(s)")
                    queued_dry = 0
                cloud_was_up = world.cloud_link_up

            if not args.quiet:
                print(format_line(t, message, world.cloud_link_up))
            if args.json:
                print(json.dumps(message, ensure_ascii=False))
            if out:
                out.write(json.dumps(message, ensure_ascii=False) + "\n")

            if pub:
                from netpie_publisher import build_envelope
                # Wall-clock time of this sample, so replayed data lands at the right time in the Feed.
                envelope = build_envelope(message, epoch_start_ms + int(t * 1000))
                if world.cloud_link_up:
                    if not pub.publish(envelope):
                        print(f"  !! t={t:.1f}s publish failed; queued")
                        pub.queue.append(envelope)
                else:
                    pub.queue.append(envelope)
            elif not world.cloud_link_up:
                queued_dry += 1
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        if out:
            out.close()
        if pub:
            pub.close()
    print(f"\nFinished. Final state: {gw.logic.state}, power_cut={gw.power_cut}")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list:
        for s in SCENARIOS.values():
            print(f"{s.name:<14} {s.duration_s:>5g}s  {s.description}")
        return 0
    if args.sample:
        return run_sample(args)
    return run_scenario(args)


if __name__ == "__main__":
    sys.exit(main())

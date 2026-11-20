"""Tests for the simulator. Run from the repo root:

    python -m unittest discover -s simulator/tests -v
"""

import json
import sys
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parent
sys.path.insert(0, str(SIM))

from netpie_publisher import build_envelope, load_env_file  # noqa: E402
from safety_logic import (HAZARD, NORMAL, SENSOR_ERROR, STARTING, WARNING,  # noqa: E402
                          GatewayInputs, SafetyLogic, Thresholds, linear_regression_slope)
from scenarios import SCENARIOS  # noqa: E402
from virtual_gateway import VirtualGateway  # noqa: E402

CONTRACT_FIELDS = {
    "schema_version", "timestamp_ms", "node_sequence", "node_age_ms", "temp_bat_c", "gas_raw",
    "flame_detected", "temp_ambient_c", "humidity_pct", "current_a", "temp_rate_c_per_s",
    "state", "power_cut", "button_event", "validity",
}


def run(name, **kw):
    gw = VirtualGateway(SCENARIOS[name], Thresholds(), seed=kw.get("seed", 42))
    return [(t, d, m) for t, _w, d, m in gw.steps(SCENARIOS[name].duration_s)]


def inputs(now_s, temp=31.5, gas=800, flame=False, age=400, button=None):
    return GatewayInputs(now_ms=int(now_s * 1000), temp_bat_c=temp, gas_raw=gas, flame_detected=flame,
                         node_age_ms=age, temp_ambient_c=28.0, humidity_pct=64.0, current_a=1.4,
                         button_event=button)


class TestRegression(unittest.TestCase):
    def test_slope_of_line(self):
        pts = [(t, 30 + 0.5 * t) for t in range(10)]
        self.assertAlmostEqual(linear_regression_slope(pts), 0.5)

    def test_slope_undefined(self):
        self.assertIsNone(linear_regression_slope([(1, 2)]))
        self.assertIsNone(linear_regression_slope([(1, 2), (1, 3)]))


class TestSafetyLogic(unittest.TestCase):
    def warm_up(self, logic, n=6):
        for k in range(n):
            d = logic.step(inputs(k))
        return d

    def test_starting_then_normal(self):
        logic = SafetyLogic()
        self.assertEqual(logic.step(inputs(0)).state, STARTING)
        self.assertEqual(self.warm_up(logic).state, NORMAL)

    def test_hazard_latches_until_reset(self):
        logic = SafetyLogic()
        self.warm_up(logic)
        d = logic.step(inputs(6, flame=True))
        self.assertEqual((d.state, d.power_cut), (HAZARD, True))
        # Flame gone, no reset -> still latched
        d = logic.step(inputs(7))
        self.assertEqual((d.state, d.power_cut), (HAZARD, True))
        # Reset while flame present -> rejected
        d = logic.step(inputs(8, flame=True, button="RESET"))
        self.assertEqual(d.state, HAZARD)
        self.assertIn("RESET rejected: hazard still present", d.reasons)
        # Reset when clear -> accepted
        d = logic.step(inputs(9, button="RESET"))
        self.assertEqual((d.state, d.power_cut), (NORMAL, False))

    def test_warning_hysteresis(self):
        t = Thresholds()
        logic = SafetyLogic(t)
        self.warm_up(logic)
        self.assertEqual(logic.step(inputs(6, gas=t.warn_gas_raw)).state, WARNING)
        for k in range(t.warning_clear_samples - 1):
            self.assertEqual(logic.step(inputs(7 + k)).state, WARNING)
        self.assertEqual(logic.step(inputs(7 + t.warning_clear_samples)).state, NORMAL)

    def test_missing_temperature_is_sensor_error_without_cut(self):
        logic = SafetyLogic()
        self.warm_up(logic)
        d = logic.step(inputs(6, temp=None))
        self.assertEqual((d.state, d.power_cut, d.temp_rate_c_per_s), (SENSOR_ERROR, False, None))

    def test_stale_node_ignores_node_values(self):
        logic = SafetyLogic()
        self.warm_up(logic)
        d = logic.step(inputs(6, flame=True, age=Thresholds().node_stale_ms + 1))
        self.assertEqual(d.state, SENSOR_ERROR)
        self.assertFalse(d.node_link_ok)

    def test_manual_stop_and_reset(self):
        logic = SafetyLogic()
        self.warm_up(logic)
        self.assertTrue(logic.step(inputs(6, button="STOP")).power_cut)
        self.assertTrue(logic.step(inputs(7)).power_cut)
        self.assertFalse(logic.step(inputs(8, button="RESET")).power_cut)

    def test_threshold_override_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            Thresholds.from_dict({"warn_temp": 40})

    def test_example_thresholds_file_matches_defaults(self):
        data = json.loads((SIM / "thresholds.example.json").read_text(encoding="utf-8"))
        self.assertEqual(Thresholds.from_dict(data), Thresholds())


class TestScenarios(unittest.TestCase):
    def states(self, name):
        return [d.state for _t, d, _m in run(name)]

    def test_every_message_matches_contract(self):
        for name in SCENARIOS:
            for _t, _d, m in run(name):
                self.assertEqual(set(m), CONTRACT_FIELDS, name)
                json.dumps(m)  # serialisable

    def test_repeatable_with_same_seed(self):
        self.assertEqual([m for *_x, m in run("rapid_rise")], [m for *_x, m in run("rapid_rise")])

    def test_expected_outcomes(self):
        self.assertNotIn(WARNING, self.states("normal"))
        self.assertIn(WARNING, self.states("gradual_rise"))
        self.assertNotIn(HAZARD, self.states("gradual_rise"))
        for name in ("rapid_rise", "over_temp", "gas_flame"):
            self.assertEqual(self.states(name)[-1], HAZARD, name)
        self.assertIn(SENSOR_ERROR, self.states("sensor_fault"))
        self.assertIn(SENSOR_ERROR, self.states("node_stale"))
        self.assertEqual(self.states("sensor_fault")[-1], NORMAL)

    def test_sensor_fault_sends_null_not_zero(self):
        faulty = [m for t, _d, m in run("sensor_fault") if 20 <= t < 35]
        self.assertTrue(all(m["temp_bat_c"] is None and m["validity"]["temp_bat"] is False for m in faulty))

    def test_power_cut_drops_current(self):
        rows = run("rapid_rise")
        first_cut = next(i for i, (_t, d, _m) in enumerate(rows) if d.power_cut)
        self.assertTrue(all(abs(m["current_a"]) < 0.1 for _t, _d, m in rows[first_cut + 1:]))

    def test_button_reset_sequence(self):
        rows = {t: d for t, d, _m in run("button_reset")}
        self.assertIn("RESET rejected: hazard still present", rows[28.0].reasons)
        self.assertEqual((rows[50.0].state, rows[50.0].power_cut), (NORMAL, False))
        self.assertTrue(rows[65.0].power_cut)
        self.assertFalse(rows[78.0].power_cut)


class TestSamplesAndEnvelope(unittest.TestCase):
    def test_samples_match_contract(self):
        files = sorted((REPO / "docs" / "samples").glob("*.json"))
        self.assertTrue(files)
        for f in files:
            self.assertEqual(set(json.loads(f.read_text(encoding="utf-8"))), CONTRACT_FIELDS, f.name)

    def test_envelope(self):
        self.assertEqual(build_envelope({"a": 1}), {"data": {"a": 1}})
        self.assertEqual(build_envelope({"a": 1}, 1700000000000), {"data": {"a": 1}, "timestamp": 1700000000000})

    def test_rest_publisher_requests(self):
        from netpie_publisher import NetpieRestPublisher
        calls = []
        pub = NetpieRestPublisher("cid", "tok", log=lambda *_: None)
        pub._request = lambda method, path, body=None: (calls.append((method, path, body)) or (200, {"alias": "EV_Gateway"}))
        pub.connect()
        self.assertTrue(pub.publish(build_envelope({"state": "NORMAL"}, 1700000000000)))
        self.assertEqual(calls[-1], ("PUT", "/shadow/data", {"data": {"state": "NORMAL"}}))
        pub.go_offline()
        self.assertFalse(pub.publish(build_envelope({"state": "WARNING"})))
        pub.queue += [build_envelope({"a": 1}, 1700000001000), build_envelope({"a": 2}, 1700000002000)]
        pub.go_online()
        self.assertEqual(pub.flush_queue(), 2)
        self.assertEqual(calls[-1], ("PUT", "/shadow/batch", {"merged": True, "batch": [
            {"data": {"a": 1}, "ts": 1700000001000}, {"data": {"a": 2}, "ts": 1700000002000}]}))
        self.assertEqual(pub.queue, [])
        self.assertEqual(pub.auth, "Device cid:tok")

    def test_dashboard_layout_has_no_secrets_and_valid_fields(self):
        layout = json.loads((REPO / "dashboard" / "netpie_dashboard_layout.json").read_text(encoding="utf-8"))
        text = json.dumps(layout)
        self.assertNotIn("dashtoken", text)
        self.assertNotIn("datasources", layout)
        import re
        used = set(re.findall(r'\[\\"shadow\\"\]\[\\"(\w+)\\"\]', text))
        used |= {f for p in layout["panes"] for w in p["widgets"] if w["type"] == "Chart"
                 for f in w["settings"]["filter"].split(",")}
        self.assertTrue(used)
        self.assertLessEqual(used, CONTRACT_FIELDS)
        # NETPIE evaluates the reference syntax even inside HTML comments
        for p in layout["panes"]:
            for w in p["widgets"]:
                if w["type"] == "html":
                    for comment in re.findall(r"<!--.*?-->", w["settings"]["html"], flags=re.S):
                        self.assertNotIn("${", comment)

    def test_env_file_parser(self):
        values = load_env_file(SIM / ".env.example")
        self.assertEqual(set(values), {"NETPIE_CLIENT_ID", "NETPIE_TOKEN", "NETPIE_SECRET"})


if __name__ == "__main__":
    unittest.main()

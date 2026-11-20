"""Optional NETPIE 2020 MQTT publisher for the simulator.

Only imported when --publish is used, so local runs need no third-party
packages and never touch the network.

NETPIE connection parameters (https://docs.netpie.io/mqtt-api.html):
  host mqtt.netpie.io, port 1883 (mqtt) / 1884 (mqtts),
  client id = Device Client ID, username = Device Token,
  password = Device Secret (documented as optional).
Shadow update topic: @shadow/data/update with payload {"data": {...}} and an
optional top-level "timestamp" (epoch ms). A timestamp older than the Shadow's
latest value is stored in the Feed only, which is how queued messages are
replayed after a simulated network loss.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

SHADOW_UPDATE_TOPIC = "@shadow/data/update"
DEFAULT_HOST = "mqtt.netpie.io"
DEFAULT_TLS_PORT = 1884
DEFAULT_PLAIN_PORT = 1883


def load_env_file(path: Path) -> Dict[str, str]:
    """Minimal KEY=VALUE reader for the ignored simulator/.env file."""
    values: Dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_credentials(env_file: Path) -> Dict[str, Optional[str]]:
    file_values = load_env_file(env_file)

    def get(name: str) -> Optional[str]:
        return os.environ.get(name) or file_values.get(name) or None

    return {
        "client_id": get("NETPIE_CLIENT_ID"),
        "token": get("NETPIE_TOKEN"),
        "secret": get("NETPIE_SECRET"),
    }


def build_envelope(message: dict, timestamp_epoch_ms: Optional[int] = None) -> dict:
    envelope = {"data": message}
    if timestamp_epoch_ms is not None:
        envelope["timestamp"] = int(timestamp_epoch_ms)
    return envelope


class NetpiePublisher:
    def __init__(self, client_id: str, token: str, secret: Optional[str] = None,
                 host: str = DEFAULT_HOST, port: int = DEFAULT_TLS_PORT, use_tls: bool = True,
                 ca_file: Optional[str] = None, log=print):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise SystemExit(
                "paho-mqtt is not installed. Run: pip install -r simulator/requirements.txt"
            ) from exc

        self._mqtt = mqtt
        self.host, self.port, self.log = host, port, log
        self._connected = threading.Event()
        self.queue: List[dict] = []

        if hasattr(mqtt, "CallbackAPIVersion"):  # paho-mqtt >= 2.0
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        else:  # paho-mqtt 1.x
            self.client = mqtt.Client(client_id=client_id)
        self.client.username_pw_set(token, secret or None)
        if use_tls:
            # Certificate verification stays on. mqtt.netpie.io uses a private
            # "NEXPIE Device Broker" CA, so pass that CA's PEM via ca_file once obtained.
            self.client.tls_set(ca_certs=ca_file)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    # paho 1.x and 2.x pass different argument counts; accept both.
    def _on_connect(self, client, userdata, flags, reason_code, *args):
        ok = (reason_code == 0) if isinstance(reason_code, int) else not reason_code.is_failure
        if ok:
            self._connected.set()
            self.log(f"[netpie] connected to {self.host}:{self.port}")
        else:
            self.log(f"[netpie] connection refused: {reason_code}")

    def _on_disconnect(self, client, userdata, *args):
        self._connected.clear()
        self.log("[netpie] disconnected")

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def connect(self, timeout_s: float = 10.0) -> None:
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()
        if not self._connected.wait(timeout_s):
            self.client.loop_stop()
            raise SystemExit(
                f"[netpie] could not connect to {self.host}:{self.port} within {timeout_s:.0f} s. "
                "Check the Device credentials and that the Device is enabled."
            )

    def go_offline(self) -> None:
        """Simulate Gateway Wi-Fi loss: drop the MQTT connection."""
        if self.connected:
            self.client.disconnect()
            self.client.loop_stop()

    def go_online(self) -> None:
        if not self.connected:
            self.client.reconnect()
            self.client.loop_start()
            self._connected.wait(10.0)

    def publish(self, envelope: dict, timeout_s: float = 5.0) -> bool:
        """Publish with QoS 1 and wait for the broker's acknowledgement.

        Waiting keeps delivery honest: a message only counts as sent once NETPIE
        has acknowledged it, so nothing is silently lost when the simulated
        Wi-Fi drops right after a publish.
        """
        if not self.connected:
            return False
        try:
            info = self.client.publish(SHADOW_UPDATE_TOPIC, json.dumps(envelope), qos=1)
            if info.rc != 0:
                return False
            info.wait_for_publish(timeout_s)
            return info.is_published()
        except (RuntimeError, ValueError):
            return False

    def flush_queue(self) -> int:
        """Replay queued envelopes (oldest first). Returns the number sent."""
        sent = 0
        while self.queue and self.connected:
            if not self.publish(self.queue[0]):
                break
            self.queue.pop(0)
            sent += 1
            time.sleep(0.05)
        return sent

    def close(self) -> None:
        self.go_offline()


# --- REST transport -----------------------------------------------------------

REST_BASE = "https://api.netpie.io/v2/device"


class NetpieRestPublisher:
    """Publish over the NETPIE Device REST API (HTTPS, standard library only).

    api.netpie.io uses a publicly trusted certificate, so normal certificate
    verification works. The MQTTS broker (mqtt.netpie.io:1884) presents
    certificates from a private "NEXPIE Device Broker" CA that is not in the
    system trust store, which is why REST is the simulator's default transport.

    REST calls do not keep a connection open. For the dashboard's online status
    (#["EV_Gateway"]["status"]) enable the Device's LivenessTTL so NETPIE keeps
    it "online" for a few seconds after each call.

    Endpoints (https://docs.netpie.io/device-api.html):
      PUT  /shadow/data   merge {"data": {...}}
      PUT  /shadow/batch  merge {"batch": [{"data": {...}, "ts": epoch_ms}, ...], "merged": true}
      GET  /status        credential check
    """

    def __init__(self, client_id: str, token: str, base_url: str = REST_BASE, log=print, timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.auth = f"Device {client_id}:{token}"
        self.log = log
        self.timeout_s = timeout_s
        self.queue: List[dict] = []
        self._online = False

    def _request(self, method: str, path: str, body: Optional[dict] = None):
        import urllib.request
        import urllib.error
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")[:300]
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return None, str(exc)

    @property
    def connected(self) -> bool:
        return self._online

    def connect(self, timeout_s: float = 10.0) -> None:
        status, body = self._request("GET", "/status")
        if status != 200:
            raise SystemExit(f"[netpie] REST credential check failed ({status}): {body}")
        self._online = True
        self.log(f"[netpie] REST API reachable ({self.base_url}), Device '{body.get('alias')}'")

    def go_offline(self) -> None:
        """Simulate Gateway Wi-Fi loss: stop sending (LivenessTTL then expires)."""
        self._online = False

    def go_online(self) -> None:
        self._online = True

    def publish(self, envelope: dict) -> bool:
        if not self._online:
            return False
        status, body = self._request("PUT", "/shadow/data", {"data": envelope["data"]})
        if status != 200:
            self.log(f"[netpie] shadow update failed ({status}): {body}")
        return status == 200

    def flush_queue(self) -> int:
        """Replay queued envelopes in one batch call with their original timestamps."""
        if not self.queue or not self._online:
            return 0
        batch = [{"data": e["data"], "ts": e.get("timestamp", 0)} for e in self.queue]
        status, body = self._request("PUT", "/shadow/batch", {"batch": batch, "merged": True})
        if status != 200:
            self.log(f"[netpie] batch replay failed ({status}): {body}")
            return 0
        sent = len(self.queue)
        self.queue.clear()
        return sent

    def close(self) -> None:
        self._online = False

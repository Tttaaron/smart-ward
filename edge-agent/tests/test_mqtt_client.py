"""MQTT topic routing and envelope regression tests."""

import json
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# The repository's edge requirements provide Paho. Keep the unit test runnable
# in the lightweight host environment used for the other fusion tests.
try:
    import paho.mqtt.client  # noqa: F401
except ModuleNotFoundError:
    paho_module = types.ModuleType("paho")
    mqtt_module = types.ModuleType("paho.mqtt.client")

    class _FakeMqttClient:
        def __init__(self, *args, **kwargs):
            pass

    mqtt_module.Client = _FakeMqttClient
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_package.client = mqtt_module
    paho_module.mqtt = mqtt_package
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_module

from mqtt_client import MqttClient


class MqttClientTest(unittest.TestCase):
    def setUp(self):
        self.client = MqttClient("W-01", "EDGE-W01-B01", "localhost")

    def _message(self, topic, payload=None):
        return SimpleNamespace(
            topic=topic,
            payload=json.dumps(payload or {"payload": {"ok": True}}).encode(),
        )

    def test_config_topic_dispatches_to_callback(self):
        callback = Mock()
        self.client.set_config_callback(callback)

        self.client._on_message(
            None,
            None,
            self._message("node/EDGE-W01-B01/config/set", {"payload": {"device": "light"}}),
        )

        callback.assert_called_once_with({"payload": {"device": "light"}})

    def test_inference_response_topic_dispatches_to_callback(self):
        callback = Mock()
        self.client.set_inference_response_callback(callback)

        self.client._on_message(
            None,
            None,
            self._message(
                "node/EDGE-W01-B01/inference/response",
                {"payload": {"event_id": "evt-1", "judgment": "confirm"}},
            ),
        )

        callback.assert_called_once_with(
            {"payload": {"event_id": "evt-1", "judgment": "confirm"}}
        )

    def test_topics_for_other_node_are_ignored(self):
        callback = Mock()
        self.client.set_config_callback(callback)

        self.client._on_message(
            None,
            None,
            self._message("node/EDGE-W01-B02/config/set"),
        )

        callback.assert_not_called()

    def test_event_envelope_contains_payload_event_id(self):
        self.client.connected = True
        self.client.client.publish = Mock()
        event = {"event_id": "evt-1", "event_type": "fall_suspected"}

        self.assertTrue(self.client.publish_event(event))

        args, kwargs = self.client.client.publish.call_args
        envelope = json.loads(args[1])
        self.assertEqual(args[0], "ward/W-01/node/EDGE-W01-B01/event")
        self.assertEqual(envelope["event_id"], "evt-1")
        self.assertEqual(envelope["payload"], event)
        self.assertEqual(kwargs["qos"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

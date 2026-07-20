import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "spatialble"))

from spatialble_config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD


def test_defaults():
    assert MQTT_BROKER == "localhost"
    assert MQTT_PORT == 1883
    assert MQTT_USERNAME == ""
    assert MQTT_PASSWORD == ""


def test_env_override():
    os.environ["SPATIALBLE_MQTT_BROKER"] = "10.0.0.1"
    os.environ["SPATIALBLE_MQTT_USERNAME"] = "test_user"
    # Reload module
    import importlib
    import spatialble_config
    importlib.reload(spatialble_config)
    assert spatialble_config.MQTT_BROKER == "10.0.0.1"
    assert spatialble_config.MQTT_USERNAME == "test_user"
    del os.environ["SPATIALBLE_MQTT_BROKER"]
    del os.environ["SPATIALBLE_MQTT_USERNAME"]
    importlib.reload(spatialble_config)

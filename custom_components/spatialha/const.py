import json
from pathlib import Path

DOMAIN = "spatialha"

with open(Path(__file__).parent / "manifest.json") as f:
    manifest = json.load(f)

VERSION = manifest["version"]

CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_MQTT_PORT = 1883
DEFAULT_UPDATE_INTERVAL = 5

MQTT_TOPIC = "spatialble/#"

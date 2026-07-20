import os

MQTT_BROKER = os.environ.get("SPATIALBLE_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("SPATIALBLE_MQTT_PORT", "1883"))
MQTT_USERNAME = os.environ.get("SPATIALBLE_MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("SPATIALBLE_MQTT_PASSWORD", "")

HEARTBEAT_INTERVAL = 10.0

OTA_PORT = 8765
OTA_UPLOAD_PATH = "/root/spatialble_server.py"
OTA_RESTART_CMD = ["systemctl", "restart", "spatialble_server"]

# MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_USERNAME = None
MQTT_PASSWORD = None

# BLE scanning
HEARTBEAT_INTERVAL = 10.0

# OTA
OTA_PORT = 8765
OTA_UPLOAD_PATH = "/root/spatialble_server.py"
OTA_RESTART_CMD = ["systemctl", "restart", "spatialble_server"]

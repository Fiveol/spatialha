"""ESPHome component registration for SpatialBLE BLE -> MQTT bridge."""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import mqtt, esp32_ble_tracker
from esphome.const import CONF_ID, CONF_TOPIC

DEPENDENCIES = ["mqtt", "esp32_ble_tracker"]

spatialble_ns = cg.esphome_ns.namespace("spatialble")
SpatialBLEServer = spatialble_ns.class_(
    "SpatialBLEServer", cg.Component, esp32_ble_tracker.ESPBTDeviceListener
)

CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(SpatialBLEServer),
            cv.Optional(CONF_TOPIC, default="spatialble"): cv.string,
            cv.Optional(
                CONF_HEARTBEAT_INTERVAL, default="10s"
            ): cv.positive_time_period_milliseconds,
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(esp32_ble_tracker.ESP_BLE_DEVICE_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await esp32_ble_tracker.register_ble_device(var, config)

    cg.add(var.set_topic(config[CONF_TOPIC]))
    cg.add(var.set_heartbeat_interval(config[CONF_HEARTBEAT_INTERVAL]))

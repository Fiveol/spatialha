#include "spatialble_ble_server.h"
#include "esphome/core/log.h"
#include "esphome/core/application.h"
#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/components/network/util.h"

#ifdef USE_ESP32_BLE_TRACKER
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"
#endif

#ifdef USE_ARDUINOJSON
#include <ArduinoJson.h>
#endif

namespace esphome {
namespace spatialble {

static const char *const TAG = "spatialble";

static const float DEBOUNCE_RSSI_DELTA = 5.0f;
static const float DEBOUNCE_TIME_SEC = 30.0f;
static const uint16_t ESPHOME_OTA_PORT = 8266;

void SpatialBLEServer::setup() {
  server_id_ = App.get_name();

  // Resolve OTA IP via network interface
  ota_ip_ = network::get_ip_address().str();
  if (ota_ip_ == "0.0.0.0") {
    ota_ip_ = "";
  }

  ESP_LOGI(TAG, "SpatialBLE server starting — device: %s, topic: %s, ota: %s:%d",
           server_id_.c_str(), topic_.c_str(), ota_ip_.c_str(), ESPHOME_OTA_PORT);

  publish_heartbeat_();
  last_heartbeat_ms_ = millis();
}

void SpatialBLEServer::loop() {
  uint32_t now = millis();
  if (now - last_heartbeat_ms_ >= heartbeat_interval_) {
    publish_heartbeat_();
    last_heartbeat_ms_ = now;
  }
}

bool SpatialBLEServer::parse_device(const esp32_ble_tracker::ESPBTDevice &device) {
  float now = millis() / 1000.0f;
  std::string addr = device.address_str();
  int rssi = device.get_rssi();

  auto it = last_publish_.find(addr);
  if (it != last_publish_.end()) {
    float dt = now - it->second.time;
    int dr = std::abs(rssi - it->second.rssi);
    if (dr < DEBOUNCE_RSSI_DELTA && dt < DEBOUNCE_TIME_SEC) {
      return true;
    }
  }
  last_publish_[addr] = {now, rssi};

  publish_device_(device, now);
  return true;
}

void SpatialBLEServer::publish_heartbeat_() {
  if (mqtt::global_mqtt_client == nullptr)
    return;

  std::string topic = topic_ + "/" + server_id_;

  DynamicJsonDocument doc(512);
  doc["type"] = "heartbeat";
  doc["server_id"] = server_id_;
  doc["timestamp"] = millis() / 1000.0;

  if (!ota_ip_.empty()) {
    doc["ota_ip"] = ota_ip_;
    doc["ota_port"] = ESPHOME_OTA_PORT;
  }

  std::string payload;
  serializeJson(doc, payload);
  mqtt::global_mqtt_client->publish(topic, payload, 1, false);
}

void SpatialBLEServer::publish_device_(const esp32_ble_tracker::ESPBTDevice &device,
                                       float timestamp) {
  if (mqtt::global_mqtt_client == nullptr)
    return;

  std::string topic = topic_ + "/" + server_id_;

  DynamicJsonDocument doc(3072);
  doc["type"] = "advertisement";
  doc["server_id"] = server_id_;
  doc["timestamp"] = timestamp;

  JsonObject dev = doc.createNestedObject("device");
  dev["address"] = device.address_str();

  std::string name = device.get_name();
  if (!name.empty())
    dev["name"] = name;

  dev["rssi"] = device.get_rssi();

  // TX Power
  auto tx_power = device.get_tx_power();
  if (tx_power.has_value())
    dev["tx_power"] = *tx_power;

  // Manufacturer data
  if (!device.get_manufacturer_datas().empty()) {
    JsonObject mfr = dev.createNestedObject("manufacturer_data");
    for (const auto &md : device.get_manufacturer_datas()) {
      char buf[16];
      snprintf(buf, sizeof(buf), "%04x", md.uuid);

      std::string hex;
      for (uint8_t b : md.data) {
        char nibble[4];
        snprintf(nibble, sizeof(nibble), "%02x", b);
        hex += nibble;
      }
      mfr[buf] = hex;
    }
  }

  // Service UUIDs
  if (!device.get_service_uuids().empty()) {
    JsonArray svc = dev.createNestedArray("service_uuids");
    for (const auto &uuid : device.get_service_uuids())
      svc.add(uuid.to_string());
  }

  // Service data
  if (!device.get_service_datas().empty()) {
    JsonObject svc_data = dev.createNestedObject("service_data");
    for (const auto &sd : device.get_service_datas()) {
      std::string hex;
      for (uint8_t b : sd.data) {
        char nibble[4];
        snprintf(nibble, sizeof(nibble), "%02x", b);
        hex += nibble;
      }
      svc_data[sd.uuid.to_string()] = hex;
    }
  }

  std::string payload;
  serializeJson(doc, payload);
  mqtt::global_mqtt_client->publish(topic, payload, 1, false);

  ESP_LOGD(TAG, "Published %s (rssi=%d, name='%s')",
           device.address_str().c_str(), device.get_rssi(), name.c_str());
}

}  // namespace spatialble
}  // namespace esphome

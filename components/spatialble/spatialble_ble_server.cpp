#include "spatialble_ble_server.h"
#include "esphome/core/log.h"
#include "esphome/core/application.h"
#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/components/network/util.h"

#include <ArduinoJson.h>

namespace esphome {
namespace spatialble {

static const char *const TAG = "spatialble";

static const float DEBOUNCE_RSSI_DELTA = 5.0f;
static const float DEBOUNCE_TIME_SEC = 30.0f;
static const uint16_t ESPHOME_OTA_PORT = 8266;

static std::string bytes_to_hex(const std::vector<uint8_t> &data) {
  std::string out;
  out.reserve(data.size() * 2);
  for (uint8_t b : data) {
    char nibble[4];
    snprintf(nibble, sizeof(nibble), "%02x", b);
    out += nibble;
  }
  return out;
}

void SpatialBLEServer::setup() {
  server_id_ = App.get_name();

  auto ips = network::get_ip_addresses();
  if (!ips.empty()) {
    char buf[network::IP_ADDRESS_BUFFER_SIZE];
    ips[0].str_to(buf);
    ota_ip_ = buf;
  }
  if (ota_ip_ == "0.0.0.0" || ota_ip_.empty()) {
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

  JsonDocument doc;
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

  JsonDocument doc;
  doc["type"] = "advertisement";
  doc["server_id"] = server_id_;
  doc["timestamp"] = timestamp;

  JsonObject dev = doc["device"].to<JsonObject>();
  dev["address"] = device.address_str();

  std::string name = device.get_name();
  if (!name.empty())
    dev["name"] = name;

  dev["rssi"] = device.get_rssi();

  // TX Power — get_tx_powers() returns a vector
  auto tx_powers = device.get_tx_powers();
  if (!tx_powers.empty()) {
    dev["tx_power"] = tx_powers[0];
  }

  // Manufacturer data
  if (!device.get_manufacturer_datas().empty()) {
    JsonObject mfr = dev["manufacturer_data"].to<JsonObject>();
    for (const auto &md : device.get_manufacturer_datas()) {
      char uuid_buf[37];
      mfr[md.uuid.to_str(uuid_buf)] = bytes_to_hex(md.data);
    }
  }

  // Service UUIDs
  if (!device.get_service_uuids().empty()) {
    JsonArray svc = dev["service_uuids"].to<JsonArray>();
    for (const auto &uuid : device.get_service_uuids()) {
      char uuid_buf[37];
      svc.add(uuid.to_str(uuid_buf));
    }
  }

  // Service data
  if (!device.get_service_datas().empty()) {
    JsonObject svc_data = dev["service_data"].to<JsonObject>();
    for (const auto &sd : device.get_service_datas()) {
      char uuid_buf[37];
      svc_data[sd.uuid.to_str(uuid_buf)] = bytes_to_hex(sd.data);
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

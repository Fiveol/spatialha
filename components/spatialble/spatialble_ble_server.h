#pragma once

#include <map>
#include <string>

#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

namespace esphome {
namespace spatialble {

class SpatialBLEServer : public Component,
                          public esp32_ble_tracker::ESPBTDeviceListener {
 public:
  void setup() override;
  void loop() override;
  bool parse_device(const esp32_ble_tracker::ESPBTDevice &device) override;

  void set_topic(const std::string &topic) { topic_ = topic; }
  void set_heartbeat_interval(uint32_t interval_ms) {
    heartbeat_interval_ = interval_ms;
  }

 protected:
  void publish_heartbeat_();
  void publish_device_(const esp32_ble_tracker::ESPBTDevice &device, float timestamp);

  std::string server_id_;
  std::string topic_;
  std::string ota_ip_;
  uint32_t heartbeat_interval_{10000};
  uint32_t last_heartbeat_ms_{0};

  struct LastPublish {
    float time;
    int rssi;
  };
  std::map<std::string, LastPublish> last_publish_;
};

}  // namespace spatialble
}  // namespace esphome

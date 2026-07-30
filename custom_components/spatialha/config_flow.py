import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    DEFAULT_MQTT_PORT,
    DOMAIN,
)


class SpatialHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="SpatialHA", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MQTT_HOST): str,
                    vol.Optional(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): int,
                    vol.Optional(CONF_MQTT_USERNAME): str,
                    vol.Optional(CONF_MQTT_PASSWORD): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return SpatialHAOptionsFlow(config_entry)


class SpatialHAOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MQTT_HOST, default=data.get(CONF_MQTT_HOST, "")): str,
                    vol.Optional(
                        CONF_MQTT_PORT, default=data.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_MQTT_USERNAME, default=data.get(CONF_MQTT_USERNAME, "")
                    ): str,
                    vol.Optional(
                        CONF_MQTT_PASSWORD, default=data.get(CONF_MQTT_PASSWORD, "")
                    ): str,
                }
            ),
        )

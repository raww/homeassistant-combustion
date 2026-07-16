"""Constants for combustion."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Combustion"
DOMAIN = "combustion"
MANUFACTURER = "Combustion, Inc."
DEVICE_NAME = "Predictive Thermometer"
VERSION = "0.0.0"
ATTRIBUTION = ""

BT_MANUFACTURER_ID = 2503

CONF_DEVICES = "devices"

PRODUCT_TYPE_PROBE = 1
PRODUCT_TYPE_REPEATER_NODE = 2

CONF_AVAILABILITY_TIMEOUT = "availability_timeout"
CONF_UPDATE_THROTTLE = "update_throttle"
CONF_ENABLE_PREDICTIONS = "enable_predictions"

DEFAULT_AVAILABILITY_TIMEOUT = 90
DEFAULT_UPDATE_THROTTLE = 1.0
DEFAULT_ENABLE_PREDICTIONS = False

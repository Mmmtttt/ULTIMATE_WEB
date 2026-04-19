from .config_service import get_plugin_config_service
from .gateway import get_protocol_gateway
from .registry import get_plugin_registry

__all__ = [
    "get_plugin_config_service",
    "get_protocol_gateway",
    "get_plugin_registry",
]

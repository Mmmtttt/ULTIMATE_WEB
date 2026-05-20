"""
Compatibility shim for protocol credential validation helpers.
"""

from protocol.credential_guard import (  # noqa: F401
    ensure_adapter_query_ready,
    filter_configured_adapters,
    get_adapter_credential_status,
)

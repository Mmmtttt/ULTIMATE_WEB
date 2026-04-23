"""
Compatibility shim for the legacy external API facade.

This module is an alias to `protocol.adapter_api`, so monkeypatching the
legacy import path still affects the protocol-backed implementation.
"""

import sys

from protocol import adapter_api as _adapter_api

sys.modules[__name__] = _adapter_api

"""
Compatibility shim for legacy metadata adapter utilities.

This module is an alias to `protocol.metadata_adapter`.
"""

import sys

from protocol import metadata_adapter as _metadata_adapter

sys.modules[__name__] = _metadata_adapter

"""
Compatibility shim for the legacy platform service facade.

This module is an alias to `protocol.platform_service`, so legacy callers and
tests can keep patching `third_party.platform_service` while the host runs on
the protocol implementation.
"""

import sys

from protocol import platform_service as _platform_service

sys.modules[__name__] = _platform_service

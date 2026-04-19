"""
Compatibility shim for legacy adapter abstractions.

The real implementation now lives under `third_party.legacy` so the root
`third_party` package can focus on protocol entrypoints and compatibility APIs.
"""

from .legacy.base_adapter import *  # noqa: F401,F403

from __future__ import annotations

from typing import Any, Dict

from .base import ProtocolProvider


class MetadataOnlyProvider(ProtocolProvider):
    """No-op provider for metadata-only manifests such as mobile protocol snapshots."""

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        raise RuntimeError(
            f"metadata-only protocol snapshot does not implement runtime capability: {str(capability or '').strip()}"
        )

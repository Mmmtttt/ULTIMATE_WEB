from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class SoftRefReaderProtocol(Protocol):
    """Protocol for soft-ref media readers (comic/video, etc.)."""

    content_type: str

    def is_soft_ref_content(self, content_id: str) -> bool:
        ...

    def get_page_count(self, content_id: str) -> int:
        ...

    def get_image_stream(self, content_id: str, page_num: int) -> Tuple[io.BytesIO, str]:
        ...

    def set_archive_password(self, content_id: str, archive_fingerprint: str, password: str) -> Dict[str, Any]:
        ...

    def get_password_required_payload(self, content_id: str, exc: Exception) -> Dict[str, Any]:
        ...


class SoftRefReaderRegistry:
    """Registry for soft-ref readers by content type."""

    def __init__(self) -> None:
        self._readers: Dict[str, SoftRefReaderProtocol] = {}

    @staticmethod
    def _normalize_content_type(content_type: str) -> str:
        return str(content_type or "").strip().lower()

    def register(self, content_type: str, reader: SoftRefReaderProtocol) -> None:
        normalized = self._normalize_content_type(content_type)
        if not normalized:
            raise ValueError("content_type is required")
        if reader is None:
            raise ValueError("reader is required")
        self._readers[normalized] = reader

    def get(self, content_type: str) -> Optional[SoftRefReaderProtocol]:
        normalized = self._normalize_content_type(content_type)
        if not normalized:
            return None
        return self._readers.get(normalized)

    def require(self, content_type: str) -> SoftRefReaderProtocol:
        reader = self.get(content_type)
        if reader is None:
            raise RuntimeError(f"soft-ref reader is not registered for content_type={content_type}")
        return reader

    def list_content_types(self) -> List[str]:
        return sorted(self._readers.keys())


softref_reader_registry = SoftRefReaderRegistry()


def register_softref_reader(content_type: str, reader: SoftRefReaderProtocol) -> None:
    softref_reader_registry.register(content_type, reader)


def get_softref_reader(content_type: str) -> Optional[SoftRefReaderProtocol]:
    return softref_reader_registry.get(content_type)


def require_softref_reader(content_type: str) -> SoftRefReaderProtocol:
    return softref_reader_registry.require(content_type)


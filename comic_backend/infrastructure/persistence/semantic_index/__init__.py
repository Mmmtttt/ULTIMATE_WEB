from .builder import (
    build_document_text,
    build_search_text,
    build_vector_text,
    is_stale,
    load_tag_vocabulary,
    rebuild_index,
    source_stats,
)
from .connection import (
    INDEX_FILE_NAME,
    get_semantic_index_path,
    open_semantic_index,
    semantic_index_connection,
)
from .embedder import DEFAULT_MODEL_NAME, EmbeddingProvider, get_embedding_provider
from .engine import index_status, search
from .schema import SCHEMA_VERSION, ensure_schema, semantic_search_available
from .text import normalize

__all__ = [
    "INDEX_FILE_NAME",
    "SCHEMA_VERSION",
    "DEFAULT_MODEL_NAME",
    "EmbeddingProvider",
    "build_document_text",
    "build_search_text",
    "build_vector_text",
    "ensure_schema",
    "get_embedding_provider",
    "get_semantic_index_path",
    "index_status",
    "is_stale",
    "load_tag_vocabulary",
    "normalize",
    "open_semantic_index",
    "rebuild_index",
    "search",
    "semantic_index_connection",
    "semantic_search_available",
    "source_stats",
]

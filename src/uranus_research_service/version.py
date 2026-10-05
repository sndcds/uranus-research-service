"""Reviewed compatibility pins. These describe expectations, not deployed services."""

SERVICE_VERSION = "0.2.0"
CONTRACT_VERSION = "uranus-research-service-v1"
ENCODER_SERVICE_VERSION = "0.2.0"
ENCODER_CONTRACT = "uranus-research-encoder-v1"
MODEL = "jina-v5"
MODEL_REPOSITORY = "jinaai/jina-embeddings-v5-text-small"
MODEL_REVISION = "dd76d535f5447ca3897a9c893fb1e612ead98192"
DIMENSIONS = 1024
CHUNK_VERSION = "sections-480-overlap64-v2"
EMBEDDING_VERSION = (
    f"{MODEL_REVISION}:native-qwen3-torch2.11.0-transformers5.17.0-peft0.21.1-cpu-eager-"
    f"retrieval-query-document-last-token-l2-f32-d1024:{CHUNK_VERSION}"
)
ENCODER_EXPECTED = {
    "contract_version": ENCODER_CONTRACT,
    "model": MODEL,
    "model_repository": MODEL_REPOSITORY,
    "model_revision": MODEL_REVISION,
    "dimensions": DIMENSIONS,
    "chunk_version": CHUNK_VERSION,
    "embedding_version": EMBEDDING_VERSION,
}

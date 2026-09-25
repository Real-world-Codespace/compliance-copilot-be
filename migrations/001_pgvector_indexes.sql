CREATE EXTENSION IF NOT EXISTS vector;

CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS ix_document_chunks_tenant_acl
ON document_chunks (organization_id, classification);

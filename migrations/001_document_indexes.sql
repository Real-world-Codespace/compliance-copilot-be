-- PostgreSQL stays the source of truth for identity, ACL metadata, documents and audit.
-- Embeddings are stored in Pinecone, not in RDS.
CREATE INDEX IF NOT EXISTS ix_document_chunks_tenant_document
ON document_chunks (organization_id, document_id);

CREATE INDEX IF NOT EXISTS ix_document_chunks_tenant_classification
ON document_chunks (organization_id, classification);

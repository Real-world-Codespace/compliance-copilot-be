-- Run once on databases created by the previous pgvector revision.
-- Back up the database before applying this migration. Chunk text and ACL remain in RDS.
-- At the next API startup, existing chunks are re-embedded and indexed in Pinecone.
DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;
ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;

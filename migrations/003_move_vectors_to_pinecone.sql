-- Run once on databases created by the previous pgvector revision.
-- Verify the Pinecone backfill has completed before applying this migration.
DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;
ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;

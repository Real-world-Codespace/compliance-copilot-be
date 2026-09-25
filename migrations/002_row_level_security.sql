-- Apply using a database migration role after validating worker transaction context.
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_documents_isolation ON knowledge_documents
FOR ALL
USING (organization_id = current_setting('app.current_tenant', true))
WITH CHECK (organization_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_chunks_isolation ON document_chunks
FOR ALL
USING (organization_id = current_setting('app.current_tenant', true))
WITH CHECK (organization_id = current_setting('app.current_tenant', true));

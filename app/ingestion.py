import uuid

from sqlalchemy import delete

from .database import DocumentChunk, KnowledgeDocument, SessionLocal
from .extractor import extract_text
from .rag import chunk_text, index_chunks
from .vector_store import get_vector_store, namespace_for
from .storage import get_storage


def process_document(document_id: str) -> None:
    """Worker entrypoint. Move this call to SQS/ECS worker in production."""
    with SessionLocal() as session:
        document = session.get(KnowledgeDocument, document_id)
        if not document or not document.storage_key:
            return
        document.status = "processing"
        document.status_message = "Đang trích xuất, chia chunk và lập chỉ mục bảo mật."
        session.commit()

    try:
        pages = extract_text(get_storage().download(document.storage_key), document.original_filename or "document.txt")
        chunks = [(part, page.page_number) for page in pages for part in chunk_text(page.text) if part.strip()]
        if not chunks:
            raise ValueError("Không trích xuất được nội dung text từ tài liệu.")
        indexed_chunks = []
        with SessionLocal() as session:
            document = session.get(KnowledgeDocument, document_id)
            session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            get_vector_store().delete_document(namespace_for(document.organization_id), document_id)
            for position, (content, page_number) in enumerate(chunks):
                chunk = DocumentChunk(
                    id=f"chk-{uuid.uuid4().hex[:16]}", document_id=document_id,
                    organization_id=document.organization_id, position=position, page_number=page_number,
                    content=content, allowed_departments=document.allowed_departments,
                    allowed_roles=document.allowed_roles, classification=document.classification,
                )
                indexed_chunks.append(chunk)
                session.add(chunk)
            session.commit()
        index_chunks(indexed_chunks)
        with SessionLocal() as session:
            document = session.get(KnowledgeDocument, document_id)
            document.status = "ready"
            document.status_message = f"Đã lập chỉ mục {len(chunks)} chunks."
            session.commit()
    except Exception as error:
        with SessionLocal() as session:
            document = session.get(KnowledgeDocument, document_id)
            if document:
                document.status = "failed"
                document.status_message = str(error)[:900]
                session.commit()

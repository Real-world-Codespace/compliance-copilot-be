import uuid

from sqlalchemy import delete

from .database import DocumentChunk, KnowledgeDocument, SessionLocal
from .extractor import extract_text
from .rag import chunk_text, embed
from .storage import get_storage


def process_document(document_id: str) -> None:
    """Worker entrypoint. Move this call to SQS/ECS worker in production."""
    with SessionLocal() as session:
        document = session.get(KnowledgeDocument, document_id)
        if not document or not document.storage_key:
            return
        document.status = "processing"
        document.status_message = "Đang trích xuất, chia chunk và tạo embedding."
        session.commit()

    try:
        pages = extract_text(get_storage().download(document.storage_key), document.original_filename or "document.txt")
        chunks = [(part, page.page_number) for page in pages for part in chunk_text(page.text) if part.strip()]
        if not chunks:
            raise ValueError("Không trích xuất được nội dung text từ tài liệu.")
        embeddings = [embed(content) for content, _ in chunks]
        with SessionLocal() as session:
            document = session.get(KnowledgeDocument, document_id)
            session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            for position, ((content, page_number), embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                session.add(DocumentChunk(
                    id=f"chk-{uuid.uuid4().hex[:16]}", document_id=document_id,
                    organization_id=document.organization_id, position=position, page_number=page_number,
                    content=content, embedding=embedding, allowed_departments=document.allowed_departments,
                    allowed_roles=document.allowed_roles, classification=document.classification,
                ))
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

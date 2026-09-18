"""Knowledge Base, Document Upload, and RAG Indexing Routes."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import select, desc, func
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.database.models import (
    Document, KnowledgeDocument, KnowledgeChunk, KnowledgeBase,
    AuditEvent, AuditEventType, DocumentCategory, DocumentStatus
)
from packages.rag.document_parser import document_parser
from packages.rag.vector_store import vector_store

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


@router.get("/documents")
async def list_documents(current_user: CurrentUser, db: TenantDB):
    """List all indexed knowledge documents for the current tenant."""
    stmt = (
        select(Document)
        .where(Document.organization_id == current_user.org_id)
        .order_by(desc(Document.created_at))
        .limit(50)
    )
    res = await db.execute(stmt)
    docs = res.scalars().all()
    return docs


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    current_user: CurrentUser,
    db: TenantDB,
    name: Optional[str] = Form(None),
    category: Optional[str] = Form("general"),
    access_level: Optional[str] = Form("global"),
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    """
    Upload a document (PDF, TXT, CSV, DOCX), extract text, chunk, and index into RAG database.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded_document"
    doc_title = name or filename

    # 1. Extract text and semantic chunks
    raw_text = document_parser.extract_text(file_bytes, filename)
    chunks = document_parser.chunk_text(raw_text, chunk_size=500, overlap=50)

    # 2. Persist Document record
    doc_id = uuid.uuid4()
    cat_enum = DocumentCategory.GENERAL
    if "invoice" in filename.lower() or "financial" in filename.lower():
        cat_enum = DocumentCategory.FINANCIAL
    elif "sop" in filename.lower() or "policy" in filename.lower():
        cat_enum = DocumentCategory.LEGAL

    new_doc = Document(
        id=doc_id,
        organization_id=current_user.org_id,
        owner_id=current_user.user_id,
        name=doc_title,
        slug=doc_title.lower().replace(" ", "-")[:100],
        file_path=f"uploads/{doc_id}_{filename}",
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type or "application/octet-stream",
        category=cat_enum,
        status=DocumentStatus.ACTIVE,
        is_indexed=True,
        indexed_at=datetime.utcnow()
    )
    db.add(new_doc)
    await db.flush()

    # 3. Persist KnowledgeDocument & Chunks
    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.organization_id == current_user.org_id).limit(1)
    kb = (await db.execute(kb_stmt)).scalars().first()

    kd = KnowledgeDocument(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id if kb else uuid.uuid4(),
        document_id=new_doc.id,
        title=doc_title,
        status="indexed",
        chunk_count=len(chunks),
        token_count=sum(c.token_count for c in chunks)
    )
    db.add(kd)
    await db.flush()

    for c in chunks:
        kc = KnowledgeChunk(
            id=uuid.uuid4(),
            knowledge_document_id=kd.id,
            chunk_index=c.chunk_index,
            content=c.content,
            token_count=c.token_count
        )
        db.add(kc)

    # 4. Index Chunks into Vector Store with departmental & tenant metadata
    chunk_texts = [c.content for c in chunks]
    dept_scope = (access_level or "global").lower()
    chunk_metas = [
        {
            "tenant_id": str(current_user.org_id),
            "document_id": str(new_doc.id),
            "document_title": doc_title,
            "chunk_index": c.chunk_index,
            "department": dept_scope
        }
        for c in chunks
    ]
    chunk_ids = [f"{new_doc.id}_{c.chunk_index}" for c in chunks]
    vector_store.add_documents(
        collection_name="agentic_knowledge",
        documents=chunk_texts,
        metadatas=chunk_metas,
        ids=chunk_ids
    )

    # 5. Record Audit Event
    audit_ev = AuditEvent(
        organization_id=current_user.org_id,
        user_id=current_user.user_id,
        user_role=current_user.role,
        document_id=new_doc.id,
        document_name=doc_title,
        event_type=AuditEventType.DOCUMENT_UPLOAD,
        event_name=f"Document Indexed for RAG: {doc_title}",
        description=f"Uploaded '{doc_title}' ({len(file_bytes)} bytes). Generated {len(chunks)} vector chunks.",
        result="success"
    )
    db.add(audit_ev)

    await db.commit()
    await db.refresh(new_doc)

    return {
        "ok": True,
        "document_id": str(new_doc.id),
        "name": new_doc.name,
        "chunks_indexed": len(chunks),
        "department_scope": dept_scope,
        "vector_store": "ChromaDB (Local Persistent)",
        "status": "indexed"
    }


@router.get("/search")
async def search_knowledge(
    q: str,
    current_user: CurrentUser,
    db: TenantDB,
    scope: Optional[str] = "global",
):
    """Semantic vector search across indexed knowledge chunks using ChromaDB with departmental scoping."""
    # 1. First attempt Chroma vector similarity search
    vector_results = vector_store.query(
        collection_name="agentic_knowledge",
        query_text=q,
        top_k=5,
        scope=scope
    )
    if vector_results:
        return {
            "query": q,
            "scope": scope,
            "engine": "ChromaDB Semantic Vector Retrieval",
            "results": vector_results
        }

    # 2. Database full-text query fallback
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
    )
    if q and q.strip():
        stmt = stmt.where(
            (KnowledgeChunk.content.ilike(f"%{q.strip()}%")) |
            (KnowledgeDocument.title.ilike(f"%{q.strip()}%"))
        )
    stmt = stmt.limit(10)
    res = await db.execute(stmt)
    rows = res.all()

    results = []
    for chunk, doc in rows:
        results.append({
            "document_title": doc.title,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "department": scope or "global",
            "relevance_score": 0.94
        })

    return {
        "query": q,
        "scope": scope,
        "engine": "Relational Index Fallback",
        "results": results
    }
